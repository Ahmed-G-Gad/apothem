# SPDX-License-Identifier: MIT

"""Validate filesystem paths against the canonical naming convention.

Why this enforcement exists. Spec section 4.1 ratifies kebab-case for
files and folders, with a closed set of canonical-uppercase exceptions
for ecosystem-wide singletons (CLAUDE.md, README.md, LICENSE, etc.) and
plan-suite singletons (MASTER-PLAN.md, PROGRESS.md, PHASE.md, SKILL.md,
VERSION). Numeric prefixes are admissible only inside ordered sequences
(phase folders `NN-topic/`, sub-phase folders `NNL-subtopic/`, migration
scripts where the host has ratified ordinal prefixes). The pre-emission
gate enforces the convention so namespace pollution cannot drift in
silently.

Per-family word-separator rule. Kebab-case governs files and folders
generally, but Python modules are snake_case by documented convention
(CLAUDE.md Coding Conventions: ``list[T]`` / snake_case modules). The two
disciplines do not conflict once encoded per filetype family:

* A ``.py`` / ``.pyi`` file's stem validates as **snake_case** (dunder
  ``__init__``/``__main__`` and leading-underscore private modules
  included) — the Python-package convention.
* A directory that is a Python package (its sibling files are modules)
  validates as snake_case too, so ``github_copilot/`` and ``claude_code/``
  pass without a per-name exception.
* Every other file and folder validates as kebab-case (plus the canonical
  singleton set).

Detection strategy. Each input path is split into its file and parent
components; each component is matched against (a) the canonical-name
exception set, (b) the ordered-sequence prefix patterns, and (c) the
per-family word-separator shape (snake_case for Python modules, kebab-case
otherwise). Components that match none are findings. Hidden directories (a
leading dot) are exempt because dotfile conventions are host-discovered.

Corpus mode. When ``_main`` is handed an absolute directory (the ``gate
--all`` invocation form), the validator walks the project's own authored
artifact tree (``src/apothem/``) and validates every tracked component
under the per-family rule — not merely the root basename. Vendored trees
(``_vendor/``) are out of scope: their names follow the upstream project's
convention, not this project's. Residual pre-existing violations that are
tracked follow-ups elsewhere are surfaced in ``notes`` rather than failing
the corpus run.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

# Canonical-uppercase exception set per spec section 4.1. These names
# are recognized verbatim regardless of casing rules. The set is closed;
# new exceptions land via rule revision, never ad-hoc.
CANONICAL_NAMES: Final[frozenset[str]] = frozenset(
    {
        "CLAUDE.md",
        "README.md",
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
        "CHANGELOG.md",
        "SECURITY.md",
        "SUPPORT.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "NOTICE",
        "NOTICE.md",
        "MASTER-PLAN.md",
        "PROGRESS.md",
        "PHASE.md",
        "SKILL.md",
        "REPORT.md",
        "PLAN-NOTES.md",
        "PREAMBLE.md",
        "COMPLETION.md",
        "VERSION",
        "MEMORY.md",
        "Makefile",
        # SHOUTING-KEBAB convention singleton carried by every harness adapter
        # package (the standard-convention pin snapshot), analogous to
        # MASTER-PLAN.md in the plan-suite family.
        "STANDARD-CONVENTION-PIN.md",
        # Materialized harness-output product surfaces: ecosystem-singleton
        # instruction-anchor filenames each downstream tool ratifies (Apothem
        # emits them, it does not author the name).
        "AGENTS.md",
        "GEMINI.md",
        "QWEN.md",
    }
)

# kebab-case for the principal stem; an optional dotted suffix carries
# the host-natural extension list. The stem may carry digits but not
# uppercase letters, underscores, or spaces.
KEBAB_STEM_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# snake_case for Python-module stems (and Python-package directories). A
# single leading underscore marks a private module; the dunder form
# (``__init__``, ``__main__``) is admitted explicitly.
SNAKE_STEM_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
DUNDER_STEM_RE: Final[re.Pattern[str]] = re.compile(r"^__[a-z0-9]+(?:_[a-z0-9]+)*__$")

# Python source suffixes governed by the snake_case family rule.
_PYTHON_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi"})

# Phase-folder prefix `NN-topic` and sub-phase-folder prefix `NNL-topic`
# (digits + optional single uppercase letter) honor the ordering
# discipline at canonical-layout section 2.1. The suffix is kebab-case.
PHASE_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"^[0-9]{2}[A-Z]?-[a-z0-9]+(?:-[a-z0-9]+)*$"
)

# Migration-script prefix `NNNN_name` honors the host-ratified ordinal
# scheme common to migration tooling.
MIGRATION_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"^[0-9]{2,5}_[a-z0-9]+(?:_[a-z0-9]+)*$"
)

# ADR filenames follow `NNNN-kebab-topic.md` per the ADR convention.
ADR_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"^[0-9]{4}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$"
)

GREP_NAME: Final[str] = "naming-grep"
RULE_ANCHOR: Final[str] = "CLAUDE.md Coding Conventions (kebab-case naming)"
EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2
STDIN_FLAG: Final[str] = "--stdin"


@dataclass(frozen=True)
class Finding:
    """One path component violating the ratified naming convention.

    Pre-conditions: ``component`` is the single offending path segment (a
    directory or file name), not the whole path, so the finding points at the
    exact token to rename; ``detail`` names the convention it breaks.
    Post-conditions: ``rule`` defaults to :data:`RULE_ANCHOR` so every finding
    cites the kebab-case naming discipline as its authority.
    """

    component: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Matcher report for a single sweep of this validator.

    Carries its own result shape rather than reusing the shared base because
    the payload adds ``components_inspected``, ``notes``.

    Pre-conditions: ``findings`` holds this module's frozen ``Finding``
    dataclasses. Post-conditions: ``passed`` is ``True`` exactly when
    ``findings`` is empty; :meth:`to_json` emits the serialised payload.
    """

    grep: str
    path: str | None
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    components_inspected: int = 0
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, path, passed,
        components_inspected, findings, notes}``; each finding is flattened
        through ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "path": self.path,
            "passed": self.passed,
            "components_inspected": self.components_inspected,
            "findings": [asdict(f) for f in self.findings],
            "notes": self.notes,
        }
        return json.dumps(payload, indent=2)


def _stem_and_extensions(name: str) -> tuple[str, str]:
    """Split a filename at the first dot; the suffix is the extension run."""
    if "." not in name:
        return name, ""
    head, tail = name.split(".", 1)
    return head, tail


def _is_canonical_name(name: str) -> bool:
    return name in CANONICAL_NAMES


def _is_phase_prefix(name: str) -> bool:
    return bool(PHASE_PREFIX_RE.match(name))


def _is_migration_prefix(stem: str) -> bool:
    return bool(MIGRATION_PREFIX_RE.match(stem))


def _is_adr_name(name: str) -> bool:
    return bool(ADR_NAME_RE.match(name))


def _suffix_of(name: str) -> str:
    """Return the terminal dotted suffix (lowercased) or '' when there is none."""
    if "." not in name or name.startswith("."):
        return ""
    return "." + name.rsplit(".", 1)[1].lower()


def _is_python_module_stem(stem: str) -> bool:
    """Return True for a snake_case Python-module stem (dunder / private ok)."""
    if DUNDER_STEM_RE.match(stem):
        return True
    body = stem[1:] if stem.startswith("_") else stem
    return bool(body) and bool(SNAKE_STEM_RE.match(body))


def _component_passes(name: str) -> tuple[bool, str]:
    """Return (passes, reason) under the per-family word-separator rule.

    A ``.py`` / ``.pyi`` component validates as snake_case (the Python-module
    family); a bare component with no dotted suffix admits kebab-case **or**
    snake_case (a directory may be a Python package); every other component
    validates as kebab-case plus the canonical singletons and ordered-sequence
    prefixes. ``reason`` explains the failure shape.
    """
    if not name:
        return True, ""
    if name.startswith("."):
        # Dotfiles and dot-dirs are host-discovered; do not enforce.
        return True, ""
    if _is_canonical_name(name):
        return True, ""
    # Phase-prefix shape (NN-topic / NNL-topic) is unambiguous; admit
    # regardless of the directory-vs-file inference because a user-
    # supplied path string carries no on-disk-stat hint.
    if _is_phase_prefix(name):
        return True, ""
    if _is_adr_name(name):
        return True, ""
    stem, _ = _stem_and_extensions(name)
    if _is_migration_prefix(stem):
        return True, ""

    suffix = _suffix_of(name)
    if suffix in _PYTHON_SUFFIXES:
        # Python-module family: snake_case stem, dunder / private admitted.
        py_stem = name[: -len(suffix)]
        if _is_python_module_stem(py_stem):
            return True, ""
        return False, (
            f"Python module {name!r} is not snake_case "
            f"(CLAUDE.md Coding Conventions: snake_case modules)"
        )
    if suffix == "":
        # A dotless component may be a Python-package directory (snake_case)
        # or a kebab-case folder; both are ratified word-separator forms.
        if KEBAB_STEM_RE.match(stem) or _is_python_module_stem(stem):
            return True, ""
        return False, (
            f"directory {name!r} is neither kebab-case nor snake_case "
            f"(spec section 4.1)"
        )
    # Non-Python file: kebab-case stem only.
    if KEBAB_STEM_RE.match(stem):
        return True, ""
    return False, (
        f"component {name!r} is neither kebab-case nor a canonical "
        f"exception (spec section 4.1)"
    )


def check(target: str, *, is_dir: bool | None = None) -> GrepResult:
    """Validate every path component against the naming convention.

    ``is_dir`` is retained for call-site signature compatibility; the
    convention check is component-shape-only and does not branch on
    whether the terminal component is a directory.
    """
    del is_dir  # accepted for signature compatibility; not consulted
    findings: list[Finding] = []
    parts = Path(target).parts
    for component in parts:
        # Drop drive anchors like 'C:', 'C:\\', or '/' on POSIX. The
        # Windows form `Path('D:\\foo').parts[0]` returns the literal
        # 'D:\\' (drive letter + colon + separator), not bare 'D:'.
        if (
            component.endswith(":")
            or component in ("/", "\\")
            or (len(component) >= 2 and component[1] == ":")
        ):
            continue
        passes, reason = _component_passes(component)
        if not passes:
            findings.append(Finding(component=component, detail=reason))
    return GrepResult(
        grep=GREP_NAME,
        path=target,
        passed=not findings,
        findings=findings,
    )


# Corpus mode. The authored artifact tree this project owns the naming of.
_CORPUS_ROOT: Final[str] = "src/apothem"

# Path fragments excluded from the corpus walk. ``_vendor/`` carries a
# third-party dependency closure whose names follow the upstream project's
# convention, and ``__pycache__`` is generated bytecode.
_CORPUS_EXEMPT_FRAGMENTS: Final[tuple[str, ...]] = ("_vendor/", "__pycache__/")


def _is_hidden_path(rel: str) -> bool:
    """Return True when any path segment is a dotfile / dot-directory.

    Hidden segments (``.mypy_cache``, ``.pytest_cache``, ``.ruff_cache``,
    ``.hypothesis`` and other generated local state) are host-discovered and
    out of the authored-naming scope, exactly as ``_component_passes`` exempts a
    dot-leading component.
    """
    return any(segment.startswith(".") for segment in rel.split("/"))


def _iter_corpus_files(root: Path) -> list[str]:
    """Return in-scope POSIX-relative file paths under the authored tree."""
    corpus = root / _CORPUS_ROOT
    if not corpus.is_dir():
        return []
    rels: list[str] = []
    for path in corpus.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if _is_hidden_path(rel):
            continue
        if any(fragment in rel for fragment in _CORPUS_EXEMPT_FRAGMENTS):
            continue
        rels.append(rel)
    return rels


def check_corpus(root: Path) -> GrepResult:
    """Walk the authored artifact tree; validate every component per family.

    Every in-scope file's relative-path components are validated under the
    per-family word-separator rule; any violation is a finding.
    """
    findings: list[Finding] = []
    inspected = 0
    for rel in _iter_corpus_files(root):
        parts = rel.split("/")
        for component in parts:
            inspected += 1
            passes, reason = _component_passes(component)
            if passes:
                continue
            findings.append(Finding(component=component, detail=f"{rel}: {reason}"))
    return GrepResult(
        grep=GREP_NAME,
        path=str(root),
        passed=not findings,
        findings=findings,
        components_inspected=inspected,
        notes=[],
    )


def _read_input(argv: list[str]) -> str:
    if len(argv) >= 2 and argv[1] != STDIN_FLAG:
        return argv[1]
    return sys.stdin.read().strip()


def _main(argv: list[str]) -> int:
    target = _read_input(argv)
    # In the conformity gate's --all mode this validator is handed the
    # absolute repository root. naming-grep then validates the project's own
    # authored artifact tree component-by-component (corpus mode) rather than
    # reducing the root to its basename — that reduction validated only the
    # literal string 'apothem' and left the corpus unscanned. Relative inputs
    # (the per-path invocation form) are validated component-by-component
    # unchanged.
    candidate = Path(target)
    if candidate.is_absolute() and candidate.is_dir():
        result = check_corpus(candidate)
    else:
        result = check(target)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
