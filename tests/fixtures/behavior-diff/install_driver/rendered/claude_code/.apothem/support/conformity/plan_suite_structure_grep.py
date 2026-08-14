# SPDX-License-Identifier: MIT

"""Validate plan-suite structure: suite-locality, closed vocab, numeric prefix.

Why this validator exists. The plan-suite layout discipline is declared
in prose across two rules but, until this matcher, no mechanical check
enforced it. ``rules/context-management-scratch.md`` 2 fixes the
suite-locality invariant (``_spec/`` / ``_inputs/`` / ``_outputs/`` exist
only as direct children of a suite folder), the disjoint purpose
vocabularies (``{spec}`` exclusive to ``_spec/``;
``{forge, notes, triage, draft, decisions, prose, requirements}``
exclusive to ``_inputs/``), and the ``_outputs/`` closed purpose set
(``{report, audit, rollup, metrics, export}`` or a kebab-topic name).
``rules/canonical-layout-reporting-tiers.md`` 2.1 fixes the
numeric-prefix discipline: ``NN-topic`` phase folders, ``NNL-subtopic``
sub-phase folders, and NO numeric prefix on suite-root singletons. This
validator operationalizes both rule sections as a single corpus-level
sweep over every ``<root>/.apothem/plans/<suite>/`` directory.

Detection strategy. The validator walks every immediate child of
``<root>/.apothem/plans/`` (each is a suite folder) and asserts, per suite:

  1. Suite-locality: ``_spec/`` / ``_inputs/`` / ``_outputs/`` appear only
     as DIRECT children of a suite folder, never at ``.apothem/plans/`` root
     and never nested deeper inside the suite.
  2. ``_spec/`` holds only ``spec.md`` at its root, plus the allowed
     subdirectories ``supporting/`` / ``diagrams/`` / ``citations/``.
  3. Disjoint purpose: no ``spec.md`` inside ``_inputs/``; no
     ``_inputs/``-vocabulary file (``forge.md`` / ``notes.md`` / ...)
     inside ``_spec/``.
  4. ``_outputs/`` top-level file purposes match the closed set
     ``{report, audit, rollup, metrics, export}-*`` OR a kebab-topic name
     (kebab-topic names are explicitly allowed by the rule).
  5. Numeric-prefix discipline: every ``phases/`` child directory matches
     ``NN-topic``; every sub-phase directory matches ``NNL-subtopic``;
     suite-root singletons carry NO numeric prefix; a ``00-X.md`` with no
     ``01-X`` sibling outside ``phases/`` is a finding.
  6. Phase coherence: every ``phases/NN-topic/`` contains a ``PHASE.md``.

Conservatism. The checks are deliberately low-false-positive. Unknown
underscore-prefixed directories (e.g. ``_notes/``) are NOT flagged --- the
rule's closed vocabulary governs only the three named directories, so a
sibling working directory outside that set carries no obligation under
this matcher. Kebab-topic filenames in ``_outputs/`` are accepted
wholesale (the rule admits them). The phase-folder regex tolerates any
kebab/alnum topic tail after the ``NN-`` prefix.

Exit semantics. Exits 0 (EXIT_PASS) when no findings; exits 2
(EXIT_FAIL) on any finding, matching the conformity-gate orchestrator's
EXIT_FAIL constant. When the root carries no ``.apothem/plans/`` directory
the validator passes vacuously (there is no suite to validate).

Bindings. Operationalizes ``rules/context-management-scratch.md`` 2
(suite-locality + closed vocabularies) and
``rules/canonical-layout-reporting-tiers.md`` 2.1 (numeric-prefix
discipline). Registered in ``gate.py`` STANDALONE_MODULES as
``plan-suite-structure-grep`` for ``--all`` and
``--check plan-suite-structure`` dispatch.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "plan-suite-structure-grep"
RULE_ANCHOR: Final[str] = (
    "context-management-scratch 2 (suite-locality + closed vocab) + "
    "canonical-layout-reporting-tiers 2.1 (numeric-prefix discipline)"
)

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# The three suite-local artifact-class directories. Each MUST appear only as a
# direct child of a suite folder, never at .apothem/plans/ root and never nested
# deeper inside the suite.
_ARTIFACT_CLASS_DIRS: Final[frozenset[str]] = frozenset(
    {"_spec", "_inputs", "_outputs"}
)

# `_spec/` closed vocabulary: the singleton `spec.md` plus three optional
# structural subdirectories. Anything else at the `_spec/` root is a finding.
_SPEC_SINGLETON: Final[str] = "spec.md"
_SPEC_ALLOWED_SUBDIRS: Final[frozenset[str]] = frozenset(
    {"supporting", "diagrams", "citations"}
)

# `_inputs/` closed-purpose canonical filename vocabulary. These canonical names
# are exclusive to `_inputs/`; a `_inputs/`-vocabulary file appearing in `_spec/`
# is cross-contamination. Free-form kebab-topic files are also allowed in
# `_inputs/`, so this set is used only to detect `_spec/` contamination, never to
# reject `_inputs/` members.
_INPUTS_CANONICAL_NAMES: Final[frozenset[str]] = frozenset(
    {
        "forge.md",
        "notes.md",
        "triage.md",
        "draft.md",
        "decisions.md",
        "prose.md",
        "requirements.md",
    }
)

# `_outputs/` closed purpose set. A top-level `_outputs/` filename either has a
# purpose prefix from this set (`report-*`, `audit-*`, ...) OR is a kebab-topic
# name; both are allowed by the rule. Non-kebab, non-purpose-prefixed names are
# findings.
_OUTPUTS_PURPOSES: Final[frozenset[str]] = frozenset(
    {"report", "audit", "rollup", "metrics", "export"}
)

# Suite-root singletons that, by the numeric-prefix discipline, carry NO numeric
# prefix. They are siblings of one another, not an ordered sequence. The set is
# the documented root-singleton class plus the README a suite may maintain.
_SUITE_ROOT_SINGLETONS: Final[frozenset[str]] = frozenset(
    {
        "PREAMBLE.md",
        "MASTER-PLAN.md",
        "MASTER-INDEX.md",
        "PROGRESS.md",
        "PLAN-NOTES.md",
        "COMPLETION.md",
        "TRACE-MATRIX.md",
        "README.md",
    }
)

# Phase folder: `NN-topic` --- a two-or-more-digit ordinal prefix, a hyphen, then
# a kebab/alnum topic tail. Sub-phase folder: `NNL-subtopic` --- the same ordinal
# prefix immediately followed by one-or-more uppercase letters, then the hyphen
# and topic. Both regexes anchor the whole directory name.
_PHASE_DIR_RE: Final[re.Pattern[str]] = re.compile(r"^\d{2,}-[a-z0-9][a-z0-9-]*$")
_SUBPHASE_DIR_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d{2,}[A-Z]+-[a-z0-9][a-z0-9-]*$"
)

# A bare numeric-prefix on a Markdown filename: `NN-...`. Used to flag a
# decorative ordinal prefix on a file living OUTSIDE `phases/` whose sibling set
# carries no ordering sequence.
_NUMERIC_PREFIX_FILE_RE: Final[re.Pattern[str]] = re.compile(r"^(\d{2,})-(.+)$")

# Kebab-case filename body (before the suffix): lowercase alnum segments joined
# by single hyphens. Used to accept free-form `_outputs/` topic names.
_KEBAB_STEM_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Date-stamped purpose form `purpose-YYYY-MM-DD`: the rule's canonical
# `_outputs/` filename pattern. The leading purpose token must be in the closed
# set; the trailing date is verified by shape.
_DATED_PURPOSE_RE: Final[re.Pattern[str]] = re.compile(r"^([a-z]+)-\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Finding:
    """One plan-suite structural violation."""

    suite: str
    path: str
    issue: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result for a single ``.apothem/plans/`` sweep."""

    grep: str
    root: str
    suite_count: int
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, suite_count,
        passed, findings}``; each finding is flattened through
        ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "suite_count": self.suite_count,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _outputs_filename_conformant(stem: str) -> bool:
    """Return True iff an ``_outputs/`` top-level file stem is conformant.

    Conformant when the stem is a dated purpose (``report-2026-06-16``), a
    bare-purpose token (``report``), a purpose-prefixed name
    (``report-foo``), or a free-form kebab-topic name (``i18n-gap``). The
    rule admits kebab-topic names wholesale, so the kebab test is the broad
    accept; the purpose tests exist to document the canonical forms.
    """
    dated = _DATED_PURPOSE_RE.match(stem)
    if dated is not None and dated.group(1) in _OUTPUTS_PURPOSES:
        return True
    # Kebab-topic (which also covers `report-foo`, `audit-bar`, and bare
    # `report`) is the rule's admitted free-form form.
    return _KEBAB_STEM_RE.match(stem) is not None


def _check_spec_dir(suite: str, spec_dir: Path, findings: list[Finding]) -> None:
    """Validate a suite's ``_spec/`` directory closed vocabulary."""
    for child in sorted(spec_dir.iterdir(), key=lambda p: p.name):
        name = child.name
        if child.is_dir():
            if name not in _SPEC_ALLOWED_SUBDIRS:
                findings.append(
                    Finding(
                        suite=suite,
                        path=f"_spec/{name}/",
                        issue="non-vocab _spec subdirectory",
                        detail=(
                            f"_spec/ admits only the subdirectories "
                            f"{sorted(_SPEC_ALLOWED_SUBDIRS)}; {name!r} is "
                            "outside the closed vocabulary"
                        ),
                    )
                )
            continue
        # A file at the _spec/ root.
        if name in _INPUTS_CANONICAL_NAMES:
            findings.append(
                Finding(
                    suite=suite,
                    path=f"_spec/{name}",
                    issue="purpose-vocabulary contamination",
                    detail=(
                        f"{name!r} is an _inputs/ canonical-purpose name; the "
                        "purpose vocabularies are disjoint --- it must not live "
                        "in _spec/"
                    ),
                )
            )
        elif name != _SPEC_SINGLETON:
            findings.append(
                Finding(
                    suite=suite,
                    path=f"_spec/{name}",
                    issue="non-singleton _spec file",
                    detail=(
                        f"_spec/ holds only the singleton {_SPEC_SINGLETON!r} at "
                        f"its root; {name!r} is not the authoritative spec file"
                    ),
                )
            )


def _check_inputs_dir(suite: str, inputs_dir: Path, findings: list[Finding]) -> None:
    """Validate a suite's ``_inputs/`` directory for ``_spec/`` contamination.

    The only disjoint-vocabulary violation detectable inside ``_inputs/`` is a
    ``spec.md`` (the ``_spec/`` singleton) appearing here; everything else in
    ``_inputs/`` is admitted (canonical-purpose names OR free-form kebab topics).
    """
    spec_here = inputs_dir / _SPEC_SINGLETON
    if spec_here.is_file():
        findings.append(
            Finding(
                suite=suite,
                path=f"_inputs/{_SPEC_SINGLETON}",
                issue="purpose-vocabulary contamination",
                detail=(
                    f"{_SPEC_SINGLETON!r} is the _spec/ singleton; the purpose "
                    "vocabularies are disjoint --- it must not live in _inputs/. "
                    "Promote it to _spec/ per the forge->spec lifecycle"
                ),
            )
        )


def _check_outputs_dir(suite: str, outputs_dir: Path, findings: list[Finding]) -> None:
    """Validate a suite's ``_outputs/`` top-level filename purposes."""
    for child in sorted(outputs_dir.iterdir(), key=lambda p: p.name):
        if child.is_dir():
            # Sub-directory mirrors (e.g. `<phase-slug>/REPORT.md`) are allowed;
            # their names are kebab phase-slugs --- accept conservatively.
            continue
        stem = child.stem
        if not _outputs_filename_conformant(stem):
            findings.append(
                Finding(
                    suite=suite,
                    path=f"_outputs/{child.name}",
                    issue="non-vocab _outputs filename",
                    detail=(
                        f"_outputs/ filenames carry a closed purpose prefix "
                        f"{sorted(_OUTPUTS_PURPOSES)} (optionally date-stamped) "
                        "or a kebab-topic name; "
                        f"{child.name!r} matches neither"
                    ),
                )
            )


def _check_phases_dir(suite: str, phases_dir: Path, findings: list[Finding]) -> None:
    """Validate a suite's ``phases/`` numeric-prefix + PHASE.md discipline."""
    for child in sorted(phases_dir.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            # A stray file directly under phases/ is not a phase folder; the
            # phase apparatus expects only NN-topic directories here.
            findings.append(
                Finding(
                    suite=suite,
                    path=f"phases/{child.name}",
                    issue="non-directory under phases/",
                    detail=(
                        "phases/ contains only NN-topic phase folders; "
                        f"{child.name!r} is a stray file"
                    ),
                )
            )
            continue
        if _PHASE_DIR_RE.match(child.name) is None:
            findings.append(
                Finding(
                    suite=suite,
                    path=f"phases/{child.name}/",
                    issue="phase folder not NN-topic",
                    detail=(
                        f"every phases/ child folder must match NN-topic "
                        f"(e.g. 01-discovery); {child.name!r} does not"
                    ),
                )
            )
            continue
        # Phase coherence: every phase folder carries a PHASE.md.
        if not (child / "PHASE.md").is_file():
            findings.append(
                Finding(
                    suite=suite,
                    path=f"phases/{child.name}/PHASE.md",
                    issue="phase missing PHASE.md",
                    detail=(
                        f"phase folder {child.name!r} contains no PHASE.md; "
                        "every phase declares its scope/tasks/verification there"
                    ),
                )
            )
        # Sub-phase folders (directories inside a phase folder) must match
        # NNL-subtopic. Non-matching sub-directories are findings; files
        # (PHASE.md, REPORT.md, ...) are ignored.
        for sub in sorted(child.iterdir(), key=lambda p: p.name):
            if not sub.is_dir():
                continue
            if _SUBPHASE_DIR_RE.match(sub.name) is None:
                findings.append(
                    Finding(
                        suite=suite,
                        path=f"phases/{child.name}/{sub.name}/",
                        issue="sub-phase folder not NNL-subtopic",
                        detail=(
                            "every sub-phase folder must match NNL-subtopic "
                            f"(e.g. 02A-foo); {sub.name!r} does not"
                        ),
                    )
                )


def _check_root_numeric_prefixes(
    suite: str, suite_dir: Path, findings: list[Finding]
) -> None:
    """Flag decorative numeric prefixes on suite-root files.

    A suite-root ``NN-X.md`` file outside ``phases/`` carries a numeric prefix
    only when it is part of an ordered sequence --- i.e. an ``NN-X`` sibling
    exists sharing the same topic tail. A lone ``00-X.md`` with no ``01-X``
    sibling is a decorative prefix and a finding per the numeric-prefix
    discipline.
    """
    prefixed: list[tuple[Path, str]] = []
    for child in suite_dir.iterdir():
        if not child.is_file():
            continue
        match = _NUMERIC_PREFIX_FILE_RE.match(child.name)
        if match is not None:
            prefixed.append((child, match.group(2)))
    # Group by topic tail; a tail with a single member is a lone decorative
    # prefix. A known suite-root singleton that somehow carries a prefix is
    # always a finding (it should never be prefixed at all).
    tails: dict[str, int] = {}
    for _child, tail in prefixed:
        tails[tail] = tails.get(tail, 0) + 1
    for child, tail in prefixed:
        is_lone = tails[tail] < 2
        is_singleton = child.name in _SUITE_ROOT_SINGLETONS or any(
            child.name.endswith(s) for s in _SUITE_ROOT_SINGLETONS
        )
        if is_lone or is_singleton:
            findings.append(
                Finding(
                    suite=suite,
                    path=child.name,
                    issue="decorative numeric prefix on suite-root file",
                    detail=(
                        "numeric prefixes convey ordering and belong only on "
                        "phases/ folders with a sibling sequence; "
                        f"{child.name!r} is a suite-root singleton with no "
                        "ordered sibling, so the prefix is meaningless decoration"
                    ),
                )
            )


def _scan_nested_artifact_dirs(
    suite: str, suite_dir: Path, findings: list[Finding]
) -> None:
    """Flag ``_spec/`` / ``_inputs/`` / ``_outputs/`` nested below the suite root.

    The suite-locality invariant fixes these three directories as DIRECT
    children of the suite folder. An instance appearing deeper inside the suite
    (e.g. ``phases/NN-x/_spec/``) is a suite-locality violation.
    """
    for path in suite_dir.rglob("*"):
        if not path.is_dir():
            continue
        if path.name not in _ARTIFACT_CLASS_DIRS:
            continue
        # The direct-child instances are the canonical ones; skip them.
        if path.parent == suite_dir:
            continue
        rel = path.relative_to(suite_dir).as_posix()
        findings.append(
            Finding(
                suite=suite,
                path=f"{rel}/",
                issue="nested artifact-class directory",
                detail=(
                    f"{path.name}/ must be a DIRECT child of the suite folder; "
                    f"found nested at {rel}/ --- suite-locality violation"
                ),
            )
        )


def _check_suite(suite_dir: Path, findings: list[Finding]) -> None:
    """Validate a single ``<root>/.apothem/plans/<suite>/`` directory."""
    suite = suite_dir.name
    spec_dir = suite_dir / "_spec"
    inputs_dir = suite_dir / "_inputs"
    outputs_dir = suite_dir / "_outputs"
    phases_dir = suite_dir / "phases"
    if spec_dir.is_dir():
        _check_spec_dir(suite, spec_dir, findings)
    if inputs_dir.is_dir():
        _check_inputs_dir(suite, inputs_dir, findings)
    if outputs_dir.is_dir():
        _check_outputs_dir(suite, outputs_dir, findings)
    if phases_dir.is_dir():
        _check_phases_dir(suite, phases_dir, findings)
    _check_root_numeric_prefixes(suite, suite_dir, findings)
    _scan_nested_artifact_dirs(suite, suite_dir, findings)


def _check_plans_tree(plans_root: Path, label: str, findings: list[Finding]) -> int:
    """Validate every suite under a single canonical plans tree.

    *plans_root* is the sole canonical project-local plans location
    (``<root>/.apothem/plans``); *label* is the display-prefix used in
    root-level findings. Returns the number of suite folders inspected.
    """
    suite_count = 0
    if not plans_root.is_dir():
        return suite_count
    # Root-level suite-locality: the artifact-class directories must NOT
    # appear directly under the plans tree (only inside a suite folder).
    for entry in sorted(plans_root.iterdir(), key=lambda p: p.name):
        if entry.is_dir() and entry.name in _ARTIFACT_CLASS_DIRS:
            findings.append(
                Finding(
                    suite=f"<{label} root>",
                    path=f"{label}/{entry.name}/",
                    issue=f"artifact-class directory at {label} root",
                    detail=(
                        f"{entry.name}/ must live inside a suite folder, not "
                        f"directly under {label}/ --- suite-locality violation"
                    ),
                )
            )
    # Each remaining sub-directory of the plans tree is a suite folder.
    for suite_dir in sorted(plans_root.iterdir(), key=lambda p: p.name):
        if not suite_dir.is_dir():
            continue
        if suite_dir.name in _ARTIFACT_CLASS_DIRS:
            # Already flagged above as a root-level violation; not a suite.
            continue
        suite_count += 1
        _check_suite(suite_dir, findings)
    return suite_count


def check(root: Path) -> GrepResult:
    """Walk every suite under the canonical project-local plans tree.

    The sole canonical project-local plans location is ``<root>/.apothem/plans``
    (the shared Apothem working directory's plans child); a legacy
    ``<root>/.plans`` tree is no longer canonical — operators upgrade it via
    ``apothem migrate-workspace``. Suites under the canonical tree are validated,
    flagging structural violations.
    """
    findings: list[Finding] = []
    suite_count = 0
    suite_count += _check_plans_tree(
        root / ".apothem" / "plans", ".apothem/plans", findings
    )
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        suite_count=suite_count,
        passed=not findings,
        findings=findings,
    )


def _read_input(argv: list[str]) -> Path:
    if len(argv) >= 2:
        return Path(argv[1])
    return Path.cwd()


def _main(argv: list[str]) -> int:
    root = _read_input(argv)
    result = check(root)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
