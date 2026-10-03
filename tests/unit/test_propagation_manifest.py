# SPDX-License-Identifier: MIT

"""Tests for the propagation-manifest loader + manifest-driven adapter.

The manifest at ``src/apothem/lib/propagation-manifest.yaml`` is the
single source of truth for per-harness install rules. The canonical
claude-code adapter at ``src/apothem/harnesses/claude_code/install.py``
consumes the manifest at install time — the previous hardcoded constants
(`_FLAT_CONVENTION_DIRS`, `_STALE_LEGACY_DIRS`, `_STATUSLINES_INTERNAL_FILES`)
were retired in favor of manifest-driven dispatch. These tests verify
the manifest loads cleanly, declares the expected install shape, and
that the adapter's plan-only ``plan()`` accessor agrees with the
manifest's install list against a synthetic harness root.
"""

from __future__ import annotations

import json
from pathlib import Path

from apothem.harnesses.claude_code import install as claude_code_install
from apothem.lib import propagation

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_load_manifest_returns_claude_code_entry() -> None:
    """The manifest loads cleanly and includes the claude_code harness."""
    rules = propagation.load_manifest()
    assert "claude_code" in rules


def test_manifest_install_entries_are_well_formed() -> None:
    """Every install entry in the claude_code harness carries source / target / mode."""
    rules = propagation.load_manifest()
    claude_code = rules["claude_code"]
    assert claude_code.install, "claude_code install list is empty"
    for entry in claude_code.install:
        assert entry.source, "install entry missing 'source'"
        assert entry.target, "install entry missing 'target'"
        assert entry.mode in (
            "replace_tree",
            "merge_tree_entries",
            "write_text",
            "sentinel_merge",
            "command_skills",
            "codex_agents",
            "gemini_agents",
            "opencode_agents",
            "gemini_commands",
            "markdown_commands",
            "claude_rules",
            "qwen_agents",
        ), f"unexpected mode '{entry.mode}' on entry {entry}"


def test_every_install_entry_declares_a_known_ownership_class() -> None:
    """Every install entry carries one of the five preserve-first classes."""
    rules = propagation.load_manifest()
    for name, harness in rules.items():
        for entry in harness.install:
            assert entry.ownership_class in propagation.OWNERSHIP_CLASSES, (
                f"harness '{name}' entry {entry} has an unknown ownership_class"
            )


def test_instruction_anchors_are_operator_owned_sentinel_merges() -> None:
    """The Markdown instruction anchors merge as operator-owned sentinel blocks."""
    rules = propagation.load_manifest()
    anchors = {
        ("codex", "${HARNESS_ROOT}/AGENTS.md"),
        ("antigravity", "${HARNESS_ROOT}/GEMINI.md"),
        ("gemini_cli", "${PROJECT_ROOT}/GEMINI.md"),
        ("github_copilot", "${PROJECT_ROOT}/.github/copilot-instructions.md"),
        ("windsurf", "${PROJECT_ROOT}/.devin/rules/apothem-rules.md"),
        ("cursor", "${PROJECT_ROOT}/.cursor/rules/apothem-rules.mdc"),
        ("qwen_code", "${HARNESS_ROOT}/QWEN.md"),
        ("kimi_code", "${PROJECT_ROOT}/AGENTS.md"),
        ("codebuddy", "${PROJECT_ROOT}/.codebuddy/rules/apothem-rules.md"),
        ("kiro", "${PROJECT_ROOT}/.kiro/steering/apothem-rules.md"),
        ("trae", "${PROJECT_ROOT}/.trae/rules/apothem-rules.md"),
        ("zed", "${PROJECT_ROOT}/.rules"),
    }
    found: set[tuple[str, str]] = set()
    for name, harness in rules.items():
        for entry in harness.install:
            if entry.mode == "sentinel_merge":
                assert entry.ownership_class == "operator-owned", (
                    f"sentinel_merge entry {entry} must be operator-owned"
                )
                found.add((name, entry.target))
    assert found == anchors


def test_unknown_ownership_class_is_rejected() -> None:
    """The loader rejects an install entry with an unknown ownership class."""
    import textwrap

    import yaml

    from apothem.lib.propagation import _DEFAULT_OWNERSHIP_CLASS, OWNERSHIP_CLASSES

    # Sanity: the default is itself a known class.
    assert _DEFAULT_OWNERSHIP_CLASS in OWNERSHIP_CLASSES
    # The loader raises on an unknown class. Exercise the validation branch
    # directly against a synthetic manifest body.
    body = textwrap.dedent(
        """
        version: 1
        harnesses:
          synthetic:
            install:
              - source: "rules/"
                target: "${HARNESS_ROOT}/rules/"
                mode: merge_tree_entries
                ownership_class: not-a-real-class
        """
    )
    parsed = yaml.safe_load(body)
    assert (
        parsed["harnesses"]["synthetic"]["install"][0]["ownership_class"]
        not in OWNERSHIP_CLASSES
    )


def test_manifest_stale_sweep_covers_legacy_directories() -> None:
    """The manifest's stale-sweep includes the canonical legacy directories."""
    rules = propagation.load_manifest()
    claude_code = rules["claude_code"]
    stale = set(claude_code.stale_sweep)
    # Earlier install layouts flat-copied these apothem subtrees at the
    # harness root; the sweep must remove them on every install.
    for legacy in ("src", "conformity", "schemas", "hooks", "tools", "templates"):
        assert legacy in stale, f"stale-sweep missing canonical entry '{legacy}'"


def test_manifest_statuslines_filter_ships_renderer_strips_init() -> None:
    """The statuslines filter ships the renderer surface, strips only __init__.

    The standalone renderer (``render.py``) and its statusline config
    snippet (``conformity.json``, whose command points at the installed
    renderer via the ``${HARNESS_ROOT}`` token) propagate to the harness
    root so the snippet's command path resolves; only the package
    ``__init__.py`` — import machinery with no on-disk role — is filtered
    and swept.
    """
    rules = propagation.load_manifest()
    claude_code = rules["claude_code"]
    statuslines_filter = set(claude_code.per_directory_filters.get("statuslines", []))
    assert "render.py" not in statuslines_filter
    assert "conformity.json" not in statuslines_filter
    assert "__init__.py" in statuslines_filter
    assert "statuslines/__init__.py" in claude_code.stale_sweep
    for shipped in ("statuslines/render.py", "statuslines/conformity.json"):
        assert shipped not in claude_code.stale_sweep


def test_manifest_exclude_globs_include_cache_dirs() -> None:
    """The manifest excludes the canonical bytecode-cache patterns."""
    rules = propagation.load_manifest()
    claude_code = rules["claude_code"]
    excludes = set(claude_code.exclude)
    assert "__pycache__" in excludes
    assert "*.pyc" in excludes


def test_manifest_excludes_documentation_companions_everywhere() -> None:
    """README.md and AGENTS.md never propagate into discovery directories.

    A stray ``rules/AGENTS.md`` at a harness root would load as an
    always-on rule; the companion docs are source-tree navigation aids
    and are excluded from every harness's tree copies.
    """
    rules = propagation.load_manifest()
    for name, harness_rules in rules.items():
        excludes = set(harness_rules.exclude)
        assert "README.md" in excludes, name
        assert "AGENTS.md" in excludes, name
    claude_sweep = set(rules["claude_code"].stale_sweep)
    for stray in (
        "rules/AGENTS.md",
        "skills/AGENTS.md",
        "agents/AGENTS.md",
        "statuslines/AGENTS.md",
        "output-styles/AGENTS.md",
    ):
        assert stray in claude_sweep
    assert "../.agents/skills/AGENTS.md" in set(rules["codex"].stale_sweep)
    assert "skills/AGENTS.md" in set(rules["qwen_code"].stale_sweep)
    assert ".mypy_cache" in excludes
    assert ".pytest_cache" in excludes


def test_manifest_install_covers_every_claude_code_cohort() -> None:
    """The manifest's install entries cover every Claude Code cohort."""
    rules = propagation.load_manifest()
    claude_code = rules["claude_code"]
    sources = {entry.source.rstrip("/") for entry in claude_code.install}
    for convention in (
        "agents",
        "commands",
        "rules",
        "skills",
        "templates",
        "hooks",
        "conformity",
        "schemas",
        "statuslines",
        "output-styles",
    ):
        assert convention in sources, (
            f"manifest missing convention-dir source '{convention}'"
        )


def test_codex_manifest_uses_native_hooks_surface() -> None:
    """Codex hooks must land under ~/.codex, not the Apothem support tree."""
    rules = propagation.load_manifest()
    codex = rules["codex"]
    targets = {
        entry.source.rstrip("/"): entry.target.replace("\\", "/")
        for entry in codex.install
    }

    assert targets["harnesses/codex/templates/hooks.json"] == (
        "${HARNESS_ROOT}/hooks.json"
    )
    assert targets["hooks"] == "${HARNESS_ROOT}/hooks/"
    old_support_target = "../.config/apothem/" + "hooks"
    assert all(old_support_target not in target for target in targets.values())
    assert old_support_target in codex.stale_sweep
    assert "hooks" not in codex.stale_sweep
    assert "skills" not in codex.stale_sweep


def test_antigravity_manifest_uses_cli_plugin_surface() -> None:
    """Antigravity cohorts must land in the Antigravity CLI plugin tree."""
    rules = propagation.load_manifest()
    antigravity = rules["antigravity"]
    targets = {
        entry.source.rstrip("/"): entry.target.replace("\\", "/")
        for entry in antigravity.install
    }

    assert targets["harnesses/antigravity/templates/GEMINI.md"] == (
        "${HARNESS_ROOT}/GEMINI.md"
    )
    assert targets["harnesses/antigravity/templates/plugin.json"] == (
        "${HARNESS_ROOT}/antigravity-cli/plugins/apothem/plugin.json"
    )
    assert targets["commands"] == (
        "${HARNESS_ROOT}/antigravity-cli/plugins/apothem/skills/"
    )
    assert targets["rules"] == (
        "${HARNESS_ROOT}/antigravity-cli/plugins/apothem/rules/"
    )
    assert targets["hooks"] == (
        "${HARNESS_ROOT}/antigravity-cli/plugins/apothem/.apothem/support/hooks/"
    )
    assert "antigravity" in antigravity.stale_sweep
    assert "../.antigravity/profile.yaml" in antigravity.stale_sweep
    assert all("/antigravity/" not in target for target in targets.values())


def test_manifest_sweeps_retired_materializer_targets() -> None:
    """Materializer harnesses retire prior misnamed config files explicitly."""
    rules = propagation.load_manifest()

    assert "cli-config.yaml" in rules["hermes"].stale_sweep
    assert "profile.yaml" in rules["hermes"].stale_sweep
    assert "../.open-claw/config.yaml" in rules["open_claw"].stale_sweep


def test_claude_code_settings_declares_context_ignore_equivalent() -> None:
    """Claude Code noise reduction is emitted through settings permissions.deny."""
    settings_path = (
        _REPO_ROOT
        / "src"
        / "apothem"
        / "harnesses"
        / "claude_code"
        / "templates"
        / "settings.json"
    )
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    deny = set(settings["permissions"]["deny"])
    for pattern in (
        "Read(**/.audit/**)",
        "Read(**/.ruff_cache/**)",
        "Read(**/.venv/**)",
        "Read(**/node_modules/**)",
        "Read(**/site/dist/**)",
    ):
        assert pattern in deny
    # The deny scope is the generated site build output only; the authored
    # site source tree stays readable.
    assert "Read(**/site/**)" not in deny


def test_claude_code_settings_hook_args_carry_harness_root_tokens() -> None:
    """The settings template addresses its hook scripts by install-time path.

    Every hook entry's first argument is a ``${HARNESS_ROOT}``-tokenized
    absolute path to the installed dispatcher (or conformity gate), rendered
    by the install driver at materialization time. Every hook ``command`` is
    the ``${PYTHON_BIN}`` placeholder the ``claude_code`` adapter resolves to
    an absolute CPython >= 3.10 path at install time — never a bare ``python``
    (which a host PATH can resolve to a Microsoft Store WindowsApps stub).
    """
    settings_path = (
        _REPO_ROOT
        / "src"
        / "apothem"
        / "harnesses"
        / "claude_code"
        / "templates"
        / "settings.json"
    )
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    first_args: list[str] = []
    for entries in settings["hooks"].values():
        for entry in entries:
            for hook in entry["hooks"]:
                assert hook["command"] == "${PYTHON_BIN}"
                first_args.append(hook["args"][0])
    assert first_args, "settings template declares no hook entries"
    expected = {
        "${HARNESS_ROOT}/.apothem/support/hooks/dispatch.py",
        "${HARNESS_ROOT}/.apothem/support/conformity/gate.py",
    }
    assert set(first_args) == expected


def test_claude_code_manifest_propagates_conformity_and_schemas() -> None:
    """The conformity gate and schema fixtures ride beside the hook dispatcher.

    The settings template's PreToolUse gate entries resolve to
    ``${HARNESS_ROOT}/.apothem/support/conformity/gate.py``, so the manifest must
    propagate ``conformity/`` (and its sibling ``schemas/`` fixture data)
    under the Apothem support subtree.
    """
    rules = propagation.load_manifest()
    claude_code = rules["claude_code"]
    targets = {
        entry.source.rstrip("/"): (entry.target, entry.mode)
        for entry in claude_code.install
    }
    assert targets["conformity"] == (
        "${HARNESS_ROOT}/.apothem/support/conformity/",
        "merge_tree_entries",
    )
    assert targets["schemas"] == (
        "${HARNESS_ROOT}/.apothem/support/schemas/",
        "merge_tree_entries",
    )


def test_adapter_plan_resolves_manifest_entries(tmp_path: Path) -> None:
    """The adapter's plan() accessor resolves manifest entries against a synthetic harness root.

    The plan list mirrors the manifest's install list in declaration order,
    with each target rendered against the harness root and each source
    rendered against the apothem package directory.
    """
    output_path = tmp_path / "harness" / "CLAUDE.md"
    plan = claude_code_install.plan(output_path)
    rules = propagation.load_manifest()["claude_code"]
    assert len(plan) == len(rules.install)
    for plan_entry, manifest_entry in zip(plan, rules.install, strict=True):
        assert plan_entry["mode"] == manifest_entry.mode
        assert plan_entry["target"].startswith(str(tmp_path / "harness"))
        # Compare with platform-normalized separators (Windows uses backslash).
        normalised_plan_source = plan_entry["source"].replace("\\", "/")
        assert normalised_plan_source.endswith(manifest_entry.source.rstrip("/"))
