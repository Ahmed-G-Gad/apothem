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
Shallow-clone or no-git contexts (no ``.git/``, empty repo) exit 0 with
an informational status so the validator never blocks a fresh clone or
a non-git working tree.

Exit semantics. Exits 0 when HEAD is conformant (or informationally
exempt). Exits 2 on any drift class. The exit-2 convention matches the
conformity-gate orchestrator's ``EXIT_FAIL`` constant.
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

# Bound the gate-path git invocation so a hung `git log` cannot block a
# commit indefinitely; a timeout is treated as a transient git error.
GIT_TIMEOUT_SECONDS: Final[int] = 5

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

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, passed, status, subject,
        drifts}``; each finding is flattened through ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "passed": self.passed,
            "status": self.status,
            "subject": self.subject,
            "drifts": [asdict(d) for d in self.drifts],
        }
        return json.dumps(payload, indent=2)


def _read_head_subject(root: Path) -> tuple[str | None, str]:
    """Return ``(subject, status)`` for the HEAD commit.

    ``status`` is one of ``ok`` (subject populated), ``not-a-git-repo``,
    ``no-commits-yet``, ``git-unavailable``. The subject is None for
    every non-``ok`` status so the caller can short-circuit.
    """
    if not (root / ".git").exists():
        return None, "not-a-git-repo"
    try:
        completed = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],  # noqa: S607 — literal git argv, trusted PATH lookup, no shell
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "git-unavailable"
    if completed.returncode != 0:
        # Empty repo or other transient git error — never block.
        return None, "no-commits-yet"
    body = completed.stdout or ""
    first_line = body.splitlines()[0] if body.strip() else ""
    if not first_line:
        return None, "no-commits-yet"
    return first_line, "ok"


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

    Pre-conditions: ``root`` is the working-tree directory.
    Post-conditions: ``result.passed`` is True iff HEAD is conformant
    or the repo state is informationally exempt (no .git, no commits).
    """
    subject, status = _read_head_subject(root)
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
    # Imported here, not at module top: ``check_repo()`` stays stdlib-only.
    from apothem.conformity._grep_base import finish_root_report, parse_root_args

    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    result = check_repo(root)
    # One HEAD subject is inspected. A directory with no commit history (no
    # repository, or no commit yet) is the documented exempt state, not a
    # vacuous pass.
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=int(result.subject is not None),
        empty_scope_expected=result.subject is None,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
