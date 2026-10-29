# SPDX-License-Identifier: MIT

"""Fail when the hash-locked CI pip, or a workflow's pip install, drifts.

CI upgrades the runner's pip from one file, ``scripts/ci/requirements-ci-pip.txt``,
with ``python -m pip install --require-hashes -r scripts/ci/requirements-ci-pip.txt``.
pip 26.2 or later closes CVE-2026-13346. CI installs every other Python
dependency from a hash-locked file in ``scripts/ci/`` the same way. This check
enforces both contracts mechanically so a bump cannot silently land in some
workflows and not others:

(a) The lock file exists and pins exactly one requirement, ``pip==X.Y.Z``, with
   at least one ``--hash=sha256:<64 hex>`` and a version at or above the
   CVE floor.
(b) No workflow file (``*.yml`` / ``*.yaml``) under ``.github/workflows``
   mentions ``PIP_PIN_VERSION``, the retired per-workflow env pin. Markdown
   files in that folder are not scanned, so a README may name the retired
   variable.
(c) Every workflow line that installs pip itself (a ``pip install`` whose
   requirement is ``pip``, ``pip==<version>`` or ``--upgrade pip`` / ``-U pip``)
   uses ``--require-hashes -r scripts/ci/requirements-ci-pip.txt``. A line is
   split at ``&&``, ``||``, ``;`` and ``|`` first, so each chained install is
   judged on its own.
(d) Every other ``pip install`` that starts a command (``pip install`` or
   ``<interpreter> -m pip install``) is pinned the way OpenSSF Scorecard's
   Pinned-Dependencies check counts it: it carries a literal
   ``--require-hashes``, or is ``--no-deps -e <local path>`` with no other
   requirement, or installs only ``*.whl`` files. The exceptions are listed in
   ``STEP_D_TOOL_PINS`` and ``ENGINE_PREREQUISITE_INSTALLS``. Text that merely
   mentions ``pip install`` (a ``grep`` pattern, an ``echo``) does not start a
   command and is not judged.

Limits: only workflow files are scanned (not composite actions under
``.github/actions``), and only backslash line continuations are joined, so a
PowerShell backtick continuation, a heredoc, or a requirement read from a shell
variable is not recognised. The scan is line-oriented and does not read the
``shell:`` of a step, so rule (d) also holds PowerShell lines to the bash rule,
which keeps them consistent with their bash siblings.

Exit 0 when the lock and the workflows agree, 1 (with a diagnostic naming the
fix) on any drift. The script is dependency-free (line-oriented parsing, no
PyYAML) so it runs on the conformity-gate execution path without extra
packages.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

LOCK_RELPATH = "scripts/ci/requirements-ci-pip.txt"
WORKFLOW_RELDIR = ".github/workflows"

# CVE-2026-13346: pip earlier than 26.2 mishandles doubly-encoded package URLs
# from indexes. The lock file must pin at least this (major, minor).
PIP_CVE_FLOOR = (26, 2)
_PIP_CVE_FLOOR_TEXT = ".".join(str(part) for part in PIP_CVE_FLOOR)

_RETIRED_ENV_NAME = "PIP_PIN_VERSION"
_LOCK_REQUIREMENT_RE = re.compile(r"^pip==(?P<version>\d+\.\d+(?:\.\d+)*)$")
_LOCK_HASH_RE = re.compile(r"^--hash=sha256:[0-9a-f]{64}$")
_INLINE_COMMENT_RE = re.compile(r"(?:^|\s)#.*$")
# `pip install ...` as `pip install`, `python -m pip install`,
# `"$APOTHEM_PYTHON" -m pip install`; `pip-audit` has no whitespace after `pip`.
_PIP_INSTALL_RE = re.compile(r"\bpip3?\s+install\b(?P<rest>.*)$")
# Shell separators that chain several commands on one logical line.
_CHAIN_SPLIT_RE = re.compile(r"&&|\|\||;|\|")
# A requirement token that is pip itself: bare `pip` (also the target of
# `--upgrade pip` / `-U pip`) or `pip` followed by a version operator.
_PIP_ITSELF_RE = re.compile(r"^pip(?:$|(?:==|>=|<=|~=|!=|<|>)\S*)")

# Single-tool installs that wait for the maintainer's decision on whether to
# hash-lock them or accept them as exact pins. Each exact pin is the Scorecard
# finding that remains; the file name plus the requirement keys the entry, so a
# version bump of a tool updates this list in the same change. Remove an entry
# when its install moves to a hash-locked file.
STEP_D_TOOL_PINS: dict[str, frozenset[str]] = {
    "ci.yml": frozenset({"bandit[toml]==1.9.4", "pip-audit==2.10.1"}),
    "conformity.yml": frozenset({"ruff==0.15.20"}),
    "license-audit.yml": frozenset({"pip-licenses==5.5.5"}),
    "markdown-lint.yml": frozenset({"pre-commit==4.7.0"}),
    "pip-audit.yml": frozenset({"pip-audit==2.10.1"}),
}

# npm-shim.yml installs the engine's own host prerequisites (HOST_PREREQUISITES
# in src/apothem/__main__.py) through an interpreter held in a shell variable,
# `"$APOTHEM_PYTHON" -m pip install "${specs[@]}"`. Scorecard does not scan that
# form, and tests/integration/test_npm_shim_workflow.py asserts the step keeps
# installing what the engine prints.
ENGINE_PREREQUISITE_INSTALLS: dict[str, frozenset[str]] = {
    "npm-shim.yml": frozenset({"${specs[@]}"}),
}

# A command position: `pip install ...` or `<interpreter> -m pip install ...`.
# The interpreter is one word or one quoted word, optionally followed by a
# launcher flag such as `-3`; a quote right before `-m` or `pip` (as in
# `grep "-m pip install"`) does not match.
_COMMAND_PIP_INSTALL_RE = re.compile(
    r"^(?:(?:\"[^\"]*\"|[^\s\"'-]\S*)\s+(?:-\d\S*\s+)?-m\s+)?"
    r"pip3?\s+install\b(?P<rest>.*)$"
)
# YAML and shell prefixes that precede a command on the same line, including
# `sudo`, `env` and bare `VAR=value` assignments.
_COMMAND_PREFIX_RE = re.compile(
    r"^(?:-\s+)?(?:run:\s*(?:[|>][-+]?\s*)?)?(?:(?:then|do|else)\s+)?"
    r"(?:sudo\s+(?:-\S+\s+)*)?(?:env\s+)?(?:[A-Za-z_]\w*=\S*\s+)*"
)
# Options that take a value, so the value is not read as a requirement.
_OPTIONS_WITH_VALUE = frozenset(
    {
        "-c",
        "--constraint",
        "-f",
        "--find-links",
        "-i",
        "--index-url",
        "--extra-index-url",
        "--prefix",
        "--root",
        "-t",
        "--target",
        "--python-version",
        "--platform",
        "--implementation",
        "--abi",
        "--only-binary",
        "--no-binary",
        "--progress-bar",
        "--report",
    }
)
_LOCAL_PATH_RE = re.compile(r"^(?:\.{1,2}(?:$|[/\\\[])|/)")


@dataclass
class Report:
    """Outcome of one check: the problems found and the facts for the summary."""

    problems: list[str] = field(default_factory=list)
    version: str | None = None
    hash_count: int = 0
    install_sites: int = 0
    judged_installs: int = 0


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Return ``(first line number, line)`` with backslash continuations joined."""
    joined: list[tuple[int, str]] = []
    pending: list[str] = []
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        if not pending:
            start = number
        stripped = raw.rstrip()
        if stripped.endswith("\\"):
            pending.append(stripped[:-1])
            continue
        pending.append(raw)
        joined.append((start, " ".join(part.strip() for part in pending)))
        pending = []
    if pending:
        joined.append((start, " ".join(part.strip() for part in pending)))
    return joined


def _check_lock(lock_path: Path, report: Report) -> None:
    """Validate the lock file: one hashed ``pip==X.Y.Z`` at or above the floor."""
    if not lock_path.is_file():
        report.problems.append(
            f"{LOCK_RELPATH} is missing; restore it (it pins `pip=={_PIP_CVE_FLOOR_TEXT}` "
            "or later with --hash=sha256 lines) and see scripts/ci/README.md to "
            "regenerate it"
        )
        return

    requirements: list[tuple[int, str]] = []
    for number, line in _logical_lines(lock_path.read_text(encoding="utf-8")):
        content = _INLINE_COMMENT_RE.sub("", line).strip()
        if content:
            requirements.append((number, content))

    if len(requirements) != 1:
        report.problems.append(
            f"{LOCK_RELPATH} holds {len(requirements)} requirement lines; keep exactly "
            "one, `pip==X.Y.Z` with its --hash=sha256 lines, and move every other "
            "package to its own file"
        )
        return

    number, content = requirements[0]
    tokens = content.split()
    match = _LOCK_REQUIREMENT_RE.match(tokens[0])
    if match is None:
        report.problems.append(
            f"{LOCK_RELPATH}:{number}: the requirement `{tokens[0]}` is not "
            "`pip==X.Y.Z`; pin pip to an exact version"
        )
        return

    version = match.group("version")
    report.version = version

    hashes = [token for token in tokens[1:] if _LOCK_HASH_RE.match(token)]
    report.hash_count = len(hashes)
    others = [token for token in tokens[1:] if not _LOCK_HASH_RE.match(token)]
    if others:
        report.problems.append(
            f"{LOCK_RELPATH}:{number}: unexpected `{' '.join(others)}`; only "
            "`--hash=sha256:<64 lowercase hex>` options may follow the pin"
        )
    if not hashes:
        report.problems.append(
            f"{LOCK_RELPATH}:{number}: `pip=={version}` has no `--hash=sha256:<64 hex>` "
            "option; regenerate the file with `uv pip compile --generate-hashes` "
            "(command in the file header) so `--require-hashes` can verify the download"
        )

    parts = tuple(int(part) for part in version.split("."))
    if parts[: len(PIP_CVE_FLOOR)] < PIP_CVE_FLOOR:
        report.problems.append(
            f"{LOCK_RELPATH}:{number}: `pip=={version}` is below {_PIP_CVE_FLOOR_TEXT}, "
            f"the first release that fixes CVE-2026-13346; pin pip {_PIP_CVE_FLOOR_TEXT} "
            "or later"
        )


def _tokens(rest: str) -> list[str]:
    """Split the text after ``pip install`` into unquoted tokens, comments dropped."""
    return [token.strip("\"'") for token in _INLINE_COMMENT_RE.sub("", rest).split()]


def _installs_pip_itself(rest: str) -> bool:
    """Return True when the text after ``pip install`` names pip as a requirement."""
    return any(_PIP_ITSELF_RE.match(token) for token in _tokens(rest))


def _uses_lock(rest: str) -> bool:
    """Return True when the install line carries ``--require-hashes -r <lock>``."""
    tokens = _tokens(rest)
    if "--require-hashes" not in tokens:
        return False
    return any(
        flag == "-r" and target == LOCK_RELPATH for flag, target in pairwise(tokens)
    )


@dataclass(frozen=True)
class _Install:
    """The parts of one ``pip install`` command that decide whether it is pinned."""

    positional: tuple[str, ...]
    editable: tuple[str, ...]
    flags: frozenset[str]
    has_requirement_file: bool


def _parse_install(rest: str) -> _Install:
    """Split the text after ``pip install`` into requirements, targets and flags."""
    positional: list[str] = []
    editable: list[str] = []
    flags: set[str] = set()
    has_requirement_file = False
    tokens = iter(_tokens(rest))
    for token in tokens:
        if token in ("-e", "--editable"):
            editable.append(next(tokens, ""))
        elif token.startswith("--editable="):
            editable.append(token.partition("=")[2])
        elif token in ("-r", "--requirement"):
            has_requirement_file = True
            next(tokens, None)
        elif token in _OPTIONS_WITH_VALUE:
            next(tokens, None)
        elif token.startswith("-"):
            flags.add(token)
        elif token:
            positional.append(token)
    return _Install(
        tuple(positional), tuple(editable), frozenset(flags), has_requirement_file
    )


def _is_scorecard_pinned(install: _Install) -> bool:
    """Return True when Scorecard counts the install as pinned.

    A literal ``--require-hashes``; or ``--no-deps -e <local path>`` with no other
    requirement; or only ``*.whl`` files.
    """
    if "--require-hashes" in install.flags:
        return True
    if install.has_requirement_file:
        return False
    if install.editable:
        return (
            "--no-deps" in install.flags
            and not install.positional
            and all(_LOCAL_PATH_RE.match(target) for target in install.editable)
        )
    return bool(install.positional) and all(
        requirement.endswith(".whl") for requirement in install.positional
    )


def _is_allow_listed(install: _Install, workflow_name: str) -> bool:
    """Return True when every requirement is an allow-listed tool pin of the file."""
    if install.editable or install.has_requirement_file or not install.positional:
        return False
    allowed = STEP_D_TOOL_PINS.get(workflow_name, frozenset()) | (
        ENGINE_PREREQUISITE_INSTALLS.get(workflow_name, frozenset())
    )
    return all(requirement in allowed for requirement in install.positional)


def _command_pip_install(segment: str) -> re.Match[str] | None:
    """Match ``segment`` when it starts a ``pip install`` command."""
    command = _COMMAND_PREFIX_RE.sub("", segment.strip(), count=1)
    return _COMMAND_PIP_INSTALL_RE.match(command)


def _check_scorecard_pinning(
    rel: str, workflow_name: str, number: int, rest: str, report: Report
) -> None:
    """Rule (d): report a command-position ``pip install`` that Scorecard flags."""
    report.judged_installs += 1
    install = _parse_install(rest)
    if _is_scorecard_pinned(install) or _is_allow_listed(install, workflow_name):
        return
    shown = " ".join(_tokens(rest)) or "(no requirement)"
    report.problems.append(
        f"{rel}:{number}: `pip install {shown}` is not pinned the way OpenSSF "
        "Scorecard counts it; install from a hash-locked file with "
        "`python -m pip install --require-hashes -r scripts/ci/requirements-ci-<name>.txt` "
        "(regenerate the locks with scripts/dev/refresh_ci_locks.py), install the "
        "package itself with `--no-deps -e <path>`, or install only `*.whl` files"
    )


def _check_workflows(repo_root: Path, report: Report) -> None:
    """Validate every workflow: no retired env pin, pip installed from the lock."""
    workflow_dir = repo_root / WORKFLOW_RELDIR
    if not workflow_dir.is_dir():
        report.problems.append(
            f"workflow directory not found: {workflow_dir}; run the check from a "
            "repository checkout"
        )
        return

    workflows = sorted(
        [*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")],
        key=lambda path: path.name,
    )
    for workflow in workflows:
        rel = workflow.relative_to(repo_root).as_posix()
        text = workflow.read_text(encoding="utf-8")

        for number, raw in enumerate(text.splitlines(), start=1):
            if _RETIRED_ENV_NAME in raw:
                report.problems.append(
                    f"{rel}:{number}: `{_RETIRED_ENV_NAME}` is retired; delete it and "
                    f"install pip with `python -m pip install --require-hashes -r "
                    f"{LOCK_RELPATH}`"
                )

        for number, line in _logical_lines(text):
            if line.lstrip().startswith("#"):
                continue
            for segment in _CHAIN_SPLIT_RE.split(line):
                match = _PIP_INSTALL_RE.search(segment)
                if match is None:
                    continue
                rest = match.group("rest")
                if not (_installs_pip_itself(rest) or LOCK_RELPATH in _tokens(rest)):
                    command = _command_pip_install(segment)
                    if command is not None:
                        _check_scorecard_pinning(
                            rel, workflow.name, number, command.group("rest"), report
                        )
                    continue
                report.install_sites += 1
                if not _uses_lock(rest):
                    report.problems.append(
                        f"{rel}:{number}: this line installs pip without the lock; "
                        f"change it to `python -m pip install --require-hashes -r "
                        f"{LOCK_RELPATH}`"
                    )


def check(repo_root: Path) -> Report:
    """Check the lock file and the workflows under ``repo_root``.

    Post-conditions: ``Report.problems`` is empty exactly when the lock file
    pins one hashed ``pip==X.Y.Z`` at or above ``PIP_CVE_FLOOR``, no workflow
    mentions ``PIP_PIN_VERSION``, and every workflow line that installs pip
    itself uses ``--require-hashes -r scripts/ci/requirements-ci-pip.txt``,
    and every other command-position ``pip install`` is Scorecard-pinned or
    allow-listed. Each problem names the file and the change that fixes it.
    """
    report = Report()
    _check_lock(repo_root / LOCK_RELPATH, report)
    _check_workflows(repo_root, report)
    return report


def main() -> int:
    """Report pip lock drift for this checkout; return the process exit code.

    Returns ``0`` when the lock file and every workflow agree and ``1`` when
    any problem is found. Diagnostics go to stderr, the success line to stdout.
    """
    report = check(_REPO_ROOT)

    if report.problems:
        print("pip lock drift detected:", file=sys.stderr)
        for problem in report.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(
        f"pip lock coherent: pip=={report.version} with {report.hash_count} hash(es); "
        f"{report.install_sites} workflow pip install(s) use {LOCK_RELPATH}; "
        f"{report.judged_installs} other pip install(s) are Scorecard-pinned or "
        "allow-listed"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
