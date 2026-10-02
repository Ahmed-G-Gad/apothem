# SPDX-License-Identifier: MIT

"""Ecosystem-wide structural and frontmatter validator for the apothem tree.

Checks performed:

* Required top-level directories exist.
* Required core files exist.
* Every artifact's frontmatter declares the canonical mandatory fields.
* Every ``version`` field matches semantic-version shape (``MAJOR.MINOR.PATCH``).
* Every ``updated`` field matches ISO 8601 date shape (``YYYY-MM-DD``).
* Every ``name`` field uses kebab-case (lowercase + digits + hyphens).
* Delegates hook-specific validation to :func:`validate_hooks.main`.

Exit codes: 0 when no FAIL outcomes occur, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Final

_HOOKS_LIB: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent / "src" / "apothem" / "hooks" / "lib"
)
if str(_HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(_HOOKS_LIB))

_LIB_DIR: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent / "src" / "apothem" / "lib"
)
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

_SRC_DIR: Final[Path] = Path(__file__).resolve().parent.parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from frontmatter import field_value, has_all_fields  # noqa: E402
from reporter import Reporter  # noqa: E402
from resolve_root import (  # noqa: E402
    Mode,
    default_content_root,
    resolve_project_root,
)

from apothem.conformity import binding_five_direction_grep  # noqa: E402

_CLAUDE_MD: Final[str] = "CLAUDE.md"

# The canonical plans home is ``<root>/.apothem/plans/``. A legacy
# ``<root>/.plans/`` tree predates the migration and is upgraded via
# ``apothem migrate-workspace``; it is honored as a fallback during the
# migration window so suite-scoped checks still resolve on an un-migrated
# workspace. Both trees are gitignored and absent from a fresh checkout.
_CANONICAL_PLANS_RELPATH: Final[tuple[str, ...]] = (".apothem", "plans")
_LEGACY_PLANS_RELPATH: Final[tuple[str, ...]] = (".plans",)


def _resolve_plans_dir(root: Path) -> Path:
    """Return the plans directory under *root*, canonical tree preferred.

    Prefers ``<root>/.apothem/plans/`` (the sole canonical home). Falls back to
    the legacy ``<root>/.plans/`` only when the canonical tree is absent and the
    legacy tree is present, so migrated and un-migrated workspaces both resolve.
    When neither exists the canonical path is returned (callers treat a missing
    directory as an empty, vacuously-passing plan tree).
    """
    canonical = root.joinpath(*_CANONICAL_PLANS_RELPATH)
    if canonical.is_dir():
        return canonical
    legacy = root.joinpath(*_LEGACY_PLANS_RELPATH)
    if legacy.is_dir():
        return legacy
    return canonical


_REQUIRED_DIRS: Final[tuple[str, ...]] = (
    "rules",
    "commands",
    "agents",
    "skills",
    "hooks",
)
# Repo-infrastructure directories live at the repository root, not under the
# content root (``src/apothem`` when validating the apothem source repo).
_REQUIRED_ROOT_DIRS: Final[tuple[str, ...]] = (
    "site",
    "scripts",
)

_REQUIRED_FILES: Final[tuple[str, ...]] = (
    _CLAUDE_MD,
    "README.md",
    "CHANGELOG.md",
    "examples/harnesses/claude-code/native-install/settings.json",
    ".markdownlint.json",
    "site/content/docs/reference/settings-reference.mdx",
)

_RULE_FIELDS: Final[list[str]] = [
    "name",
    "description",
    "pathFilter",
    "alwaysApply",
]
_COMMAND_FIELDS: Final[list[str]] = [
    "name",
    "version",
    "updated",
    "description",
    "argument-hint",
    "disable-model-invocation",
]
_AGENT_FIELDS: Final[list[str]] = [
    "name",
    "version",
    "updated",
    "description",
    "tools",
    "disallowedTools",
    "maxTurns",
    "effort",
]
_SKILL_FIELDS: Final[list[str]] = [
    "name",
    "description",
    "archetype",
    "userInvocable",
]
_CLAUDEMD_FIELDS: Final[list[str]] = [
    "name",
    "version",
    "updated",
    "description",
    "scope",
    "portability",
]

_SEMVER_SHAPE: Final[re.Pattern[str]] = re.compile(
    r"^\d+\.\d+\.\d+(?:-[A-Za-z0-9.\-]+)?(?:\+[A-Za-z0-9.\-]+)?$"
)
_ISO_DATE_SHAPE: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_KEBAB_SHAPE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_AUTHORITY_HOMEPATH_SHAPE: Final[re.Pattern[str]] = re.compile(
    r"(?:[Cc]:[\\/]|/c/|/)Users/(?P<owner>[A-Za-z0-9._-]+)(?:[\\/]\.claude\b|/\.claude\b)"
)
_AUTHORITY_SLUG_SHAPE: Final[re.Pattern[str]] = re.compile(
    r"\bc--users-(?P<owner>[a-z0-9-]+)--claude\b"
)
_AUTHORITY_FIXTURE_OWNERS: Final[frozenset[str]] = frozenset(
    {"test-user", "test-fixture", "alice", "bob", "user", "username", "example"}
)
_AUTHORITY_SCOPE_DIRS: Final[tuple[str, ...]] = (
    "rules",
    "commands",
    "agents",
    "skills",
    "hooks",
    "scripts",
    "tests",
    "docs",
)
_AUTHORITY_ROOT_FILES: Final[tuple[str, ...]] = (
    "CLAUDE.md",
    "examples/harnesses/claude-code/native-install/settings.json",
    "README.md",
    "CHANGELOG.md",
    ".gitignore",
    ".markdownlint.json",
)
_AUTHORITY_TEXT_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".py", ".sh", ".ps1", ".json", ".md", ".toml", ".yaml", ".yml", ".cfg", ".ini"}
)


def validate_directories(content_root: Path, root: Path, reporter: Reporter) -> None:
    """Assert required directories exist.

    Content directories (``rules``, ``commands``, ``agents``, ``skills``,
    ``hooks``) are resolved under ``content_root``; repo-infrastructure
    directories (``docs``, ``scripts``) are resolved under the repository
    ``root``.
    """
    for name in _REQUIRED_DIRS:
        if (content_root / name).is_dir():
            reporter.ok(f"Directory exists: {name}")
        else:
            reporter.fail(f"Missing directory: {name}")
    for name in _REQUIRED_ROOT_DIRS:
        if (root / name).is_dir():
            reporter.ok(f"Directory exists: {name}")
        else:
            reporter.fail(f"Missing directory: {name}")


def validate_core_files(root: Path, reporter: Reporter) -> None:
    """Assert every required core file exists under ``root``."""
    for rel in _REQUIRED_FILES:
        if (root / rel).is_file():
            reporter.ok(f"File exists: {rel}")
        else:
            reporter.fail(f"Missing file: {rel}")


def _check_value_shape(
    path: Path,
    rel: Path,
    field: str,
    pattern: re.Pattern[str],
    shape_label: str,
    label: str,
    reporter: Reporter,
    skip_kebab_for: str | None = None,
) -> None:
    """Validate that ``path``'s ``field`` value matches ``pattern``.

    ``skip_kebab_for`` lets callers exempt a known non-conforming name
    (CLAUDE.md uses ``"CLAUDE"`` rather than kebab-case).
    """
    value = field_value(path, field)
    if value is None:
        return
    if skip_kebab_for is not None and value == skip_kebab_for:
        return
    if pattern.match(value):
        return
    reporter.fail(f"{label} {field} not {shape_label}: {rel} -> {value!r}")


def validate_frontmatter(
    files: list[Path],
    required_fields: list[str],
    label: str,
    root: Path,
    reporter: Reporter,
    *,
    name_exempt: str | None = None,
) -> None:
    """Verify each file declares the required fields with valid values.

    Presence is checked for every required field; in addition, the universal
    fields ``version``, ``updated``, and ``name`` (when present) are checked
    for semver / ISO 8601 / kebab-case shape respectively.
    """
    for path in files:
        rel = path.relative_to(root)
        if not has_all_fields(path, required_fields):
            reporter.fail(f"{label} frontmatter incomplete: {rel}")
            continue
        reporter.ok(f"{label} frontmatter present: {rel}")
        _check_value_shape(
            path,
            rel,
            "version",
            _SEMVER_SHAPE,
            "semver",
            label,
            reporter,
        )
        _check_value_shape(
            path,
            rel,
            "updated",
            _ISO_DATE_SHAPE,
            "ISO 8601 date",
            label,
            reporter,
        )
        _check_value_shape(
            path,
            rel,
            "name",
            _KEBAB_SHAPE,
            "kebab-case",
            label,
            reporter,
            skip_kebab_for=name_exempt,
        )


def validate_rule_bind(files: list[Path], root: Path, reporter: Reporter) -> None:
    """Verify the bidirectional bind alwaysApply IFF pathFilter is empty."""
    for path in files:
        rel = path.relative_to(root)
        path_filter = field_value(path, "pathFilter")
        always_apply = field_value(path, "alwaysApply")
        if path_filter is None or always_apply is None:
            continue
        stripped = path_filter.strip()
        is_empty = stripped == "" or stripped in {'""', "''"}
        is_always = always_apply.strip().lower() == "true"
        if is_empty == is_always:
            reporter.ok(f"Rule bind holds: {rel}")
        else:
            reporter.fail(
                f"Rule bind violated: {rel} -> pathFilter empty={is_empty}, "
                f"alwaysApply={is_always}"
            )


_REGISTRY_PREFIXES: Final[tuple[str, ...]] = (
    "src/apothem/rules/",
    "src/apothem/commands/",
    "src/apothem/agents/",
    "src/apothem/skills/",
    "src/apothem/hooks/",
    "scripts/",
    "memory/",
    "site/content/docs/",
)


def validate_registries(root: Path, reporter: Reporter) -> None:
    """Walk Markdown link targets in CLAUDE.md and verify each exists.

    Targets a small subset of paths under canonical artifact directories so the
    sweep stays focused on the registry-vs-disk parity invariant. Anchor-only
    references (``#anchor``), absolute URLs, and external-host references are
    skipped.
    """
    claude_md = root / _CLAUDE_MD
    if not claude_md.is_file():
        reporter.fail("CLAUDE.md missing: cannot run registry sweep")
        return
    text = claude_md.read_text(encoding="utf-8")
    backtick_pattern = re.compile(r"`([A-Za-z][A-Za-z0-9._/-]+\.[A-Za-z]+)`")
    seen: set[str] = set()
    for match in backtick_pattern.finditer(text):
        candidate = match.group(1)
        if candidate in seen:
            continue
        seen.add(candidate)
        if "://" in candidate or candidate.startswith("#"):
            continue
        if not candidate.startswith(_REGISTRY_PREFIXES):
            continue
        target = root / candidate
        if target.exists():
            reporter.ok(f"Registry target exists: {candidate}")
        else:
            reporter.fail(f"Registry target missing: {candidate}")


def _iter_authority_scope_files(root: Path) -> list[Path]:
    """Enumerate text files under the authority-hygiene sweep scope.

    Scope is the ecosystem-authored core surface: the eight scope directories
    plus the seven root-level files. Excludes plan suites, per-project memory,
    third-party plugins, and runtime caches by virtue of the closed scope set.
    """
    files: list[Path] = []
    for directory in _AUTHORITY_SCOPE_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in _AUTHORITY_TEXT_SUFFIXES:
                continue
            if "__pycache__" in path.parts or ".mypy_cache" in path.parts:
                continue
            files.append(path)
    for name in _AUTHORITY_ROOT_FILES:
        candidate = root / name
        if candidate.is_file():
            files.append(candidate)
    return sorted(files)


def validate_authority_hygiene(root: Path, reporter: Reporter) -> None:
    """Sweep ecosystem-core for fabrication-suspect identity-bearing literals.

    Detects two pattern classes: hardcoded user-home paths
    (``C:/Users/<name>/.claude`` and POSIX equivalents) and identity slugs
    (``c--users-<name>--claude``). Owners listed in the fixture allowlist
    (``test-user``, ``alice``, ``bob``, ``example``, etc.) are exempt because
    they declare themselves as test fixtures, not personal data.
    """
    files = _iter_authority_scope_files(root)
    hits = 0
    for path in files:
        rel = path.relative_to(root)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in _AUTHORITY_HOMEPATH_SHAPE.finditer(line):
                owner = match.group("owner").lower()
                if owner in _AUTHORITY_FIXTURE_OWNERS:
                    continue
                hits += 1
                reporter.fail(
                    f"Hardcoded identity path: {rel}:{line_no} owner={owner!r}"
                )
            for match in _AUTHORITY_SLUG_SHAPE.finditer(line):
                owner = match.group("owner")
                if owner in _AUTHORITY_FIXTURE_OWNERS:
                    continue
                hits += 1
                reporter.fail(
                    f"Hardcoded identity slug: {rel}:{line_no} owner={owner!r}"
                )
    if hits == 0:
        reporter.ok(f"Authority hygiene clean across {len(files)} files")


_SEVEN_AXES: Final[tuple[str, ...]] = (
    "Architecture",
    "Concurrency",
    "Performance",
    "Security",
    "Testing",
    "Tooling",
    "Observability",
)


def validate_expertise_coverage(root: Path, reporter: Reporter) -> None:
    """Verify the seven-axs-of-breadth taxonomy is declared and tracked.

    The cognitive-identity rule MUST declare the seven canonical axs in §1; the
    `memory/expertise-gap-log.md` tracker is optional (the memory tier is
    user-specific and may be absent in fresh checkouts), but when present it
    MUST also enumerate every axis.
    """
    rule = root / "rules" / "cognitive-identity.md"
    if not rule.is_file():
        reporter.fail("cognitive-identity rule missing")
        return
    rule_text = rule.read_text(encoding="utf-8")
    missing_in_rule = [axis for axis in _SEVEN_AXES if axis not in rule_text]
    if missing_in_rule:
        reporter.fail(
            "cognitive-identity §1 missing axs: " + ", ".join(missing_in_rule)
        )
    else:
        reporter.ok("cognitive-identity declares all seven expertise axs")

    log = root / "memory" / "expertise-gap-log.md"
    if not log.is_file():
        reporter.ok("expertise-gap-log absent (memory tier is user-specific)")
        return
    log_text = log.read_text(encoding="utf-8")
    missing_in_log = [axis for axis in _SEVEN_AXES if axis not in log_text]
    if missing_in_log:
        reporter.fail("expertise-gap-log missing axs: " + ", ".join(missing_in_log))
    else:
        reporter.ok("expertise-gap-log enumerates all seven expertise axs")


_BENCH_ENTRY_POINTS: Final[tuple[str, ...]] = (
    "bench_hooks.py",
    "bench_validate_ecosystem.py",
    "bench_tests.py",
    "bench_agents.py",
)


def validate_perf_budgets(root: Path, reporter: Reporter) -> None:
    """Verify the performance-discipline rule and benchmark scaffold are in place."""
    rule = root / "rules" / "performance-discipline.md"
    if not rule.is_file():
        reporter.fail("performance-discipline rule missing")
    else:
        rule_text = rule.read_text(encoding="utf-8")
        if "Per-Class Performance Budgets" not in rule_text:
            reporter.fail(
                "performance-discipline rule missing Per-Class budget section"
            )
        else:
            reporter.ok("performance-discipline rule declares per-class budgets")
        if "Shell-Execution Sub-Budgets" not in rule_text:
            reporter.fail(
                "performance-discipline rule missing Shell-Execution Sub-Budgets section"
            )
        else:
            reporter.ok(
                "performance-discipline rule declares shell-execution sub-budgets"
            )

    bench_dir = root / "benchmarks"
    if not bench_dir.is_dir():
        reporter.fail(f"{bench_dir} directory missing")
        return
    missing_scripts = [
        name for name in _BENCH_ENTRY_POINTS if not (bench_dir / name).is_file()
    ]
    if missing_scripts:
        reporter.fail(
            "src/apothem/benchmarks/ missing scripts: " + ", ".join(missing_scripts)
        )
    else:
        reporter.ok(
            f"src/apothem/benchmarks/ carries {len(_BENCH_ENTRY_POINTS)} entry-point scripts"
        )


_CODE_CRAFT_PYTHON_GLOBS: Final[tuple[str, ...]] = (
    "src/apothem/hooks/*.py",
    "src/apothem/hooks/lib/*.py",
    "scripts/dev/*.py",
    "src/apothem/lib/*.py",
    "src/apothem/benchmarks/*.py",
)
_CODE_CRAFT_SHELL_GLOBS: Final[tuple[str, ...]] = ("src/apothem/hooks/lib/*.sh",)
_CODE_CRAFT_PWSH_GLOBS: Final[tuple[str, ...]] = ("src/apothem/hooks/lib/*.ps1",)
_CODE_CRAFT_SHELL_HEADER_TOKENS: Final[tuple[str, ...]] = (
    "Purpose:",
    "Contract:",
    "Sibling files in",
)
_CODE_CRAFT_BARE_EXCEPT_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^\s*except\s*:\s*$"),
    re.compile(r"^\s*except\s+Exception\s*:\s*(?:#.*)?$"),
)
_CODE_CRAFT_BOUNDARY_MARKERS: Final[tuple[str, ...]] = (
    "noqa: BLE001",
    "code-craft-boundary: broad-except",
)


def _glob_many(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    """Return the unique, sorted union of files matched by ``patterns`` under ``root``."""
    seen: set[Path] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file():
                seen.add(path)
    return sorted(seen)


def _python_has_silent_swallow(path: Path) -> tuple[bool, int]:
    """Return ``(has_violation, line_number)`` for a silent-exception swallow.

    A bare ``except:`` is always a violation. A bare ``except Exception:`` is
    permitted only at an outermost boundary marked with an approved broad-except
    comment, since the surrounding handlers there route uncaught exceptions
    through a structured failure envelope rather than silently dropping them.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False, 0
    for index, line in enumerate(text.splitlines(), start=1):
        for pattern in _CODE_CRAFT_BARE_EXCEPT_PATTERNS:
            if pattern.match(line) and not any(
                marker in line for marker in _CODE_CRAFT_BOUNDARY_MARKERS
            ):
                return True, index
    return False, 0


def validate_code_craft(root: Path, reporter: Reporter) -> None:
    """Verify the code-craft enforcement surface is in place across the code tree.

    Three concurrent assertions:

    * ``.shellcheckrc`` exists at the ecosystem root and the ``[tool.ruff]``
      block in ``pyproject.toml`` declares the project-wide style ratification.
    * Every shell wrapper under ``src/apothem/hooks/lib/`` carries the purpose / contract /
      sibling-files header tokens at file head.
    * No Python artifact swallows exceptions silently — a bare ``except:`` or
      a bare ``except Exception:`` without the outermost-boundary marker is a
      hard fail.
    """
    shellcheck_rc = root / ".shellcheckrc"
    if shellcheck_rc.is_file():
        reporter.ok(".shellcheckrc present at ecosystem root")
    else:
        reporter.fail(".shellcheckrc missing at ecosystem root")

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8")
        if "[tool.ruff]" in text:
            reporter.ok("pyproject.toml carries [tool.ruff] section")
        else:
            reporter.fail("pyproject.toml missing [tool.ruff] section")
    else:
        reporter.fail("pyproject.toml missing at ecosystem root")

    shell_artifacts = _glob_many(root, _CODE_CRAFT_SHELL_GLOBS + _CODE_CRAFT_PWSH_GLOBS)
    missing_headers: list[str] = []
    for path in shell_artifacts:
        try:
            head = path.read_text(encoding="utf-8").splitlines()[:30]
        except OSError:
            continue
        head_text = "\n".join(head)
        if not all(token in head_text for token in _CODE_CRAFT_SHELL_HEADER_TOKENS):
            missing_headers.append(str(path.relative_to(root)))
    if missing_headers:
        reporter.fail(
            "Shell wrappers missing purpose/contract/sibling-files header: "
            + ", ".join(missing_headers)
        )
    else:
        reporter.ok(
            f"Shell wrappers carry purpose/contract/sibling header: "
            f"{len(shell_artifacts)} files clean"
        )

    python_artifacts = _glob_many(root, _CODE_CRAFT_PYTHON_GLOBS)
    swallow_findings: list[str] = []
    for path in python_artifacts:
        violated, line_no = _python_has_silent_swallow(path)
        if violated:
            swallow_findings.append(f"{path.relative_to(root)}:{line_no}")
    if swallow_findings:
        reporter.fail(
            "Python artifacts with silent exception swallow: "
            + ", ".join(swallow_findings)
        )
    else:
        reporter.ok(
            f"Python artifacts free of silent exception swallow: "
            f"{len(python_artifacts)} files clean"
        )


def validate_self_application(root: Path, reporter: Reporter) -> None:
    """Verify any plan-suite present honors the suite-locality invariant.

    The plan-suite tier is gitignored and may be absent in a fresh checkout. When
    absent, the gate is vacuously PASS. When present, every suite under the plans
    tree (canonical ``.apothem/plans/``, legacy ``.plans/`` as a migration-window
    fallback) MUST carry at least one of the two canonical artifact directories
    (``_inputs/`` for in-flight elicitation, ``_spec/`` for the authoritative
    spec). Either state is admissible — the forge→spec promotion arc allows a
    suite to live in ``_inputs/forge.md`` until promotion to ``_spec/spec.md``.
    """
    plans_dir = _resolve_plans_dir(root)
    if not plans_dir.is_dir():
        reporter.ok("self-application vacuously passes (no plan tree present)")
        return
    suite_dirs = [
        p for p in plans_dir.iterdir() if p.is_dir() and not p.name.startswith("_")
    ]
    if not suite_dirs:
        reporter.ok("self-application vacuously passes (no suites in plan tree)")
        return
    malformed: list[str] = []
    for suite in sorted(suite_dirs):
        has_inputs = (suite / "_inputs").is_dir()
        has_prose = (suite / "_prose").is_dir()
        if not (has_inputs or has_prose):
            malformed.append(suite.name)
    if malformed:
        reporter.fail(
            "suites missing both _inputs/ and _spec/: " + ", ".join(malformed)
        )
    else:
        reporter.ok(f"self-application clean across {len(suite_dirs)} suite(s)")


_OPTION_ANNOTATION_SCOPE_DIRS: Final[tuple[str, ...]] = (
    "commands",
    "rules",
    "skills",
    "agents",
    "hooks",
)
_OPTION_ANNOTATION_ROOT_FILES: Final[tuple[str, ...]] = ("CLAUDE.md",)
_OPTION_ANNOTATION_EXCLUDED: Final[frozenset[str]] = frozenset(
    {
        "src/apothem/rules/interactive-questions.md",
        "src/apothem/rules/interactive-questions-sweep-matchers.md",
        "src/apothem/rules/operational-mandates.md",
        "src/apothem/skills/plan-suite/master-template.md",
        "src/apothem/skills/ecosystem-audit/SKILL.md",
    }
)
_INVOCATION_HEAD_SHAPE: Final[re.Pattern[str]] = re.compile(
    r"structured[- ]inquiry\s*:\s*question\s*`"
)
_OPTION_LABEL_SHAPE: Final[re.Pattern[str]] = re.compile(
    r"^\s*>?\s*-\s*`(?P<label>[^`]+)`\s*:"
)
_RECOMMENDATION_VALUE_SHAPE: Final[re.Pattern[str]] = re.compile(
    r"recommendation:\s*(?P<value>recommended|acceptable|discouraged|destructive-no-default)"
)
_NO_DEFAULT_FLOOR_LITERAL: Final[str] = "no-default: user decision required"
# Canonical postfix is capital `(Recommended)` per
# `rules/interactive-questions-canonical-shapes.md` §2.1; the lowercase form is
# the banned variant and is itself an H6 finding.
_CANONICAL_POSTFIX_LITERAL: Final[str] = "(Recommended)"
_LOWERCASE_POSTFIX_LITERAL: Final[str] = "(recommended)"


def _iter_option_annotation_files(root: Path) -> list[Path]:
    """Enumerate files under the option-annotation sweep scope."""
    files: list[Path] = []
    for directory in _OPTION_ANNOTATION_SCOPE_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*.md"):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    for name in _OPTION_ANNOTATION_ROOT_FILES:
        candidate = root / name
        if candidate.is_file():
            files.append(candidate)
    return sorted(files)


def _extract_invocation_block(lines: list[str], start: int) -> tuple[int, list[str]]:
    """Extract a structured-inquiry invocation block starting at ``start``.

    The block ends at the first line containing the literal ``multiSelect:``
    terminator within a 40-line look-ahead window, or at the window boundary
    when the terminator is absent.
    """
    block: list[str] = [lines[start]]
    end = start
    for offset in range(1, 40):
        idx = start + offset
        if idx >= len(lines):
            break
        block.append(lines[idx])
        end = idx
        if "multiSelect:" in lines[idx]:
            break
    return end, block


def validate_option_annotation(root: Path, reporter: Reporter) -> None:
    """Sweep structured-inquiry invocations for option-annotation discipline.

    Implements heuristics H4 (body-segment omission), H6 (label-postfix
    bidirectional bind), and H7 (destructive-op no-default floor) declared at
    ``src/apothem/rules/interactive-questions-sweep-matchers.md`` §1. The §3
    exclusion zones are honored: the canonical-channel rule, its companion
    sub-rule, the operational-mandates rule, and the two ratified skill
    surfaces are skipped because their structured-inquiry citations are
    definitional self-citations rather than live invocations.
    """
    files = _iter_option_annotation_files(root)
    h4_hits: list[str] = []
    h6_hits: list[str] = []
    h7_hits: list[str] = []
    swept = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        if rel in _OPTION_ANNOTATION_EXCLUDED:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        swept += 1
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            if not _INVOCATION_HEAD_SHAPE.search(lines[i]):
                i += 1
                continue
            end_idx, block = _extract_invocation_block(lines, i)
            block_text = "\n".join(block)
            location = f"{rel}:{i + 1}"

            has_rationale = "rationale:" in block_text
            has_recommendation = "recommendation:" in block_text
            has_default_pointer = "default-pointer:" in block_text
            if not (has_rationale and has_recommendation and has_default_pointer):
                h4_hits.append(location)

            multi_select = any(
                re.search(r"multiSelect:\s*true\b", blk_line) for blk_line in block
            )
            # Pair each option label with the first recommendation value in its
            # body so the bind is checked per option, not by file-wide count.
            options: list[list[str | None]] = []
            for blk_line in block:
                label_match = _OPTION_LABEL_SHAPE.match(blk_line)
                if label_match:
                    options.append([label_match.group("label"), None])
                    continue
                if options and options[-1][1] is None:
                    rec_match = _RECOMMENDATION_VALUE_SHAPE.search(blk_line)
                    if rec_match:
                        options[-1][1] = rec_match.group("value")
            recommended_count = 0
            bind_violation = False
            for label, value in options:
                if label is None:
                    continue
                is_recommended = value == "recommended"
                if is_recommended:
                    recommended_count += 1
                has_canonical = label.endswith(_CANONICAL_POSTFIX_LITERAL)
                has_lowercase = label.endswith(_LOWERCASE_POSTFIX_LITERAL)
                if has_lowercase:
                    bind_violation = True  # banned non-canonical case
                elif is_recommended and not has_canonical:
                    bind_violation = True  # body→label: missing canonical postfix
                elif has_canonical and not is_recommended:
                    bind_violation = True  # label→body: spurious postfix
            if bind_violation or (not multi_select and recommended_count > 1):
                h6_hits.append(location)

            if "destructive-no-default" in block_text:
                for blk_line in block:
                    if (
                        "default-pointer:" in blk_line
                        and _NO_DEFAULT_FLOOR_LITERAL not in blk_line
                    ):
                        h7_hits.append(location)
                        break

            i = end_idx + 1

    total = len(h4_hits) + len(h6_hits) + len(h7_hits)
    if total == 0:
        reporter.ok(f"Option annotation clean across {swept} files")
        return
    reporter.fail(
        f"Option annotation: H4={len(h4_hits)} H6={len(h6_hits)} H7={len(h7_hits)} hits"
    )
    for hit in h4_hits[:5]:
        reporter.fail(f"  H4 (missing body segments): {hit}")
    for hit in h6_hits[:5]:
        reporter.fail(f"  H6 (label-postfix mismatch): {hit}")
    for hit in h7_hits[:5]:
        reporter.fail(f"  H7 (destructive-op no-default floor): {hit}")


_UDA_SCOPE_DIRS: Final[tuple[str, ...]] = (
    "commands",
    "rules",
    "skills",
    "agents",
    "src/apothem/hooks/messages",
    "docs",
)
_UDA_ROOT_FILES: Final[tuple[str, ...]] = ("CLAUDE.md",)
_UDA_HEDGE_LEXICON: Final[re.Pattern[str]] = re.compile(
    r"\b(maybe|might|could|should probably|usually|"
    r"generally speaking|in most cases|mostly|typically|often|"
    r"or similar|etc\.|and so on)\b",
    re.IGNORECASE,
)
_UDA_FENCE_MARKER: Final[re.Pattern[str]] = re.compile(r"^\s*```")
_UDA_FRONTMATTER_MARKER: Final[str] = "---"
# Definitional self-citation markers — when these phrases appear on a
# scanned line, the surrounding sentence is the rule-body itself
# describing the forbidden vocabulary. The hedge tokens cited there are
# the rule's subject matter, not authored hedging, and are exempt.
_UDA_DEFINITIONAL_MARKERS: Final[tuple[str, ...]] = (
    "forbidden phrase",
    "forbid list",
    "hedging vocabulary",
    "hedging-vocabulary",
    "hedge words",
    "hedge tokens",
    "hedge token",
    "hedge lexicon",
)

_UDA_LINE_ALLOWLIST: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        # Counterfactual conditional: "could produce" describes the logical
        # corollary of the clean-room invariant, not a hedge.
        (
            "src/apothem/rules/clean-room-generation.md",
            "could produce substantially the same output",
        ),
        # Possibility-conditioned guard: parallel writes "might conflict" names
        # the contingent state the worktree isolation prevents.
        (
            "src/apothem/rules/agent-orchestration.md",
            "make independent changes to the same codebase that might conflict",
        ),
        # Conditional possibility: the parallel-eligibility predicate.
        (
            "src/apothem/rules/agent-orchestration.md",
            "launch agents sequentially when they could run in parallel",
        ),
        # Instructional thought-experiment: cognitive principle prescribes
        # imagining failure as design input.
        (
            "src/apothem/rules/cognitive-identity.md",
            "Imagine how the idea could fail",
        ),
        # Counterfactual: "could not determine" is the gap-reporting predicate.
        (
            "src/apothem/agents/codebase-explorer.md",
            "Anything you could not determine",
        ),
        # Worked-example scenario: tooling components admissible at release.
        (
            "src/apothem/rules/interactive-questions.md",
            "tooling components that could ship with the next release",
        ),
        # Instructional thought-experiment: Inversion Press filter.
        (
            "src/apothem/skills/plan-suite/master-template.md",
            "which could be completely wrong",
        ),
        # Instructional thought-experiment: Failure Is A Design Material.
        (
            "src/apothem/skills/plan-suite/master-template.md",
            "imagine how the idea could fail",
        ),
        # Heuristic interrogative: skill-vs-command classification predicate.
        (
            "site/content/docs/developer-guide.mdx",
            "Could it timeout or require user input mid-execution",
        ),
        # Self-citation of matcher-defining rule body — analogous to the
        # src/apothem/rules/interactive-questions-sweep-matchers.md §3
        # self-citation-exemption pattern. The rule body that DEFINES the
        # closed hedging vocabulary necessarily enumerates it inline; the
        # surrounding sentence is the rule's pedagogical content, not a
        # binding prescription that hedges. Rewriting would corrupt the
        # rule's clarity by forcing readers to consult two sources.
        (
            "src/apothem/rules/definitiveness.md",
            "Closed list, detected and eliminated when binding prescription",
        ),
    }
)


def _iter_uda_scope_files(root: Path) -> list[Path]:
    """Enumerate Markdown files under the UDA airtightness sweep scope."""
    files: list[Path] = []
    for directory in _UDA_SCOPE_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*.md"):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    for name in _UDA_ROOT_FILES:
        candidate = root / name
        if candidate.is_file():
            files.append(candidate)
    return sorted(files)


def _uda_line_is_definitional(line: str) -> bool:
    """Return True when ``line`` is a definitional hedge-token self-citation.

    Definitional contexts retain hedge tokens because the surrounding sentence
    is quoting the token to define, forbid, or anti-pattern it. The five
    detected shapes:

    1. The hedge token appears inside backticks (`` `usually` ``).
    2. The hedge token appears inside double quotes (``"usually"``).
    3. The line is a DON'T anti-pattern bullet.
    4. The line cites a forbidden-phrase or vague-rationale list.
    5. The line is a labeled hedge-classification example (``|`` table column).
    """
    if "DON'T" in line:
        return True
    lowered = line.lower()
    if any(marker in lowered for marker in _UDA_DEFINITIONAL_MARKERS):
        return True
    for match in _UDA_HEDGE_LEXICON.finditer(line):
        token_start = match.start()
        token_end = match.end()
        prefix = line[:token_start]
        suffix = line[token_end:]
        backticks_before = prefix.count("`")
        backticks_after = suffix.count("`")
        if backticks_before % 2 == 1 and backticks_after % 2 == 1:
            continue
        quotes_before = prefix.count('"')
        quotes_after = suffix.count('"')
        if quotes_before % 2 == 1 and quotes_after % 2 == 1:
            continue
        return False
    return True


def validate_uda_airtightness(root: Path, reporter: Reporter) -> None:
    """Sweep the governed-core tree for §0.h forbidden hedges.

    The sweep flags every line that contains a hedge-lexicon match outside
    declared exclusion zones: fenced code blocks, YAML frontmatter, quoted
    hedge-token contexts, DON'T anti-pattern bullets, forbidden-phrase lists,
    and the per-line allowlist for counterfactual-conditional and
    instructional-thought-experiment usages. A clean sweep returns PASS.
    """
    files = _iter_uda_scope_files(root)
    hits: list[str] = []
    swept = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        swept += 1
        in_fence = False
        in_frontmatter = False
        frontmatter_seen = False
        for line_no, line in enumerate(text.splitlines(), start=1):
            if line.strip() == _UDA_FRONTMATTER_MARKER:
                if line_no == 1:
                    in_frontmatter = True
                    frontmatter_seen = True
                    continue
                if in_frontmatter:
                    in_frontmatter = False
                    continue
                if not frontmatter_seen:
                    frontmatter_seen = True
            if in_frontmatter:
                continue
            if _UDA_FENCE_MARKER.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if not _UDA_HEDGE_LEXICON.search(line):
                continue
            if _uda_line_is_definitional(line):
                continue
            allowlisted = False
            for allowed_path, allowed_substr in _UDA_LINE_ALLOWLIST:
                if rel == allowed_path and allowed_substr in line:
                    allowlisted = True
                    break
            if allowlisted:
                continue
            hits.append(f"{rel}:{line_no}")
    if not hits:
        reporter.ok(f"UDA airtightness clean across {swept} files")
        return
    reporter.fail(f"UDA airtightness: {len(hits)} hits")
    for hit in hits[:10]:
        reporter.fail(f"  hedge in binding prescription: {hit}")


def validate_binding_five_direction(root: Path, reporter: Reporter) -> None:
    """Sweep the content strata for the five-direction Bindings section.

    Every rule, command, agent, and skill MUST close with a ``## Bindings``
    section carrying Drives, Satisfies, Established by, Gated by, and
    Cross-bound with; hook-message contexts carry the Drives, Established by,
    and Cross-bound subset. ``root`` is the content root (``src/apothem`` in
    the repository) or a project root above it. The walk is the conformity
    gate's ``binding-five-direction-grep``, so the developer check and the
    gate cannot disagree. A root holding no artifact to inspect is a failure,
    never a clean pass across zero files.
    """
    result = binding_five_direction_grep.check(root)
    if result.inspected == 0:
        reporter.fail(
            "Binding five-direction: no rule, command, agent, skill, or hook "
            f"message found under {root}"
        )
        return
    for finding in result.findings:
        if finding.detail.startswith("no ## Bindings"):
            reporter.fail(f"Missing Bindings section: {finding.path}")
        else:
            reporter.fail(
                f"Missing directions in {finding.path}: {', '.join(finding.missing)}"
            )
    if result.passed:
        reporter.ok(f"Binding five-direction clean across {result.inspected} files")


_PHASE_ROLLUP_FOLDER_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\d{2}-")


def _iter_phase_folders(root: Path, suite_name: str | None = None) -> list[Path]:
    """Return every phase folder under every plan suite below the plans tree.

    A phase folder is a direct child of ``{plans}/{suite}/phases/`` whose name
    matches the canonical ``NN-kebab-topic`` shape, where ``{plans}`` is the
    canonical ``.apothem/plans/`` tree (legacy ``.plans/`` as a migration-window
    fallback). Suites without a ``phases`` directory are skipped silently — only
    initialised suites contribute. When ``suite_name`` is given, only that
    suite's phase folders are returned; otherwise every suite is swept.
    """
    plans_dir = _resolve_plans_dir(root)
    if not plans_dir.is_dir():
        return []
    folders: list[Path] = []
    if suite_name is not None:
        suites = [plans_dir / suite_name] if (plans_dir / suite_name).is_dir() else []
    else:
        suites = sorted(plans_dir.iterdir())
    for suite in suites:
        phases_dir = suite / "phases"
        if not phases_dir.is_dir():
            continue
        for phase_folder in sorted(phases_dir.iterdir()):
            if phase_folder.is_dir() and _PHASE_ROLLUP_FOLDER_PATTERN.match(
                phase_folder.name
            ):
                folders.append(phase_folder)
    return folders


def _phase_has_sub_phase_content(phase_folder: Path) -> bool:
    """Return True when the phase folder carries any descendant artifact beyond ``PHASE.md``.

    A phase folder with only ``PHASE.md`` (and no sub-phase folders or aggregate
    files) marks a wave that has not yet entered execution. The verifier exempts
    such folders from the rollup-presence requirement under the forward-resolvable
    convention declared at the §0.l two-tier reporting discipline.
    """
    for child in phase_folder.iterdir():
        if child.name == "PHASE.md":
            continue
        if child.is_file() and child.suffix == ".md":
            return True
        if child.is_dir():
            for descendant in child.rglob("*.md"):
                if descendant.is_file():
                    return True
    return False


def validate_phase_rollup_completeness(
    root: Path,
    reporter: Reporter,
    suite_name: str | None = None,
) -> None:
    """Sweep every plan-suite phase folder for the rollup ``REPORT.md`` artifact.

    The §0.l two-tier reporting discipline requires every closed phase to carry
    a phase-level rollup ``REPORT.md`` at its root, alongside per-sub-phase
    ``REPORT.md`` files inside its sub-phase folders. Phases that have not yet
    entered execution (no descendant content beyond ``PHASE.md``) are exempt
    under the forward-resolvable convention.

    Pass criteria: every closed phase folder has ``REPORT.md`` at its root.
    Exempt: phase folders carrying only ``PHASE.md`` (wave-execution pending).
    When ``suite_name`` is given, only that suite is swept; otherwise every
    suite under the plans tree contributes.
    """
    folders = _iter_phase_folders(root, suite_name=suite_name)
    if not folders:
        scope_label = f"suite '{suite_name}'" if suite_name else "any plan suite"
        reporter.ok(
            f"Phase rollup completeness: no phases under {scope_label} — vacuously clean"
        )
        return

    fails = 0
    forward_resolvable = 0
    verified = 0
    for folder in folders:
        rel = folder.relative_to(root)
        rollup = folder / "REPORT.md"
        if rollup.is_file():
            verified += 1
            continue
        if not _phase_has_sub_phase_content(folder):
            forward_resolvable += 1
            continue
        reporter.fail(
            f"Missing phase-rollup REPORT.md: {rel} (phase has descendant content but no rollup)"
        )
        fails += 1

    if fails == 0:
        if forward_resolvable:
            reporter.ok(
                f"Phase rollup completeness: {verified} closed-phase rollups verified across "
                f"{len(folders)} phase folders ({forward_resolvable} forward-resolvable wave-execution-pending)"
            )
        else:
            reporter.ok(
                f"Phase rollup completeness: {verified} of {len(folders)} phase folders carry a rollup REPORT.md"
            )


def collect_frontmatter_targets(root: Path) -> dict[str, list[Path]]:
    """Return the four sets of markdown files needing frontmatter checks."""
    rules = sorted((root / "rules").glob("*.md"))
    commands = sorted((root / "commands").glob("*.md"))
    agents = sorted((root / "agents").glob("*.md"))
    skills = sorted((root / "skills").rglob("SKILL.md"))
    return {
        "rules": rules,
        "commands": commands,
        "agents": agents,
        "skills": skills,
    }


def run(
    root: Path,
    reporter: Reporter,
    content_root: Path | None = None,
    suite_name: str | None = None,
) -> None:
    """Execute the ecosystem validation stages in order."""
    cr = content_root if content_root is not None else root
    reporter.info(f"Root: {root}")
    if cr != root:
        reporter.info(f"Content-root: {cr}")

    reporter.section("Directory Structure")
    validate_directories(cr, root, reporter)

    reporter.section("Core Files")
    validate_core_files(root, reporter)

    reporter.section("Frontmatter")
    validate_frontmatter(
        [root / _CLAUDE_MD],
        _CLAUDEMD_FIELDS,
        _CLAUDE_MD,
        root,
        reporter,
        name_exempt="CLAUDE",
    )
    targets = collect_frontmatter_targets(root)
    validate_frontmatter(
        targets["rules"],
        _RULE_FIELDS,
        "Rule",
        root,
        reporter,
    )
    validate_rule_bind(targets["rules"], root, reporter)
    validate_frontmatter(
        targets["commands"],
        _COMMAND_FIELDS,
        "Command",
        root,
        reporter,
    )
    validate_frontmatter(
        targets["agents"],
        _AGENT_FIELDS,
        "Agent",
        root,
        reporter,
    )
    validate_frontmatter(
        targets["skills"],
        _SKILL_FIELDS,
        "Skill",
        root,
        reporter,
    )

    reporter.section("Registry Sweep")
    validate_registries(root, reporter)

    reporter.section("Authority Hygiene")
    validate_authority_hygiene(root, reporter)

    reporter.section("Expertise Coverage")
    validate_expertise_coverage(cr, reporter)

    reporter.section("Performance Budgets")
    validate_perf_budgets(cr, reporter)

    reporter.section("Self-Application")
    validate_self_application(root, reporter)

    reporter.section("Option Annotation")
    validate_option_annotation(root, reporter)

    reporter.section("UDA Airtightness")
    validate_uda_airtightness(root, reporter)

    reporter.section("Binding Five-Direction")
    validate_binding_five_direction(cr, reporter)

    reporter.section("Phase Rollup Completeness")
    validate_phase_rollup_completeness(root, reporter, suite_name=suite_name)

    reporter.section("Code Craft")
    validate_code_craft(root, reporter)

    reporter.section("Systemicity")
    validate_systemicity(root, reporter)


# The systemicity phase artifacts (basename + human label). Their location is
# discovered under the active plans tree rather than pinned to any one suite, so
# no plan-internal launch identifier is embedded in tracked source. The two
# memory-tier projections carry their fixed memory/ location.
_SYSTEMICITY_PHASE_ARTIFACTS: Final[tuple[tuple[str, str], ...]] = (
    ("ecosystem-systemicity-map.md", "Ecosystem Systemicity Map (phase artifact)"),
    (
        "plan-suite-integration-thread.md",
        "Plan-Suite Integration Thread (phase artifact)",
    ),
    ("orphan-closure-ledger.md", "Orphan Closure Ledger (eleven-pattern register)"),
    ("silo-dissolution-ledger.md", "Silo Dissolution Ledger (nine-pattern register)"),
)

_SYSTEMICITY_MEMORY_ARTIFACTS: Final[tuple[tuple[str, str], ...]] = (
    (
        "ecosystem-systemicity-map.md",
        "Ecosystem Systemicity Map (memory-tier projection)",
    ),
    (
        "plan-suite-integration-thread.md",
        "Plan-Suite Integration Thread (memory-tier projection)",
    ),
)


def _find_systemicity_phase_artifact(plans_dir: Path, basename: str) -> Path | None:
    """Locate a systemicity phase artifact anywhere under the plans tree.

    Searches ``{plans}/*/phases/*/`` for *basename* so the check binds to the
    artifact by name rather than to a specific historical suite path. Returns the
    first match (paths sorted for determinism) or ``None`` when absent.
    """
    if not plans_dir.is_dir():
        return None
    for match in sorted(plans_dir.glob(f"*/phases/*/{basename}")):
        if match.is_file():
            return match
    return None


_SYSTEMICITY_FORBIDDEN_SYNONYMS: Final[tuple[tuple[str, str], ...]] = (
    # Each tuple is (canonical-token, forbidden-synonym).
    # The verifier sweeps the /plan pipeline surfaces (the first-class
    # `commands/plan-*.md` stage commands) for the forbidden token.
    ("agent", "subagent"),
)


def validate_systemicity(root: Path, reporter: Reporter) -> None:
    """Verify the §0.n Ecosystem Systemicity invariants.

    The check enforces three independent properties:

    1. The canonical systemicity artifacts exist: the phase-tier artifacts
       (Ecosystem Systemicity Map + Plan-Suite Integration Thread + closure
       ledgers) discovered under the active plans tree, plus the two memory-tier
       projections under ``memory/``.
    2. The MEMORY.md index lists every topic file present in ``memory/`` —
       orphan topic files (on disk but not indexed) are findings.
    3. The Plan-Suite Integration Thread's Vocabulary Convention holds across
       the /plan pipeline surfaces (the first-class ``commands/plan-*.md``
       stage commands) — forbidden synonyms return zero hits.

    Publish-checkout guard: properties 1 and 2 govern local development tree
    state (the plans tree and the ``memory/`` tree, both gitignored from the
    publish surface). When BOTH are absent, the publish surface is in scope
    but the systemicity invariants apply only to local trees — the property
    1 / 2 checks pass-through silently and only property 3 (the vocabulary
    sweep against ``commands/``) runs.
    """
    memory_dir = root / "memory"
    plans_dir = _resolve_plans_dir(root)
    # The phase tier is "present" when any suite under the plans tree carries a
    # systemicity phase artifact — discovered by name, not by a pinned suite path.
    has_phase_tier = any(
        _find_systemicity_phase_artifact(plans_dir, basename) is not None
        for basename, _label in _SYSTEMICITY_PHASE_ARTIFACTS
    )
    publish_only = not has_phase_tier and not memory_dir.is_dir()
    if publish_only:
        reporter.ok(
            "Systemicity (publish-only): plans tree and memory/ not present; "
            "skipping artifact-presence and memory-index checks"
        )

    fails = 0
    checks = 0

    if not publish_only:
        # Property 1a: phase-tier artifacts exist somewhere under the plans tree.
        for basename, label in _SYSTEMICITY_PHASE_ARTIFACTS:
            checks += 1
            if _find_systemicity_phase_artifact(plans_dir, basename) is None:
                reporter.fail(f"Missing systemicity artifact: {basename} ({label})")
                fails += 1

        # Property 1b: memory-tier projections exist at their fixed memory/ path.
        for basename, label in _SYSTEMICITY_MEMORY_ARTIFACTS:
            checks += 1
            if not (memory_dir / basename).is_file():
                reporter.fail(
                    f"Missing systemicity artifact: memory/{basename} ({label})"
                )
                fails += 1

        # Property 2: MEMORY.md indexes every topic file in memory/.
        memory_index = memory_dir / "MEMORY.md"
        if memory_index.is_file():
            checks += 1
            try:
                index_text = memory_index.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                reporter.fail("Cannot read memory/MEMORY.md")
                fails += 1
            else:
                for topic in sorted(memory_dir.glob("*.md")):
                    if topic.name == "MEMORY.md":
                        continue
                    if topic.name not in index_text:
                        reporter.fail(
                            f"Memory topic file not listed in MEMORY.md index: memory/{topic.name}",
                        )
                        fails += 1
        else:
            reporter.fail("Missing memory/MEMORY.md")
            fails += 1

    # Property 3: forbidden-synonym sweep on the /plan pipeline surfaces.
    plan_command_files = sorted((root / "commands").glob("plan-*.md"))
    for plan_command in plan_command_files:
        try:
            text = plan_command.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for canonical, forbidden in _SYSTEMICITY_FORBIDDEN_SYNONYMS:
            checks += 1
            # Word-boundary search; tolerant of hyphenation (e.g., 'subagent-orchestration')
            # because the forbidden token's appearance in any form indicates drift from the
            # canonical token. The Π-1 cascade closure permits zero hits ecosystem-wide.
            pattern = re.compile(rf"(?<![\w-]){re.escape(forbidden)}(?![\w-])")
            if pattern.search(text):
                rel = plan_command.relative_to(root)
                reporter.fail(
                    f"Vocabulary drift in {rel}: forbidden token '{forbidden}' "
                    f"(canonical: '{canonical}')",
                )
                fails += 1

    if fails == 0:
        reporter.ok(f"Systemicity clean across {checks} checks")


_CHECK_CHOICES: Final[tuple[str, ...]] = (
    "all",
    "registries",
    "frontmatter-cohort",
    "rule-bind",
    "authority-hygiene",
    "expertise-coverage",
    "perf-budgets",
    "self-application",
    "option-annotation",
    "uda-airtightness",
    "binding-five-direction",
    "phase-rollup-completeness",
    "code-craft",
    "systemicity",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(prog="validate_ecosystem")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--content-root",
        type=Path,
        default=None,
        help=(
            "Directory where ecosystem content dirs (rules, commands, agents, "
            "skills, hooks) live. Defaults to --root. Use src/apothem when "
            "running against the apothem source repository."
        ),
    )
    parser.add_argument(
        "--skip-hooks",
        action="store_true",
        help="Skip the hook validator delegation.",
    )
    parser.add_argument(
        "--check",
        choices=_CHECK_CHOICES,
        default="all",
        help="Restrict the run to a single sub-check.",
    )
    parser.add_argument(
        "--suite",
        type=str,
        default=None,
        help=(
            "Restrict suite-scoped checks (currently: phase-rollup-completeness) "
            "to a single plan suite name under the plans tree (.apothem/plans/{suite}). "
            "Other checks ignore this argument."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 when all checks pass, 1 otherwise."""
    args = parse_args(argv)
    root = args.root or resolve_project_root(Mode.MARKER, script_path=Path(__file__))
    if root is None:
        print("[FAIL] Cannot resolve apothem ecosystem root")
        return 1

    content_root = args.content_root or default_content_root(root)

    reporter = Reporter()
    if args.check == "all":
        run(root, reporter, content_root=content_root, suite_name=args.suite)
    elif args.check == "registries":
        reporter.section("Registry Sweep")
        validate_registries(root, reporter)
    elif args.check == "frontmatter-cohort":
        reporter.section("Frontmatter Cohort")
        targets = collect_frontmatter_targets(root)
        validate_frontmatter(
            targets["rules"],
            _RULE_FIELDS,
            "Rule",
            root,
            reporter,
        )
        validate_rule_bind(targets["rules"], root, reporter)
    elif args.check == "rule-bind":
        reporter.section("Rule Bind")
        targets = collect_frontmatter_targets(root)
        validate_rule_bind(targets["rules"], root, reporter)
    elif args.check == "authority-hygiene":
        reporter.section("Authority Hygiene")
        validate_authority_hygiene(root, reporter)
    elif args.check == "expertise-coverage":
        reporter.section("Expertise Coverage")
        validate_expertise_coverage(root, reporter)
    elif args.check == "perf-budgets":
        reporter.section("Performance Budgets")
        validate_perf_budgets(root, reporter)
    elif args.check == "self-application":
        reporter.section("Self-Application")
        validate_self_application(root, reporter)
    elif args.check == "option-annotation":
        reporter.section("Option Annotation")
        validate_option_annotation(root, reporter)
    elif args.check == "uda-airtightness":
        reporter.section("UDA Airtightness")
        validate_uda_airtightness(root, reporter)
    elif args.check == "binding-five-direction":
        reporter.section("Binding Five-Direction")
        validate_binding_five_direction(content_root, reporter)
    elif args.check == "phase-rollup-completeness":
        reporter.section("Phase Rollup Completeness")
        validate_phase_rollup_completeness(root, reporter, suite_name=args.suite)
    elif args.check == "code-craft":
        reporter.section("Code Craft")
        validate_code_craft(root, reporter)
    elif args.check == "systemicity":
        reporter.section("Systemicity")
        validate_systemicity(root, reporter)

    if args.check == "all" and not args.skip_hooks:
        reporter.section("Hook Validator Delegation")
        import validate_hooks

        hook_code = validate_hooks.main(
            ["--root", str(root), "--content-root", str(content_root)]
        )
        if hook_code == 0:
            reporter.ok("validate_hooks passed")
        else:
            reporter.fail("validate_hooks failed")

    reporter.summary()
    return reporter.exit_code


if __name__ == "__main__":
    sys.exit(main())
