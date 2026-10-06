# SPDX-License-Identifier: MIT

"""Declarative harness-registry data table (split from harness_registry.py).

This module carries ONLY the static, declarative ``HARNESS_REGISTRY`` data table
and the dataclass + capability-matrix builders it is constructed from. The
resolution / discovery LOGIC and every public re-export live in the sibling
``harness_registry`` module, which imports this data and is the authoritative
runtime surface. Consumers import from ``apothem.lib.harness_registry`` as
before; this module is an internal data partition.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

CapabilityStatus = Literal[
    "native",
    "converted",
    "support-tree",
    "profile-projected",
    "unsupported",
    "not-applicable",
    "discovery-pending",
]

HarnessScope = Literal["user", "project"]

REQUIRED_CAPABILITIES: tuple[str, ...] = (
    "commands",
    "skills",
    "hooks",
    "agents",
    "rules",
    "templates",
    "statuslines",
    "output_styles",
    "mcp_servers",
    "sub_agent_dispatch",
    "tool_surface_restrictions",
    "system_prompt_templates",
    "agent_memory",
)

SUPPORTED_HARNESS_COUNT = 17


@dataclass(frozen=True)
class HarnessRegistryEntry:
    """One supported harness and the files that must agree with it."""

    public_id: str
    package_key: str
    display_name: str
    entry_point: str
    scope: HarnessScope
    output_format: str
    target_paths: tuple[str, ...]
    docs_path: str
    comparison_docs_path: str
    capabilities_path: str
    standard_pin_path: str
    fixture_tests: tuple[str, ...]
    package_data_key: str | None = None
    template_sources: tuple[str, ...] = ()
    capability_status: Mapping[str, CapabilityStatus] = field(default_factory=dict)
    unsupported_rationale: Mapping[str, str] = field(default_factory=dict)

    @property
    def adapter_module(self) -> str:
        """Return the importable module path for the adapter class."""
        return self.entry_point.split(":", 1)[0]

    @property
    def adapter_class_name(self) -> str:
        """Return the adapter class name declared by the entry point."""
        return self.entry_point.split(":", 1)[1]


@dataclass(frozen=True)
class SharedRoot:
    """An install target that harnesses other than its writer also load.

    Each shared root has exactly one owner: the registered adapter that writes
    ``path``. ``readers`` are the other registered harnesses whose vendor docs
    load ``path`` by default (an opt-in load is not listed), and ``evidence``
    holds those vendor pages, retrieved on ``retrieved``. ``path`` uses the
    registry ``target_paths`` notation (``~/`` for the user home,
    ``<project>/`` for the project root).
    """

    path: str
    owner: str
    readers: tuple[str, ...]
    evidence: tuple[str, ...]
    retrieved: str


def _matrix(**values: CapabilityStatus) -> Mapping[str, CapabilityStatus]:
    # Exact-coverage gate: every one of REQUIRED_CAPABILITIES must be assigned a
    # status AND no unknown axis may leak in, so a registry entry's matrix is
    # provably complete. (`_unsupported` below relaxes this to subset-valid,
    # since only exempt-status cells carry a rationale.)
    missing = sorted(set(REQUIRED_CAPABILITIES).difference(values))
    extra = sorted(set(values).difference(REQUIRED_CAPABILITIES))
    if missing or extra:
        raise ValueError(
            "capability matrix mismatch: "
            f"missing={missing or 'none'} extra={extra or 'none'}"
        )
    return dict(values)


def _unsupported(**values: str) -> Mapping[str, str]:
    # Mirror `_matrix`'s extra-key guard: every rationale key MUST name a real
    # capability axis. A rationale is subset-valid (only exempt-status cells —
    # unsupported / not-applicable / discovery-pending — need one, not all 13),
    # so no missing-key check applies; but a typo'd or renamed axis key would
    # silently attach a rationale to no cell and leave the intended cell
    # unbacked, which is exactly the drift `_matrix` rejects at construction.
    extra = sorted(set(values).difference(REQUIRED_CAPABILITIES))
    if extra:
        raise ValueError(
            f"unsupported rationale names unknown capability axes: {extra}"
        )
    return dict(values)


HARNESS_REGISTRY: tuple[HarnessRegistryEntry, ...] = (
    HarnessRegistryEntry(
        public_id="antigravity",
        package_key="antigravity",
        display_name="Antigravity",
        entry_point="apothem.harnesses.antigravity:AntigravityAdapter",
        scope="user",
        output_format="markdown",
        target_paths=(
            "~/.gemini/GEMINI.md",
            "~/.gemini/antigravity-cli/plugins/apothem/",
        ),
        docs_path="site/content/docs/harnesses/antigravity.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-antigravity.mdx",
        capabilities_path="src/apothem/harnesses/antigravity/capabilities.yml",
        standard_pin_path=(
            "src/apothem/harnesses/antigravity/STANDARD-CONVENTION-PIN.md"
        ),
        fixture_tests=("tests/unit/test_antigravity_adapter.py",),
        package_data_key="apothem.harnesses.antigravity",
        template_sources=(
            "harnesses/antigravity/templates/GEMINI.md",
            "harnesses/antigravity/templates/plugin.json",
        ),
        capability_status=_matrix(
            commands="converted",
            skills="native",
            hooks="support-tree",
            agents="converted",
            rules="converted",
            templates="support-tree",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="discovery-pending",
            sub_agent_dispatch="native",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="discovery-pending",
        ),
        unsupported_rationale=_unsupported(
            mcp_servers="MCP lives in an operator-owned config surface (file / CLI / service state); the adapter names it but authors no entries.",
            statuslines="No current Antigravity CLI statusline file surface is pinned.",
            output_styles="No current Antigravity CLI output-style surface is pinned.",
            agent_memory="The Antigravity docs index (antigravity.google/llms.txt, retrieved 2026-10-03) lists no durable-memory surface.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="claude-code",
        package_key="claude_code",
        display_name="Claude Code",
        entry_point="apothem.harnesses.claude_code:ClaudeCodeAdapter",
        scope="user",
        output_format="json",
        target_paths=(
            "~/.claude/settings.json",
            "~/.claude/CLAUDE.md",
            "~/.claude/{agents,rules,skills,statuslines,output-styles}/",
            "~/.claude/.apothem/support/{templates,hooks,conformity,schemas}/",
        ),
        docs_path="site/content/docs/harnesses/claude-code.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-claude-code.mdx",
        capabilities_path="src/apothem/harnesses/claude_code/capabilities.yml",
        standard_pin_path=(
            "src/apothem/harnesses/claude_code/STANDARD-CONVENTION-PIN.md"
        ),
        fixture_tests=("tests/unit/test_claude_code_adapter.py",),
        package_data_key="apothem.harnesses.claude_code",
        template_sources=("harnesses/claude_code/templates/settings.json",),
        capability_status=_matrix(
            commands="converted",
            skills="native",
            hooks="native",
            agents="native",
            rules="native",
            templates="support-tree",
            statuslines="native",
            output_styles="native",
            mcp_servers="discovery-pending",
            sub_agent_dispatch="native",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="not-applicable",
            agent_memory="not-applicable",
        ),
        unsupported_rationale=_unsupported(
            mcp_servers="MCP lives in an operator-owned config surface (file / CLI / service state); the adapter names it but authors no entries.",
            system_prompt_templates=(
                "CLAUDE.md is operator-owned and intentionally not adapter-written."
            ),
        ),
    ),
    HarnessRegistryEntry(
        public_id="codex",
        package_key="codex",
        display_name="Codex",
        entry_point="apothem.harnesses.codex:CodexAdapter",
        scope="user",
        output_format="markdown",
        target_paths=(
            "~/.codex/AGENTS.md",
            "~/.codex/hooks.json",
            "~/.codex/hooks/",
            "~/.codex/agents/*.toml",
            "~/.agents/skills/",
            "~/.config/apothem/{rules,templates}/",
        ),
        docs_path="site/content/docs/harnesses/codex.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-codex.mdx",
        capabilities_path="src/apothem/harnesses/codex/capabilities.yml",
        standard_pin_path="src/apothem/harnesses/codex/STANDARD-CONVENTION-PIN.md",
        fixture_tests=("tests/unit/test_codex_adapter.py",),
        package_data_key="apothem.harnesses.codex",
        template_sources=(
            "harnesses/codex/templates/AGENTS.md",
            "harnesses/codex/templates/hooks.json",
        ),
        capability_status=_matrix(
            commands="converted",
            skills="native",
            hooks="native",
            agents="converted",
            rules="support-tree",
            templates="support-tree",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="discovery-pending",
            sub_agent_dispatch="native",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="not-applicable",
        ),
        unsupported_rationale=_unsupported(
            mcp_servers="MCP lives in an operator-owned config surface (file / CLI / service state); the adapter names it but authors no entries.",
            statuslines="No Codex statusline file surface is pinned.",
            output_styles="No Codex output-style file surface is pinned.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="cursor",
        package_key="cursor",
        display_name="Cursor",
        entry_point="apothem.harnesses.cursor:CursorAdapter",
        scope="project",
        output_format="mdc",
        target_paths=("<project>/.cursor/rules/apothem-rules.mdc",),
        docs_path="site/content/docs/harnesses/cursor.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-cursor.mdx",
        capabilities_path="src/apothem/harnesses/cursor/capabilities.yml",
        standard_pin_path="src/apothem/harnesses/cursor/STANDARD-CONVENTION-PIN.md",
        fixture_tests=("tests/unit/test_cursor_adapter.py",),
        package_data_key="apothem.harnesses.cursor",
        template_sources=("harnesses/cursor/templates/apothem-rules.mdc",),
        capability_status=_matrix(
            commands="unsupported",
            skills="unsupported",
            hooks="unsupported",
            agents="unsupported",
            rules="native",
            templates="not-applicable",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="discovery-pending",
            sub_agent_dispatch="unsupported",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="unsupported",
        ),
        unsupported_rationale=_unsupported(
            mcp_servers="MCP lives in an operator-owned config surface (file / CLI / service state); the adapter names it but authors no entries.",
            commands="The Cursor adapter delivers the project rules surface "
            "only; Apothem does not author a Cursor command cohort.",
            skills="The Cursor adapter delivers the project rules surface "
            "only; Apothem does not author a Cursor skill cohort.",
            hooks="The Cursor adapter delivers the project rules surface "
            "only; Apothem does not author a Cursor hook cohort.",
            agents="The Cursor adapter delivers the project rules surface "
            "only; Apothem does not author a Cursor agent cohort.",
            statuslines="No Cursor statusline file surface is pinned.",
            output_styles="No Cursor output-style file surface is pinned.",
            sub_agent_dispatch="The Cursor adapter delivers the project rules "
            "surface only; Apothem does not dispatch sub-agents through Cursor.",
            agent_memory="No Cursor durable memory file surface is adapter-owned.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="gemini-cli",
        package_key="gemini_cli",
        display_name="Gemini CLI",
        entry_point="apothem.harnesses.gemini_cli:GeminiCliAdapter",
        scope="project",
        output_format="markdown",
        target_paths=(
            "<project>/GEMINI.md",
            "<project>/.gemini/{commands,skills,agents}/",
            "<project>/.gemini/.apothem/support/",
        ),
        docs_path="site/content/docs/harnesses/gemini-cli.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-gemini-cli.mdx",
        capabilities_path="src/apothem/harnesses/gemini_cli/capabilities.yml",
        standard_pin_path=(
            "src/apothem/harnesses/gemini_cli/STANDARD-CONVENTION-PIN.md"
        ),
        fixture_tests=("tests/unit/test_gemini_cli_adapter.py",),
        package_data_key="apothem.harnesses.gemini_cli",
        template_sources=("harnesses/gemini_cli/templates/GEMINI.md",),
        capability_status=_matrix(
            commands="converted",
            skills="native",
            hooks="support-tree",
            agents="converted",
            rules="support-tree",
            templates="support-tree",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="discovery-pending",
            sub_agent_dispatch="native",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="native",
        ),
        unsupported_rationale=_unsupported(
            mcp_servers="MCP lives in an operator-owned config surface (file / CLI / service state); the adapter names it but authors no entries.",
            statuslines="No Gemini CLI statusline file surface is pinned.",
            output_styles="No Gemini CLI output-style file surface is pinned.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="github-copilot",
        package_key="github_copilot",
        display_name="GitHub Copilot",
        entry_point="apothem.harnesses.github_copilot:GitHubCopilotAdapter",
        scope="project",
        output_format="markdown",
        target_paths=("<project>/.github/copilot-instructions.md",),
        docs_path="site/content/docs/harnesses/github-copilot.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-github-copilot.mdx",
        capabilities_path="src/apothem/harnesses/github_copilot/capabilities.yml",
        standard_pin_path=(
            "src/apothem/harnesses/github_copilot/STANDARD-CONVENTION-PIN.md"
        ),
        fixture_tests=("tests/unit/test_github_copilot_adapter.py",),
        package_data_key="apothem.harnesses.github_copilot",
        template_sources=(
            "harnesses/github_copilot/templates/copilot-instructions.md",
        ),
        capability_status=_matrix(
            commands="unsupported",
            skills="unsupported",
            hooks="unsupported",
            agents="unsupported",
            rules="native",
            templates="not-applicable",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="unsupported",
            sub_agent_dispatch="unsupported",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="unsupported",
        ),
        unsupported_rationale=_unsupported(
            commands="Copilot runs prompt files (.github/prompts/*.prompt.md) as slash commands; the adapter delivers the repo-wide instructions file only and Apothem does not author prompt files.",
            skills="The Copilot adapter delivers the repo-wide instructions "
            "surface only; Apothem does not author a Copilot skill cohort.",
            hooks="The Copilot adapter delivers the repo-wide instructions "
            "surface only; Apothem does not author a Copilot hook cohort.",
            agents="Copilot reads custom agent profiles (.github/agents/*.agent.md); the adapter delivers the repo-wide instructions file only and Apothem does not author agent profiles.",
            statuslines="No Copilot statusline file surface is pinned.",
            output_styles="No Copilot output-style file surface is pinned.",
            mcp_servers="Copilot MCP is configured in repository settings, the IDE, the Copilot CLI, or a custom agent profile; the adapter authors none of them.",
            sub_agent_dispatch="Copilot sub-agent dispatch is outside this adapter scope.",
            agent_memory="Copilot user memory is IDE/service state, not a file target.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="hermes",
        package_key="hermes",
        display_name="Hermes",
        entry_point="apothem.harnesses.hermes:HermesAdapter",
        scope="user",
        output_format="yaml",
        target_paths=("~/.hermes/config.yaml", "~/.hermes/.apothem/support/"),
        docs_path="site/content/docs/harnesses/hermes.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-hermes.mdx",
        capabilities_path="src/apothem/harnesses/hermes/capabilities.yml",
        standard_pin_path="src/apothem/harnesses/hermes/STANDARD-CONVENTION-PIN.md",
        fixture_tests=("tests/unit/test_hermes_adapter.py",),
        package_data_key="apothem.harnesses.hermes",
        capability_status=_matrix(
            commands="converted",
            skills="support-tree",
            hooks="support-tree",
            agents="support-tree",
            rules="support-tree",
            templates="support-tree",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="native",
            sub_agent_dispatch="native",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="not-applicable",
        ),
        unsupported_rationale=_unsupported(
            statuslines="No Hermes statusline file surface is pinned.",
            output_styles="No Hermes output-style file surface is pinned.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="kimi-code",
        package_key="kimi_code",
        display_name="Kimi Code",
        entry_point="apothem.harnesses.kimi_code:KimiCodeAdapter",
        scope="project",
        output_format="markdown",
        target_paths=(
            "<project>/AGENTS.md",
            "<project>/.kimi-code/.apothem/support/",
        ),
        docs_path="site/content/docs/harnesses/kimi-code.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-kimi-code.mdx",
        capabilities_path="src/apothem/harnesses/kimi_code/capabilities.yml",
        standard_pin_path=(
            "src/apothem/harnesses/kimi_code/STANDARD-CONVENTION-PIN.md"
        ),
        fixture_tests=("tests/unit/test_kimi_code_adapter.py",),
        package_data_key="apothem.harnesses.kimi_code",
        template_sources=("harnesses/kimi_code/templates/AGENTS.md",),
        capability_status=_matrix(
            commands="support-tree",
            skills="support-tree",
            hooks="support-tree",
            agents="support-tree",
            rules="support-tree",
            templates="support-tree",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="discovery-pending",
            sub_agent_dispatch="native",
            tool_surface_restrictions="discovery-pending",
            system_prompt_templates="native",
            agent_memory="native",
        ),
        unsupported_rationale=_unsupported(
            statuslines="No Kimi Code statusline file surface is pinned.",
            output_styles="No Kimi Code output-style file surface is pinned.",
            mcp_servers="`.kimi-code/mcp.json` is the recognized operator-owned "
            "MCP surface; Apothem names it but defers authoring entries.",
            tool_surface_restrictions="Kimi Code documents "
            "default_permission_mode and [[permission.rules]] in "
            "~/.kimi-code/config.toml; Apothem has not yet decided how to project "
            "the universal-deny floor into them.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="open-claw",
        package_key="open_claw",
        display_name="Open-Claw",
        entry_point="apothem.harnesses.open_claw:OpenClawAdapter",
        scope="user",
        output_format="json",
        target_paths=("~/.openclaw/openclaw.json", "~/.openclaw/.apothem/support/"),
        docs_path="site/content/docs/harnesses/open-claw.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-open-claw.mdx",
        capabilities_path="src/apothem/harnesses/open_claw/capabilities.yml",
        standard_pin_path=(
            "src/apothem/harnesses/open_claw/STANDARD-CONVENTION-PIN.md"
        ),
        fixture_tests=("tests/unit/test_open_claw_adapter.py",),
        package_data_key="apothem.harnesses.open_claw",
        capability_status=_matrix(
            commands="converted",
            skills="support-tree",
            hooks="support-tree",
            agents="support-tree",
            rules="support-tree",
            templates="support-tree",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="unsupported",
            sub_agent_dispatch="native",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="not-applicable",
        ),
        unsupported_rationale=_unsupported(
            statuslines="No Open-Claw statusline file surface is pinned.",
            output_styles="No Open-Claw output-style file surface is pinned.",
            mcp_servers=(
                "Open-Claw MCP lives in the mcp.servers config block managed "
                "via the openclaw mcp CLI; the adapter authors no entries."
            ),
            agent_memory="Open-Claw support material is config-referenced, not memory.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="opencode",
        package_key="opencode",
        display_name="OpenCode",
        entry_point="apothem.harnesses.opencode:OpenCodeAdapter",
        scope="user",
        output_format="json",
        target_paths=(
            "~/.config/opencode/opencode.json",
            "~/.config/opencode/{commands,skills,agents}/",
            "~/.config/opencode/.apothem/support/",
        ),
        docs_path="site/content/docs/harnesses/opencode.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-opencode.mdx",
        capabilities_path="src/apothem/harnesses/opencode/capabilities.yml",
        standard_pin_path="src/apothem/harnesses/opencode/STANDARD-CONVENTION-PIN.md",
        fixture_tests=("tests/unit/test_opencode_adapter.py",),
        package_data_key="apothem.harnesses.opencode",
        capability_status=_matrix(
            commands="converted",
            skills="native",
            hooks="support-tree",
            agents="converted",
            rules="support-tree",
            templates="support-tree",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="native",
            sub_agent_dispatch="native",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="not-applicable",
        ),
        unsupported_rationale=_unsupported(
            statuslines="No OpenCode statusline file surface is pinned.",
            output_styles="No OpenCode output-style file surface is pinned.",
            agent_memory="OpenCode support material is config-referenced, not memory.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="qwen-code",
        package_key="qwen_code",
        display_name="Qwen Code",
        entry_point="apothem.harnesses.qwen_code:QwenCodeAdapter",
        scope="user",
        output_format="json",
        target_paths=(
            "~/.qwen/settings.json",
            "~/.qwen/QWEN.md",
            "~/.qwen/{commands,skills,agents}/",
            "~/.qwen/.apothem/support/",
        ),
        docs_path="site/content/docs/harnesses/qwen-code.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-qwen-code.mdx",
        capabilities_path="src/apothem/harnesses/qwen_code/capabilities.yml",
        standard_pin_path=(
            "src/apothem/harnesses/qwen_code/STANDARD-CONVENTION-PIN.md"
        ),
        fixture_tests=("tests/unit/test_qwen_code_adapter.py",),
        package_data_key="apothem.harnesses.qwen_code",
        template_sources=("harnesses/qwen_code/templates/QWEN.md",),
        capability_status=_matrix(
            commands="converted",
            skills="native",
            hooks="native",
            agents="converted",
            rules="support-tree",
            templates="support-tree",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="native",
            sub_agent_dispatch="native",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="not-applicable",
        ),
        unsupported_rationale=_unsupported(
            statuslines="No Qwen Code statusline file surface is pinned.",
            output_styles="No Qwen Code output-style file surface is pinned.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="windsurf",
        package_key="windsurf",
        display_name="Windsurf",
        entry_point="apothem.harnesses.windsurf:WindsurfAdapter",
        scope="project",
        output_format="markdown",
        target_paths=("<project>/.devin/rules/apothem-rules.md",),
        docs_path="site/content/docs/harnesses/windsurf.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-windsurf.mdx",
        capabilities_path="src/apothem/harnesses/windsurf/capabilities.yml",
        standard_pin_path="src/apothem/harnesses/windsurf/STANDARD-CONVENTION-PIN.md",
        fixture_tests=("tests/unit/test_windsurf_adapter.py",),
        package_data_key="apothem.harnesses.windsurf",
        template_sources=("harnesses/windsurf/templates/apothem-rules.md",),
        capability_status=_matrix(
            commands="unsupported",
            skills="unsupported",
            hooks="unsupported",
            agents="unsupported",
            rules="native",
            templates="not-applicable",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="discovery-pending",
            sub_agent_dispatch="unsupported",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="unsupported",
        ),
        unsupported_rationale=_unsupported(
            mcp_servers="MCP lives in an operator-owned config surface (file / CLI / service state); the adapter names it but authors no entries.",
            commands="The Windsurf adapter delivers the project rules surface "
            "only; Apothem does not author a Windsurf workflow cohort.",
            skills="The Windsurf adapter delivers the project rules surface "
            "only; Apothem does not author a Windsurf skill cohort.",
            hooks="The Windsurf adapter delivers the project rules surface "
            "only; Apothem does not author a Windsurf hook cohort.",
            agents="Devin documents subagents (docs.devin.ai/cli/subagents); the Windsurf adapter delivers the project rules file only and Apothem does not author Devin subagents.",
            statuslines="No Windsurf statusline file surface is pinned.",
            output_styles="No Windsurf output-style file surface is pinned.",
            sub_agent_dispatch="The Windsurf adapter delivers the project rules file only; Apothem does not dispatch sub-agents through Devin Desktop.",
            agent_memory="Windsurf memories are machine-local and not adapter-owned.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="codebuddy",
        package_key="codebuddy",
        display_name="CodeBuddy",
        entry_point="apothem.harnesses.codebuddy:CodeBuddyAdapter",
        scope="project",
        output_format="markdown",
        target_paths=("<project>/.codebuddy/rules/apothem-rules.md",),
        docs_path="site/content/docs/harnesses/codebuddy.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-codebuddy.mdx",
        capabilities_path="src/apothem/harnesses/codebuddy/capabilities.yml",
        standard_pin_path=(
            "src/apothem/harnesses/codebuddy/STANDARD-CONVENTION-PIN.md"
        ),
        fixture_tests=("tests/unit/test_codebuddy_adapter.py",),
        package_data_key="apothem.harnesses.codebuddy",
        template_sources=("harnesses/codebuddy/templates/apothem-rules.md",),
        capability_status=_matrix(
            commands="unsupported",
            skills="unsupported",
            hooks="unsupported",
            agents="unsupported",
            rules="native",
            templates="not-applicable",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="discovery-pending",
            sub_agent_dispatch="unsupported",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="not-applicable",
        ),
        unsupported_rationale=_unsupported(
            mcp_servers="MCP lives in an operator-owned config surface (file / CLI / service state); the adapter names it but authors no entries.",
            commands="The CodeBuddy adapter delivers the project rules surface "
            "only; Apothem does not author a CodeBuddy command cohort.",
            skills="The CodeBuddy adapter delivers the project rules surface "
            "only; Apothem does not author a CodeBuddy skill cohort.",
            hooks="The CodeBuddy adapter delivers the project rules surface "
            "only; Apothem does not author a CodeBuddy hook cohort.",
            agents="The CodeBuddy adapter delivers the project rules surface "
            "only; Apothem does not author a CodeBuddy sub-agent cohort.",
            statuslines="No CodeBuddy statusline file surface is pinned.",
            output_styles="No CodeBuddy output-style file surface is pinned.",
            sub_agent_dispatch="CodeBuddy Code documents sub-agents; the "
            "CodeBuddy adapter delivers the project rules file only and Apothem "
            "does not dispatch sub-agents through CodeBuddy.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="kiro",
        package_key="kiro",
        display_name="Kiro",
        entry_point="apothem.harnesses.kiro:KiroAdapter",
        scope="project",
        output_format="markdown",
        target_paths=("<project>/.kiro/steering/apothem-rules.md",),
        docs_path="site/content/docs/harnesses/kiro.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-kiro.mdx",
        capabilities_path="src/apothem/harnesses/kiro/capabilities.yml",
        standard_pin_path="src/apothem/harnesses/kiro/STANDARD-CONVENTION-PIN.md",
        fixture_tests=("tests/unit/test_kiro_adapter.py",),
        package_data_key="apothem.harnesses.kiro",
        template_sources=("harnesses/kiro/templates/apothem-rules.md",),
        capability_status=_matrix(
            commands="unsupported",
            skills="unsupported",
            hooks="unsupported",
            agents="unsupported",
            rules="native",
            templates="not-applicable",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="discovery-pending",
            sub_agent_dispatch="unsupported",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="not-applicable",
        ),
        unsupported_rationale=_unsupported(
            mcp_servers="MCP lives in an operator-owned config surface (file / CLI / service state); the adapter names it but authors no entries.",
            commands="The Kiro adapter delivers the project steering surface "
            "only; Apothem does not author a Kiro command cohort.",
            skills="The Kiro adapter delivers the project steering surface "
            "only; Apothem does not author a Kiro skill cohort.",
            hooks="The Kiro adapter delivers the project steering surface "
            "only; Apothem does not author a Kiro agent-hook cohort.",
            agents="The Kiro adapter delivers steering rules only; Apothem "
            "does not author a Kiro sub-agent cohort.",
            statuslines="No Kiro statusline file surface is pinned.",
            output_styles="No Kiro output-style file surface is pinned.",
            sub_agent_dispatch="Kiro documents custom agents (.kiro/agents and "
            "the Kiro CLI); the Kiro adapter delivers steering rules only and "
            "Apothem does not dispatch sub-agents through Kiro.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="trae",
        package_key="trae",
        display_name="Trae",
        entry_point="apothem.harnesses.trae:TraeAdapter",
        scope="project",
        output_format="markdown",
        target_paths=("<project>/.trae/rules/apothem-rules.md",),
        docs_path="site/content/docs/harnesses/trae.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-trae.mdx",
        capabilities_path="src/apothem/harnesses/trae/capabilities.yml",
        standard_pin_path="src/apothem/harnesses/trae/STANDARD-CONVENTION-PIN.md",
        fixture_tests=("tests/unit/test_trae_adapter.py",),
        package_data_key="apothem.harnesses.trae",
        template_sources=("harnesses/trae/templates/apothem-rules.md",),
        capability_status=_matrix(
            commands="unsupported",
            skills="unsupported",
            hooks="unsupported",
            agents="unsupported",
            rules="native",
            templates="not-applicable",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="discovery-pending",
            sub_agent_dispatch="unsupported",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="unsupported",
        ),
        unsupported_rationale=_unsupported(
            mcp_servers="MCP lives in an operator-owned config surface (file / CLI / service state); the adapter names it but authors no entries.",
            commands="The Trae adapter delivers the project rules surface "
            "only; Apothem does not author a Trae command cohort.",
            skills="The Trae adapter delivers the project rules surface "
            "only; Apothem does not author a Trae skill cohort.",
            hooks="The Trae adapter delivers the project rules surface "
            "only; Apothem does not author a Trae hook cohort.",
            agents="Trae documents custom Agents (docs.trae.ai/ide/agent); the Trae adapter delivers the project rules file only and Apothem does not author Trae agents.",
            statuslines="No Trae statusline file surface is pinned.",
            output_styles="No Trae output-style file surface is pinned.",
            sub_agent_dispatch="The Trae adapter delivers the project rules file only; Apothem does not dispatch sub-agents through Trae.",
            agent_memory="No Trae adapter-owned agent-memory surface is documented.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="zed",
        package_key="zed",
        display_name="Zed",
        entry_point="apothem.harnesses.zed:ZedAdapter",
        scope="project",
        output_format="markdown",
        target_paths=("<project>/.rules",),
        docs_path="site/content/docs/harnesses/zed.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-zed.mdx",
        capabilities_path="src/apothem/harnesses/zed/capabilities.yml",
        standard_pin_path="src/apothem/harnesses/zed/STANDARD-CONVENTION-PIN.md",
        fixture_tests=("tests/unit/test_zed_adapter.py",),
        package_data_key="apothem.harnesses.zed",
        template_sources=("harnesses/zed/templates/apothem-rules.md",),
        capability_status=_matrix(
            commands="unsupported",
            skills="unsupported",
            hooks="unsupported",
            agents="unsupported",
            rules="native",
            templates="not-applicable",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="discovery-pending",
            sub_agent_dispatch="unsupported",
            tool_surface_restrictions="not-applicable",
            system_prompt_templates="native",
            agent_memory="unsupported",
        ),
        unsupported_rationale=_unsupported(
            mcp_servers="MCP lives in an operator-owned config surface (file / CLI / service state); the adapter names it but authors no entries.",
            commands="The Zed adapter delivers the project rules surface "
            "only; Apothem does not author a Zed command cohort.",
            skills="The Zed adapter delivers the project rules surface "
            "only; Apothem does not author a Zed skill cohort.",
            hooks="The Zed adapter delivers the project rules surface "
            "only; Apothem does not author a Zed hook cohort.",
            agents="The Zed adapter delivers the project rules file only; Apothem does not author Zed agent profiles or external agents.",
            statuslines="No Zed statusline file surface is pinned.",
            output_styles="No Zed output-style file surface is pinned.",
            sub_agent_dispatch="The Zed adapter delivers the project rules file only; Apothem does not dispatch sub-agents through Zed.",
            agent_memory="Zed agent memory is session-local and not adapter-owned.",
        ),
    ),
    HarnessRegistryEntry(
        public_id="glm",
        package_key="glm",
        display_name="GLM (Z.ai)",
        entry_point="apothem.harnesses.glm:GlmAdapter",
        scope="project",
        output_format="toml",
        target_paths=("<project>/.apothem/providers/glm.toml",),
        docs_path="site/content/docs/harnesses/glm.mdx",
        comparison_docs_path="site/content/docs/comparison/vs-raw-glm.mdx",
        capabilities_path="src/apothem/harnesses/glm/capabilities.yml",
        standard_pin_path="src/apothem/harnesses/glm/STANDARD-CONVENTION-PIN.md",
        fixture_tests=("tests/unit/test_glm_adapter.py",),
        package_data_key="apothem.harnesses.glm",
        template_sources=("harnesses/glm/templates/glm.toml",),
        capability_status=_matrix(
            commands="unsupported",
            skills="unsupported",
            hooks="unsupported",
            agents="unsupported",
            rules="unsupported",
            templates="unsupported",
            statuslines="unsupported",
            output_styles="unsupported",
            mcp_servers="unsupported",
            sub_agent_dispatch="unsupported",
            tool_surface_restrictions="unsupported",
            system_prompt_templates="unsupported",
            agent_memory="unsupported",
        ),
        unsupported_rationale=_unsupported(
            commands="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native command surface.",
            skills="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native skill surface.",
            hooks="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native hook surface.",
            agents="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native agent surface.",
            rules="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native rule surface.",
            templates="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native template surface.",
            statuslines="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native statusline surface.",
            output_styles="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native output-style surface.",
            mcp_servers="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native MCP-server surface.",
            sub_agent_dispatch="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native sub-agent-dispatch surface.",
            tool_surface_restrictions="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native tool-surface-restriction surface.",
            system_prompt_templates="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native system-prompt-template surface.",
            agent_memory="GLM is a model backend configured via Anthropic/OpenAI-compatible env; it exposes no native agent-memory surface.",
        ),
    ),
)


# Paths that more than one harness loads. One owner per shared root: the owner
# is the only adapter that writes the path, and every other harness that loads
# it is a reader. Installing the owner places Apothem content in front of every
# reader, and uninstalling the owner removes it from every reader, so the
# install advisories name the readers. Evidence retrieved 2026-10-02.
SHARED_ROOTS: tuple[SharedRoot, ...] = (
    SharedRoot(
        path="~/.agents/skills/",
        owner="codex",
        readers=(
            "cursor",
            "gemini-cli",
            "github-copilot",
            "kimi-code",
            "open-claw",
            "opencode",
            "windsurf",
            "zed",
        ),
        evidence=(
            "https://learn.chatgpt.com/docs/build-skills",
            "https://cursor.com/docs/skills",
            "https://raw.githubusercontent.com/google-gemini/gemini-cli/fb972b2f87fe7d5b06d37eac711490162d98de2c/docs/cli/skills.md",
            "https://docs.github.com/en/copilot/concepts/agents/about-agent-skills",
            "https://moonshotai.github.io/kimi-code/en/customization/skills",
            "https://docs.openclaw.ai/tools/skills",
            "https://opencode.ai/docs/skills/",
            "https://docs.devin.ai/desktop/cascade/skills.md",
            "https://zed.dev/docs/ai/skills",
        ),
        retrieved="2026-10-02",
    ),
    SharedRoot(
        path="~/.claude/skills/",
        owner="claude-code",
        readers=("cursor", "opencode"),
        evidence=(
            "https://code.claude.com/docs/en/skills.md",
            "https://cursor.com/docs/skills",
            "https://opencode.ai/docs/skills/",
        ),
        retrieved="2026-10-02",
    ),
    SharedRoot(
        path="~/.claude/CLAUDE.md",
        owner="claude-code",
        readers=("opencode",),
        evidence=(
            "https://code.claude.com/docs/en/memory",
            "https://opencode.ai/docs/rules/",
        ),
        retrieved="2026-10-03",
    ),
    SharedRoot(
        path="<project>/AGENTS.md",
        owner="kimi-code",
        readers=(
            "antigravity",
            "codebuddy",
            "codex",
            "cursor",
            "github-copilot",
            "hermes",
            "kiro",
            "opencode",
            "windsurf",
            "zed",
        ),
        evidence=(
            "https://moonshotai.github.io/kimi-code/en/customization/agents",
            "https://antigravity.google/docs/rules",
            "https://www.codebuddy.ai/docs/cli/memory",
            "https://learn.chatgpt.com/docs/agent-configuration/agents-md",
            "https://cursor.com/docs/rules",
            "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions",
            "https://raw.githubusercontent.com/NousResearch/hermes-agent/1c56fed0480e67ffd56675d10862e607fb61a55b/website/docs/user-guide/features/context-files.md",
            "https://kiro.dev/docs/steering/",
            "https://opencode.ai/docs/rules/",
            "https://docs.devin.ai/desktop/cascade/agents-md.md",
            "https://zed.dev/docs/ai/instructions",
        ),
        retrieved="2026-10-02",
    ),
    SharedRoot(
        path="<project>/GEMINI.md",
        owner="gemini-cli",
        readers=("antigravity", "github-copilot", "zed"),
        evidence=(
            "https://raw.githubusercontent.com/google-gemini/gemini-cli/fb972b2f87fe7d5b06d37eac711490162d98de2c/docs/cli/gemini-md.md",
            "https://antigravity.google/docs/rules",
            "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions",
            "https://zed.dev/docs/ai/instructions",
        ),
        retrieved="2026-10-02",
    ),
    SharedRoot(
        path="~/.gemini/GEMINI.md",
        owner="antigravity",
        readers=("gemini-cli",),
        evidence=(
            "https://antigravity.google/docs/rules",
            "https://raw.githubusercontent.com/google-gemini/gemini-cli/fb972b2f87fe7d5b06d37eac711490162d98de2c/docs/cli/gemini-md.md",
        ),
        retrieved="2026-10-02",
    ),
    SharedRoot(
        path="<project>/.github/copilot-instructions.md",
        owner="github-copilot",
        readers=("zed",),
        evidence=(
            "https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions",
            "https://zed.dev/docs/ai/instructions",
        ),
        retrieved="2026-10-02",
    ),
)

# Instruction filenames that several vendors read under the same name. A
# registry target with one of these basenames is a shared root unless it sits
# under a directory only its own harness reads (listed here with the reason).
CROSS_TOOL_INSTRUCTION_FILES: frozenset[str] = frozenset(
    {"AGENTS.md", "CLAUDE.md", "GEMINI.md", "copilot-instructions.md"}
)
PRIVATE_INSTRUCTION_TARGETS: Mapping[str, str] = {
    "~/.codex/AGENTS.md": "Codex reads it from CODEX_HOME; no other registered "
    "harness documents loading this path.",
}
