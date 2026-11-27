# SPDX-License-Identifier: MIT

"""Flag HEAD commit messages that drift from the Conventional-Commits grammar.

Why this enforcement exists. The apothem source repo
ratifies enterprise-grade Conventional-Commits discipline at the
project ``CLAUDE.md`` Coding Conventions block: every commit subject
follows ``<type>(<scope>): <subject>`` where type is drawn from the
closed set {feat, fix, chore, docs, refactor, test, perf, ci, build,
style, revert, release}, scope is optional kebab/comma-form, subject is <= 72
characters, written in imperative mood, and carries no trailing period.
Drift is silent in git history; the standalone validator reads the
HEAD commit message via ``git log -1 --pretty=%B`` and reports the
specific drift classes that fail.

Scope. Corpus-level standalone validator. Reads HEAD only. Merge commit
subjects (``Merge branch ...`` / ``Merge pull request ...``) pass
through — the merger does not author the merged content's subject form.
Shallow-clone or no-git contexts (an empty repository, or a folder outside
any checkout) exit 0 with an informational status, so the validator never
blocks a fresh clone. A folder is outside any checkout when no ``.git`` entry
of any kind lies in it or in a folder above it that git's own search reaches.
A repository in a folder above it counts when it tracks a file in the folder
(``git ls-files``), and its HEAD subject is then checked. When it tracks
nothing there, as for a new project inside a home-folder dotfiles repository,
the folder is outside any checkout too. A ``.git`` entry that git cannot open,
such as an empty ``.git`` folder or a ``.git`` file that names no repository,
also counts: when git then finds no repository it can use, it fails, and so
does the check, with ``git-failed``. Two outcomes are not an
exempt context: a git command that runs past ``GIT_TIMEOUT_SECONDS`` (the
repository's own configuration can make git wait for ever) gives status
``git-timeout``, and a git that refuses the repository (another owner, a bad
configuration line, an include it cannot read, a ``.git`` entry it cannot
open) gives ``git-failed``. In both no HEAD subject was read, so the check
does not pass.

Exit semantics. Exits 0 when HEAD is conformant (or informationally
exempt). Exits 2 on any drift class, and on ``git-timeout`` or
``git-failed``. The exit-2 convention matches the conformity-gate
orchestrator's ``EXIT_FAIL`` constant.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "conventional-commit-grep"
RULE_ANCHOR: Final[str] = "CLAUDE.md Coding Conventions — Conventional Commits"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# Bound the gate-path git invocations so a hung `git log` cannot block a
# commit indefinitely. A timeout does not pass: the subject was never read.
# The limit sits far above the fraction of a second these commands take, so a
# slow or busy machine does not fail the check.
GIT_TIMEOUT_SECONDS: Final[int] = 60

# Statuses with nothing to inspect, which pass: no repository, no commit
# yet, or no git to read the history with.
EXEMPT_STATUSES: Final[frozenset[str]] = frozenset(
    {"not-a-git-repo", "no-commits-yet", "git-unavailable"}
)

ALLOWED_TYPES: Final[frozenset[str]] = frozenset(
    {
        "feat",
        "fix",
        "chore",
        "docs",
        "refactor",
        "test",
        "perf",
        "ci",
        "build",
        "style",
        "revert",
        "release",
    }
)

MAX_SUBJECT_LEN: Final[int] = 72

# Full Conventional-Commits subject form. The scope is optional and
# constrained to kebab-case / comma-separated lowercase ASCII tokens.
CONVENTIONAL_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!?): (?P<subject>.+)$"
)

# Scope shape: lowercase letters, digits, hyphens, commas, forward
# slashes (e.g. ``harness/claude_code`` style). Uppercase or spaces
# trigger the scope-malformed drift class.
SCOPE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9,\-/_]+$")

# Imperative-mood heuristic: forbid first verbs ending in -ed / -ing,
# and 3rd-person singular -s on common verbs. Heuristic only; intended
# to catch the most frequent drift forms (``added X``, ``adding X``,
# ``adds X``) without policing every English verb.
NON_IMPERATIVE_TAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<verb>[a-z]+?)(?P<tail>ed|ing)$", re.IGNORECASE
)

# Imperative verbs (and imperative-mood tokens) that merely end in the
# ``-ed`` / ``-ing`` letters without being a past-tense or gerund form —
# the ``-ed``/``-ing`` is part of the root, not an inflection. Without this
# allow-list the tail heuristic misfires on legitimate imperative subjects
# such as ``embed the schema`` or ``bring the adapter online``. Compared
# lower-cased against the first word.
IMPERATIVE_ALLOW_LIST: Final[frozenset[str]] = frozenset(
    {
        "embed",
        "shed",
        "feed",
        "bleed",  # (rare) kept for parity with the -eed family
        "breed",
        "speed",
        "seed",
        "need",
        "heed",
        "weed",
        "proceed",
        "exceed",
        "succeed",
        "bring",
        "ping",
        "ring",
        "sing",
        "string",
        "spring",
        "cling",
        "fling",
        "sling",
        "swing",
        "wring",
        "sting",
        "king",
        "wing",
        "thing",  # noun, but a valid first token in rare docs subjects
    }
)

# Common 3rd-person-singular verbs that surface as commit-message drift.
# Not exhaustive — intentionally narrow to avoid false positives on
# legitimate plural nouns acting as the first token (rare in imperative
# subjects but possible in chore/docs surfaces).
THIRD_PERSON_SINGULAR_VERBS: Final[frozenset[str]] = frozenset(
    {
        "adds",
        "removes",
        "updates",
        "fixes",
        "refactors",
        "renames",
        "moves",
        "creates",
        "deletes",
        "introduces",
        "implements",
        "applies",
        "changes",
        "handles",
        "wires",
        "ensures",
        "supports",
        "enables",
        "disables",
    }
)

MERGE_PREFIXES: Final[tuple[str, ...]] = (
    "Merge branch ",
    "Merge pull request ",
    "Merge remote-tracking branch ",
    "Merge tag ",
    # GitHub Actions checks out a synthetic `pull/N/merge` ref whose HEAD
    # subject is `Merge <sha> into <sha>`; it is machine-authored, not a
    # conventional commit. The generic "Merge " prefix covers this form (no
    # conventional subject starts with a capitalized "Merge ").
    "Merge ",
)


@dataclass(frozen=True)
class Drift:
    """One drift class detected on the HEAD commit subject."""

    klass: str
    detail: str
    subject: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated result for a single HEAD-commit-subject check."""

    grep: str
    passed: bool
    status: str
    subject: str | None = None
    drifts: list[Drift] = field(default_factory=list)
    # Why the check could not finish (``git-timeout`` or ``git-failed``);
    # None otherwise.
    check_error: str | None = None

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, passed, status, subject,
        drifts}``, plus ``check_error`` when it is set; each finding is
        flattened through ``dataclasses.asdict``.
        """
        payload: dict[str, object] = {
            "grep": self.grep,
            "passed": self.passed,
            "status": self.status,
            "subject": self.subject,
            "drifts": [asdict(d) for d in self.drifts],
        }
        if self.check_error is not None:
            # The same key as ``_grep_base.CHECK_ERROR_KEY``, spelled out so
            # the module imports without the package.
            payload["check_error"] = self.check_error
        return json.dumps(payload, indent=2)


def _git(
    root: Path, label: str, *args: str, file_names: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` in *root* within ``GIT_TIMEOUT_SECONDS``.

    git runs through :func:`~apothem.conformity._git.run_git`, which turns off
    the repository's program-running settings and keeps the limit for every
    program git starts. *file_names* keeps every byte of the output, as
    ``run_git`` does for a path name. Raises
    :class:`~apothem.conformity._grep_base.GitTimeoutError`, naming the
    command as *label*, past the limit and :class:`OSError` when git cannot be
    started.
    """
    # Imported here, not at module top, so the module itself imports without
    # the package; only a run that reads git history needs it.
    from apothem.conformity._git import run_git
    from apothem.conformity._grep_base import GitTimeoutError

    try:
        return run_git(
            list(args),
            cwd=root,
            timeout=GIT_TIMEOUT_SECONDS,
            file_names=file_names,
            discover=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitTimeoutError(label, GIT_TIMEOUT_SECONDS) from exc


def _checked(
    completed: subprocess.CompletedProcess[str], label: str, *ok: int
) -> subprocess.CompletedProcess[str]:
    """Return *completed*, or raise when its exit code is not 0 or in *ok*."""
    from apothem.conformity._grep_base import GitFailedError

    if completed.returncode != 0 and completed.returncode not in ok:
        raise GitFailedError(label, completed.returncode)
    return completed


def _tracks_a_file_in(root: Path, prefix: str) -> bool:
    """Return True when git's repository tracks a file in *root* or below it.

    The index counts, so a staged file is tracked. When the repository
    ignores case (``core.ignorecase``, as on Windows and macOS), the folder's
    path below the top, *prefix* from :func:`_work_tree_prefix`, is matched
    without regard to case. A tracked folder renamed on disk only in case
    then still counts: git status shows no change there, but
    ``git ls-files -- .`` matches by case and lists nothing. The setting is
    read only then, so a tracked folder costs one git start. Raises
    :class:`~apothem.conformity._grep_base.GitFailedError` when a git command
    fails.
    """
    if _lists_a_file(root, "."):
        return True
    case = _checked(
        _git(root, "git config", "config", "--type=bool", "--get", "core.ignorecase"),
        "git config",
        1,  # The setting is not there: git then matches by case.
    )
    if case.returncode != 0 or case.stdout.strip() != "true":
        return False
    # *prefix* ends in "/", as git spells the path from the folder on disk.
    # ``top`` reads it from the top, where ``icase`` covers every part of it.
    # ``literal`` is a guard only: git compares the path as plain text first,
    # and the trailing "/" keeps a "*" or "[" in a name from matching another
    # folder, so it changes no result today.
    return _lists_a_file(root, f":(top,icase,literal){prefix}")


def _lists_a_file(root: Path, pathspec: str) -> bool:
    """Return True when ``git ls-files`` in *root* lists a file for *pathspec*."""
    tracked = _checked(
        _git(root, "git ls-files", "ls-files", "-z", "--", pathspec),
        "git ls-files",
    )
    return bool(tracked.stdout)


def _work_tree_prefix(root: Path) -> str:
    """Return *root*'s path below the top of the work tree git uses there.

    git answers: ``git rev-parse --show-prefix`` prints it with a trailing
    ``/``, and nothing at the top, so a non-empty result means the top is
    above *root*; only a repository whose top is above *root* is one *root*
    may not belong to. Nothing in a ``.git`` entry is read here. A git
    failure gives an empty result and is left to the ``git log`` that
    follows, which fails the same way. Raises
    :class:`~apothem.conformity._grep_base.GitTimeoutError` past the limit.
    """
    shown = _git(root, "git rev-parse", "rev-parse", "--show-prefix", file_names=True)
    return shown.stdout.removesuffix("\n") if shown.returncode == 0 else ""


def _read_head_subject(root: Path) -> tuple[str | None, str, str | None]:
    """Return ``(subject, status, check_error)`` for the HEAD commit.

    ``status`` is one of ``ok`` (subject populated), ``not-a-git-repo``,
    ``no-commits-yet``, ``git-unavailable`` (git could not be started),
    ``git-timeout`` (a git command ran past ``GIT_TIMEOUT_SECONDS``) or
    ``git-failed`` (git refused the repository: another owner, a bad
    configuration line, an include it cannot read). The subject is None for
    every non-``ok`` status so the caller can short-circuit; ``check_error``
    says why for the last two, and is None otherwise. git runs through
    :func:`~apothem.conformity._git.run_git`, so the repository's own settings
    cannot make it start a program (a signature check, say).
    """
    from apothem.conformity._grep_base import (
        GitCheckError,
        GitFailedError,
        GitTimeoutError,
        in_checkout,
        nearest_linked_git_entry,
    )

    # git finds the repository in ``root`` or a folder above it, so a run on
    # a subfolder of a checkout reads the checkout's history. git is not run
    # when a .git entry in ``root`` or a folder above it that git searches is
    # a link (dangling or not); which repository git then uses is git's own
    # answer, not checked here.
    if nearest_linked_git_entry(root) is not None or not in_checkout(root):
        return None, "not-a-git-repo", None
    try:
        prefix = _work_tree_prefix(root)
        if prefix and not _tracks_a_file_in(root, prefix):
            # git uses a repository in a folder above ``root`` (an empty
            # ``.git`` folder in ``root``, say from a ``git init`` that
            # stopped, is one git looks past). Its history belongs to ``root``
            # only when it tracks a file there. A new project inside a
            # home-folder dotfiles repository is not part of it, so it stays
            # exempt.
            return None, "not-a-git-repo", None
        completed = _git(root, "git log", "log", "-1", "--pretty=%B")
        if completed.returncode != 0:
            # A branch with no commit yet and a repository git refused both
            # fail the log; only the first is exempt. ``rev-parse --verify
            # --quiet`` exits 1 for a HEAD that names no commit, and 128 when
            # git cannot read the repository at all.
            head = _git(
                root, "git rev-parse", "rev-parse", "--verify", "--quiet", "HEAD"
            )
            if head.returncode == 1:
                return None, "no-commits-yet", None
            raise GitFailedError("git log", completed.returncode)
    except OSError:
        return None, "git-unavailable", None
    except GitCheckError as exc:
        status = "git-timeout" if isinstance(exc, GitTimeoutError) else "git-failed"
        return None, status, str(exc)
    body = completed.stdout or ""
    first_line = body.splitlines()[0] if body.strip() else ""
    if not first_line:
        return None, "no-commits-yet", None
    return first_line, "ok", None


def _is_merge_subject(subject: str) -> bool:
    return any(subject.startswith(prefix) for prefix in MERGE_PREFIXES)


def _classify_drift(subject: str) -> list[Drift]:
    """Return every drift class the subject exhibits (empty list = clean)."""
    drifts: list[Drift] = []
    match = CONVENTIONAL_RE.match(subject)
    if match is None:
        drifts.append(
            Drift(
                klass="missing-type",
                detail="subject does not match '<type>(<scope>)?: <subject>'",
                subject=subject,
            )
        )
        # Without a parsed shape the remaining drift classes are not
        # individually decidable; return the structural failure alone.
        return drifts

    type_token = match.group("type")
    scope_token = match.group("scope")
    body_subject = match.group("subject")

    if type_token not in ALLOWED_TYPES:
        drifts.append(
            Drift(
                klass="invalid-type",
                detail=f"type '{type_token}' not in {sorted(ALLOWED_TYPES)}",
                subject=subject,
            )
        )

    if scope_token is not None and not SCOPE_RE.match(scope_token):
        drifts.append(
            Drift(
                klass="scope-malformed",
                detail=(
                    f"scope '{scope_token}' contains characters outside [a-z0-9,-/_]"
                ),
                subject=subject,
            )
        )

    if len(subject) > MAX_SUBJECT_LEN:
        drifts.append(
            Drift(
                klass="subject-too-long",
                detail=f"subject length {len(subject)} > {MAX_SUBJECT_LEN}",
                subject=subject,
            )
        )

    if body_subject.endswith("."):
        drifts.append(
            Drift(
                klass="subject-ends-with-period",
                detail="subject body ends with '.' — strip the trailing period",
                subject=subject,
            )
        )

    first_word = body_subject.split(" ", 1)[0] if body_subject else ""
    if first_word:
        lower = first_word.lower()
        # Imperative verbs that merely end in the -ed/-ing letters (embed,
        # shed, bring, ping, …) are not inflections; the allow-list suppresses
        # the tail heuristic's false positive on them.
        tail = (
            None
            if lower in IMPERATIVE_ALLOW_LIST
            else NON_IMPERATIVE_TAIL_RE.match(first_word)
        )
        if tail is not None:
            drifts.append(
                Drift(
                    klass="non-imperative-verb",
                    detail=(
                        f"first word '{first_word}' ends with "
                        f"'-{tail.group('tail')}' — use imperative mood"
                    ),
                    subject=subject,
                )
            )
        elif lower in THIRD_PERSON_SINGULAR_VERBS:
            drifts.append(
                Drift(
                    klass="non-imperative-verb",
                    detail=(
                        f"first word '{first_word}' is 3rd-person singular — "
                        "use imperative mood"
                    ),
                    subject=subject,
                )
            )

    return drifts


def check_repo(root: Path) -> GrepResult:
    """Inspect ``root``'s HEAD commit; return a structured result.

    Pre-conditions: ``root`` is a folder; git reads the repository it is in,
    which can be in a folder above it.
    Post-conditions: ``result.passed`` is True iff HEAD is conformant or the
    repository state is informationally exempt: no ``.git`` entry in ``root``
    or above it (as far as git's own search goes), a repository above
    ``root`` that tracks no file in it, or no commits yet. A ``.git`` entry
    git cannot open (an empty ``.git`` folder, say) is not exempt: when git
    finds no repository it can use, it fails and the status is
    ``git-failed``. A git command
    past ``GIT_TIMEOUT_SECONDS`` gives status ``git-timeout``, and a git that
    refused the repository gives ``git-failed``: both have ``passed`` False
    and a ``check_error`` that names the command.
    """
    subject, status, check_error = _read_head_subject(root)
    if check_error is not None:
        return GrepResult(
            grep=GREP_NAME,
            passed=False,
            status=status,
            check_error=check_error,
        )
    if status != "ok" or subject is None:
        return GrepResult(
            grep=GREP_NAME,
            passed=True,
            status=status,
            subject=None,
        )
    if _is_merge_subject(subject):
        return GrepResult(
            grep=GREP_NAME,
            passed=True,
            status="merge-commit",
            subject=subject,
        )
    drifts = _classify_drift(subject)
    return GrepResult(
        grep=GREP_NAME,
        passed=not drifts,
        status="ok",
        subject=subject,
        drifts=drifts,
    )


def _main(argv: list[str]) -> int:
    # Imported here, not at module top, so the module itself imports without
    # the package.
    from apothem.conformity._grep_base import finish_root_report, parse_root_args

    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    result = check_repo(root)
    # One HEAD subject is inspected. A directory with no commit history (no
    # repository, or no commit yet) is the documented exempt state, not a
    # vacuous pass. A git command that ran past its limit, or a git that
    # refused the repository, is not exempt: it reports an unexpected empty
    # scope plus the ``check_error``.
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=int(result.subject is not None),
        empty_scope_expected=result.status in EXEMPT_STATUSES,
        check_error=result.check_error,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
