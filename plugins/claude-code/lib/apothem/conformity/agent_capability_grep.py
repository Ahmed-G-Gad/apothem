# SPDX-License-Identifier: MIT

"""Verify every harness declares its agentic-capability matrix.

Why this validator exists. The agent-capability discipline (per
``rules/agent-capability-discipline.md``) requires every harness in
the 17-harness cohort to declare a structured capability matrix in its
template tree so adapter authors, operators, and downstream tooling can
reason about the harness's agentic surface without inspecting source.
The installed machine-readable projection names thirteen fields:
``mcp_servers`` (list of MCP servers the harness can host),
``sub_agent_dispatch`` (bool — whether the harness spawns sub-agents),
``custom_command_support`` (yes/no/discovery-pending),
``recommended_postfix_rendering`` (how recommended option labels render),
``long_context_compaction`` (native or profile-managed long-session
continuity), ``context_ignore_surface`` (native ignore surface or declared
absence), ``standard_convention_pin`` (the sibling pin file),
``tool_surface_restrictions`` (list of tool-surface constraints),
``system_prompt_template_path`` (str pointer to the harness's system-prompt
template), ``agent_memory_surface`` (str naming the harness's memory
surface), ``layered_context_surface`` (native hierarchy or profile-managed
projection), ``lsp_symbol_navigation`` (native/plugin-backed symbol lookup
or tracked gap), and ``hook_learning_capture`` (where recurring hook lessons
are persisted without pass-class chatter).

Detection. For each harness directory at
``src/apothem/harnesses/<harness>/`` that exists, look for one of three
declaration files: ``capabilities.yml`` / ``capabilities.yaml`` /
``agent_capabilities.md``. The YAML form is parsed; the Markdown form is
inspected for the thirteen field markers as ``- field_name:`` lines. A
harness whose directory is present but whose declaration is absent OR
whose declaration is missing any required projection field produces a
finding.

Pre-materialization tolerance. Some harness directories may not yet exist
on disk in early repository states. The validator is absence-tolerant: when zero harness
directories are present, it exits 0 with an informational
``harnesses_not_yet_materialized`` message so the gate does not block
the early absence-tolerant state. Once at least one harness directory exists, the
validator enforces the discipline on every present harness.

Exit semantics. Exits 0 when every present harness declares a complete
capability matrix (or when zero harness directories exist). Exits 2 on
any present harness lacking the declaration or missing any required
field. The exit-2 convention matches the conformity-gate orchestrator's
``EXIT_FAIL`` constant.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

import yaml

GREP_NAME: Final[str] = "agent-capability-grep"
RULE_ANCHOR: Final[str] = "agent-capability-discipline (per-harness capability matrix)"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# The 17-harness cohort. Each entry is the directory name (package key)
# under src/apothem/harnesses/. The cohort is derived from the registry's
# SUPPORTED_PACKAGE_KEYS so a newly-registered adapter (e.g. codebuddy,
# kiro, trae, zed) is validated without editing this tuple. When the
# registry cannot be imported (an unusual mount layout the standalone
# subprocess cannot reach), the validator falls back to the static cohort
# so it never silently shrinks its sweep below the known full set.
_FALLBACK_HARNESS_COHORT: Final[tuple[str, ...]] = (
    "antigravity",
    "claude_code",
    "codex",
    "cursor",
    "gemini_cli",
    "github_copilot",
    "hermes",
    "kimi_code",
    "open_claw",
    "opencode",
    "qwen_code",
    "windsurf",
    "codebuddy",
    "kiro",
    "trae",
    "zed",
    "glm",
)


def _resolve_cohort() -> tuple[str, ...]:
    """Return the harness package-key cohort, derived from the registry.

    Imports ``SUPPORTED_PACKAGE_KEYS`` from the harness registry so the
    cohort tracks the registered adapter set automatically. Falls back to
    the static full cohort if the import fails.
    """
    try:
        from apothem.lib.harness_registry import SUPPORTED_PACKAGE_KEYS
    except Exception:  # import boundary: fall back to the static cohort
        return _FALLBACK_HARNESS_COHORT
    return tuple(SUPPORTED_PACKAGE_KEYS)


HARNESS_COHORT: Final[tuple[str, ...]] = _resolve_cohort()

# The required capability-matrix fields for the installed projection.
REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "mcp_servers",
    "sub_agent_dispatch",
    "custom_command_support",
    "recommended_postfix_rendering",
    "long_context_compaction",
    "context_ignore_surface",
    "layered_context_surface",
    "lsp_symbol_navigation",
    "hook_learning_capture",
    "standard_convention_pin",
    "tool_surface_restrictions",
    "system_prompt_template_path",
    "agent_memory_surface",
)

# Declaration filenames the validator probes per harness, in priority order.
DECLARATION_FILENAMES: Final[tuple[str, ...]] = (
    "capabilities.yml",
    "capabilities.yaml",
    "agent_capabilities.md",
)


@dataclass(frozen=True)
class Finding:
    """One harness lacking a complete capability matrix."""

    harness: str
    detail: str
    missing_fields: list[str] = field(default_factory=list)
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result for a single cohort sweep."""

    grep: str
    root: str
    harnesses_present: int
    harnesses_total: int
    passed: bool
    informational: str | None = None
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, harnesses_present,
        harnesses_total, passed, informational, findings}``; each finding is
        flattened through ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "harnesses_present": self.harnesses_present,
            "harnesses_total": self.harnesses_total,
            "passed": self.passed,
            "informational": self.informational,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _harnesses_dir(root: Path) -> Path:
    return root / "src" / "apothem" / "harnesses"


def _find_declaration(harness_dir: Path) -> Path | None:
    """Probe the harness directory tree for a declaration file.

    Looks at the harness root and at ``templates/`` inside it (the
    rule allows either location). Returns the first match in
    ``DECLARATION_FILENAMES`` priority order, or None when absent.
    """
    candidate_dirs = (harness_dir, harness_dir / "templates")
    for directory in candidate_dirs:
        for filename in DECLARATION_FILENAMES:
            candidate = directory / filename
            if candidate.is_file():
                return candidate
    return None


def _parse_yaml_declaration(path: Path) -> dict[str, object]:
    """Load a YAML declaration into a dict. Empty or non-mapping → {}."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        loaded = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}
    if isinstance(loaded, dict):
        return loaded
    return {}


def _parse_markdown_declaration(path: Path) -> dict[str, object]:
    """Scan a Markdown declaration for ``- field_name:`` field markers.

    The Markdown form admits any prose around the field markers; this
    parser is presence-only — it records each required field's
    presence (mapping to a placeholder True value) without inspecting
    the field's substantive value. The YAML form is the rigorous
    surface; the Markdown form is the lightweight alternative.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    found: dict[str, object] = {}
    for line in text.splitlines():
        stripped = line.strip()
        for field_name in REQUIRED_FIELDS:
            # Accept `- field_name:` or `field_name:` at line start.
            if stripped.startswith(f"- {field_name}:") or stripped.startswith(
                f"{field_name}:"
            ):
                found[field_name] = True
    return found


def _missing_fields(declaration: dict[str, object]) -> list[str]:
    return [f for f in REQUIRED_FIELDS if f not in declaration]


def check(root: Path) -> GrepResult:
    """Walk the harness cohort under root; flag incomplete declarations."""
    harnesses_dir = _harnesses_dir(root)
    findings: list[Finding] = []
    present_count = 0
    for harness in HARNESS_COHORT:
        harness_dir = harnesses_dir / harness
        if not harness_dir.is_dir():
            continue
        present_count += 1
        declaration_path = _find_declaration(harness_dir)
        if declaration_path is None:
            findings.append(
                Finding(
                    harness=harness,
                    detail=(
                        "no capability declaration found; expected one of "
                        f"{list(DECLARATION_FILENAMES)} under {harness_dir} "
                        "or its templates/ subdirectory"
                    ),
                    missing_fields=list(REQUIRED_FIELDS),
                )
            )
            continue
        if declaration_path.suffix in {".yml", ".yaml"}:
            declaration = _parse_yaml_declaration(declaration_path)
        else:
            declaration = _parse_markdown_declaration(declaration_path)
        missing = _missing_fields(declaration)
        if missing:
            findings.append(
                Finding(
                    harness=harness,
                    detail=(
                        f"declaration at {declaration_path} is missing "
                        f"{len(missing)} of {len(REQUIRED_FIELDS)} required "
                        "capability-matrix fields"
                    ),
                    missing_fields=missing,
                )
            )
    informational: str | None = None
    if present_count == 0:
        informational = (
            "harnesses_not_yet_materialized: zero of "
            f"{len(HARNESS_COHORT)} harness directories present under "
            f"{harnesses_dir}; validator is in an absence-tolerant pass"
        )
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        harnesses_present=present_count,
        harnesses_total=len(HARNESS_COHORT),
        passed=not findings,
        informational=informational,
        findings=findings,
    )


def _main(argv: list[str]) -> int:
    # Imported here, not at module top: ``check()`` stays stdlib-only; only
    # the command-line entry needs the shared parser and report stamp.
    from apothem.conformity._grep_base import finish_root_report, parse_root_args

    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    result = check(root)
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=result.harnesses_present,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
