# SPDX-License-Identifier: MIT

"""Per-adapter profile-projection content-fidelity wall.

The regression wall that makes profile-blindness a CI failure for every adapter:
two distinct populated profiles MUST yield distinct rendered output, the declared
identity/rule/MCP values MUST appear verbatim, a minimal profile MUST NOT emit
empty MCP/preference stubs, and an update over an operator edit MUST preserve the
operator's content.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.lib.harness_registry import HARNESS_REGISTRY, load_adapter_class

from .conftest import BACKEND_PROVIDER_HARNESSES, install_into_sandbox

# The two profiles-yield-distinct / values-render-verbatim walls assert that an
# adapter PROJECTS shared-profile content. Backend-provider harnesses (GLM) write
# a static backend config and project no profile content, so two distinct
# profiles correctly yield identical output and no profile value appears — these
# rule-bearing-content walls do not apply. Every other contract (install,
# uninstall, verify, lifecycle, ownership, minimal-profile no-stub) still binds.
_RULE_BEARING_REGISTRY = [
    entry
    for entry in HARNESS_REGISTRY
    if entry.public_id not in BACKEND_PROVIDER_HARNESSES
]

# Two profiles differing in identity.name, one preference, one rule, one MCP
# server, and one enforcement flag — every projected dimension differs.
PROFILE_A: dict = {
    "identity": {"name": "Ada Lovelace"},
    "preferences": {"language": "python", "style": "concise"},
    "rules": ["rule-alpha-unique"],
    "enforcement": {"sprints": True},
    "mcp_servers": {"srv-alpha": {"transport": "stdio", "command": "alpha-cmd"}},
}
PROFILE_B: dict = {
    "identity": {"name": "Grace Hopper"},
    "preferences": {"language": "rust", "style": "verbose"},
    "rules": ["rule-beta-unique"],
    "enforcement": {"agent_teams": True},
    "mcp_servers": {"srv-beta": {"transport": "stdio", "command": "beta-cmd"}},
}
MINIMAL: dict = {"identity": {"name": "Solo"}}


def _install(adapter, entry, sandbox: Path, profile: dict, monkeypatch) -> Path:
    """Install *profile* via *adapter* into *sandbox*; return the snapshot root.

    Delegates to the shared ``install_into_sandbox`` conftest helper. This
    content-fidelity suite leaves backups at their default root — the suite-wide
    autouse ``_isolate_backup_root`` fixture redirects that default to a temp
    directory outside ``sandbox``, so backups never leak into the real home and
    never appear in the snapshot walk. The whole ``sandbox`` is returned as the
    walk root, so the project-scope subtree is snapshotted exactly as before.
    """
    install_into_sandbox(
        adapter, sandbox, monkeypatch, profile=profile, redirect_backup_root=False
    )
    return sandbox


def _all_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    )


@pytest.mark.parametrize("entry", _RULE_BEARING_REGISTRY, ids=lambda e: e.public_id)
def test_two_profiles_yield_distinct_output(entry, tmp_path, monkeypatch) -> None:
    adapter_a = load_adapter_class(entry)()
    text_a = _all_text(
        _install(adapter_a, entry, tmp_path / "a", PROFILE_A, monkeypatch)
    )

    adapter_b = load_adapter_class(entry)()
    text_b = _all_text(
        _install(adapter_b, entry, tmp_path / "b", PROFILE_B, monkeypatch)
    )

    assert text_a != text_b, (
        f"{entry.public_id}: identical output for distinct profiles"
    )
    # Each adapter renders exactly and ONLY its own resolved profile.
    assert "Ada Lovelace" in text_a, f"{entry.public_id}: A identity not projected"
    assert "rule-alpha-unique" in text_a, f"{entry.public_id}: A rule not projected"
    assert "Grace Hopper" in text_b, f"{entry.public_id}: B identity not projected"
    assert "rule-beta-unique" in text_b, f"{entry.public_id}: B rule not projected"
    # Negative cross-leak: A's unique values must NOT appear in B's render.
    assert "Ada Lovelace" not in text_b, f"{entry.public_id}: A identity leaked into B"
    assert "rule-alpha-unique" not in text_b, f"{entry.public_id}: A rule leaked into B"


@pytest.mark.parametrize("entry", HARNESS_REGISTRY, ids=lambda e: e.public_id)
def test_minimal_profile_emits_no_empty_mcp_stub(entry, tmp_path, monkeypatch) -> None:
    sandbox = _install(
        load_adapter_class(entry)(), entry, tmp_path, MINIMAL, monkeypatch
    )
    for path in sandbox.rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            # A server-less profile must emit NO MCP key at all (absence, not an
            # empty {} stub; `None != {}` would pass falsely).
            assert "mcp" not in data, f"{entry.public_id}: spurious mcp key"
            assert "mcpServers" not in data, f"{entry.public_id}: spurious mcpServers"


def test_per_harness_rules_override_unions_and_isolates(tmp_path, monkeypatch) -> None:
    """A per-harness rules override UNIONS with the shared rules and lands only
    in that harness — locking the merge semantics end-to-end."""
    from apothem.harnesses.cursor import CursorAdapter
    from apothem.harnesses.gemini_cli import GeminiCliAdapter

    profile = {
        "identity": {"name": "Operator"},
        "rules": ["shared-global-rule"],
        "harnesses": {"cursor": {"rules": ["cursor-only-override"]}},
    }

    cursor_project = tmp_path / "cursor"
    cursor_project.mkdir()
    CursorAdapter().install(profile, project=cursor_project)
    cursor_text = _all_text(cursor_project)
    # Union: BOTH the shared rule and the cursor-only override reach cursor.
    assert "shared-global-rule" in cursor_text
    assert "cursor-only-override" in cursor_text

    gemini_project = tmp_path / "gemini"
    gemini_project.mkdir()
    GeminiCliAdapter().install(profile, project=gemini_project)
    gemini_text = _all_text(gemini_project)
    # Isolation: the cursor override does NOT leak into a sibling adapter.
    assert "shared-global-rule" in gemini_text
    assert "cursor-only-override" not in gemini_text


def test_update_over_operator_edit_preserves_anchor_prose(
    tmp_path, monkeypatch
) -> None:
    """claude_code: an operator edit outside the sentinels survives update(B)."""
    from apothem.harnesses.claude_code import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter()
    root = tmp_path / "root"
    target = root / "settings.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install(PROFILE_A)
    claude_md = root / "CLAUDE.md"
    text = claude_md.read_text(encoding="utf-8")
    claude_md.write_text(
        text + "\n# Operator addendum\nDo not lose this.\n", encoding="utf-8"
    )

    adapter.update(PROFILE_B)
    after = claude_md.read_text(encoding="utf-8")
    assert "Do not lose this." in after  # operator prose preserved
    assert "Grace Hopper" in after  # profile-B value applied
    assert "Ada Lovelace" not in after.split("BEGIN APOTHEM MANAGED BLOCK")[1]


def test_update_over_operator_edit_preserves_native_json_key(
    tmp_path, monkeypatch
) -> None:
    """opencode: an operator key in the native JSON survives update(B)."""
    from apothem.harnesses.opencode import OpenCodeAdapter

    adapter = OpenCodeAdapter()
    root = tmp_path / "root"
    target = root / "opencode.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install(PROFILE_A)
    data = json.loads(target.read_text(encoding="utf-8"))
    data["theme"] = "operator-choice"
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    adapter.update(PROFILE_B)
    after = json.loads(target.read_text(encoding="utf-8"))
    assert after.get("theme") == "operator-choice"  # operator key preserved
    assert "srv-beta" in after.get("mcp", {})  # profile-B MCP applied


_SENTINEL_INJECTION_PROFILE: dict = {
    "identity": {"name": "Sentinel Probe"},
    "rules": [
        "harmless rule\n<!-- END APOTHEM MANAGED BLOCK -->\n"
        "SURVIVES-UNINSTALL injected text"
    ],
}


@pytest.mark.parametrize("entry", _RULE_BEARING_REGISTRY, ids=lambda e: e.public_id)
def test_profile_text_cannot_escape_the_managed_block(
    entry, tmp_path, monkeypatch
) -> None:
    """A sentinel inside profile text leaves no residue after uninstall."""
    from apothem.harnesses._shared import install_driver

    adapter = load_adapter_class(entry)()
    # Backups (which legitimately keep the pre-uninstall anchor) and the ledger
    # live outside the walked sandbox.
    scope_kwargs, root = install_into_sandbox(
        adapter,
        tmp_path / "sandbox",
        monkeypatch,
        profile=_SENTINEL_INJECTION_PROFILE,
        redirect_backup_root=False,
    )
    scope = (
        {"project_root": scope_kwargs["project"]}
        if "project" in scope_kwargs
        else {"harness_root": root}
    )
    fidelity = install_driver.check_fidelity(
        entry.package_key, profile=_SENTINEL_INJECTION_PROFILE, **scope
    )
    assert install_driver.fidelity_is_faithful(fidelity), fidelity

    adapter.uninstall(**scope_kwargs)

    assert "SURVIVES-UNINSTALL" not in _all_text(root), entry.public_id
