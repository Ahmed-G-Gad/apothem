# SPDX-License-Identifier: MIT

"""Per-adapter profile-section DEPTH-fidelity wall.

A complement to the full-cohort two-profile DISTINCTNESS regression in
``test_profile_projection_fidelity.py``. Where that suite proves two distinct
profiles yield distinct output, this suite proves a single richly-populated
profile renders EACH projected section into each adapter's native surface, and
that a section an adapter has no native home for is gracefully omitted rather
than crashed or emitted as an empty stub.

The per-section support decision is anchored on the capability matrix
(``HARNESS_REGISTRY[*].capability_status``), not on the assumption that every
adapter renders every section:

- Identity and the profile-projection sections folded into the managed-block
  body (identity contact fields, preferences, rules, seriousness, enforcement,
  and the MCP server NAME reference) reach every adapter that projects an
  instruction/profile surface, so they are asserted present for all adapters.
- The native MCP server SPEC (the stdio command) is materialized only by
  adapters whose ``mcp_servers`` capability is ``native``; for every other
  adapter the spec is asserted absent (the omission contract), while the MCP
  server name may still appear as a managed-block reference.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.lib.harness_registry import HARNESS_REGISTRY, load_adapter_class

from .conftest import (
    BACKEND_PROVIDER_HARNESSES,
    POPULATED_SENTINELS,
    install_into_sandbox,
)

# The universal-section verbatim wall asserts an adapter PROJECTS the populated
# profile's managed-block body. Backend-provider harnesses (GLM) write a static
# backend config and project no profile content, so no universal section appears
# — the wall does not apply. The capability-anchored MCP tests below stay on the
# full registry: glm's all-``unsupported`` matrix satisfies their omission
# contract (no native MCP spec materialized) without exemption.
_RULE_BEARING_REGISTRY = [
    entry
    for entry in HARNESS_REGISTRY
    if entry.public_id not in BACKEND_PROVIDER_HARNESSES
]

# Sections projected into the managed-block body of every instruction/profile
# surface. Each maps to its sentinel key in POPULATED_SENTINELS. These are the
# universally-projected sections every adapter MUST carry verbatim.
_UNIVERSAL_SECTIONS: tuple[str, ...] = (
    "identity.name",
    "identity.role",
    "identity.email",
    "identity.website",
    "identity.github",
    "preferences.language",
    "preferences.style",
    "rules",
    "seriousness",
    "enforcement.label",
    "mcp.name",
)


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
    """Concatenate the text of every file materialized under *root*."""
    return "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    )


@pytest.mark.parametrize("entry", _RULE_BEARING_REGISTRY, ids=lambda e: e.public_id)
def test_universal_sections_render_verbatim(
    entry, populated_profile, tmp_path, monkeypatch
) -> None:
    """Every universally-projected section's sentinel appears verbatim.

    Every adapter projects an instruction/profile surface carrying the
    managed-block body, so the identity name (and the other folded sections)
    MUST appear verbatim in the rendered output. A profile-discarding adapter
    fails here: the assertion requires the exact sentinel value, so a render
    that drops or mangles a section cannot pass.
    """
    adapter = load_adapter_class(entry)()
    text = _all_text(_install(adapter, entry, tmp_path, populated_profile, monkeypatch))

    for section in _UNIVERSAL_SECTIONS:
        sentinel = POPULATED_SENTINELS[section]
        assert sentinel in text, (
            f"{entry.public_id}: section '{section}' not projected "
            f"(missing sentinel '{sentinel}')"
        )


@pytest.mark.parametrize("entry", HARNESS_REGISTRY, ids=lambda e: e.public_id)
def test_native_mcp_spec_present_only_when_supported(
    entry, populated_profile, tmp_path, monkeypatch
) -> None:
    """The native MCP server spec renders iff the adapter declares mcp native.

    Anchored on the capability matrix: an adapter whose ``mcp_servers`` status
    is ``native`` materializes the server's stdio command into its native
    config; every other adapter omits the native spec. The MCP server name may
    still appear as a managed-block reference in both cases, so this asserts on
    the command value (the native-spec marker), not the name.
    """
    adapter = load_adapter_class(entry)()
    text = _all_text(_install(adapter, entry, tmp_path, populated_profile, monkeypatch))

    command_sentinel = POPULATED_SENTINELS["mcp.command"]
    mcp_native = entry.capability_status["mcp_servers"] == "native"

    if mcp_native:
        assert command_sentinel in text, (
            f"{entry.public_id}: mcp native but server command spec "
            f"'{command_sentinel}' not materialized"
        )
    else:
        # Omission contract: the populated profile HAS an MCP server, but an
        # adapter with no native MCP home must not materialize the server spec.
        assert command_sentinel not in text, (
            f"{entry.public_id}: mcp not native but server command spec "
            f"'{command_sentinel}' leaked into output"
        )


@pytest.mark.parametrize("entry", HARNESS_REGISTRY, ids=lambda e: e.public_id)
def test_union_safe_no_wrong_value(
    entry, populated_profile, tmp_path, monkeypatch
) -> None:
    """A union-safe invariant for every projected section.

    For every section, IF its sentinel's distinguishing prefix appears anywhere
    in the adapter's output, the FULL sentinel value appears too - the render
    never carries a truncated or wrong value for a section it does project. This
    holds regardless of which sections a given adapter renders, so it guards
    even sections whose per-adapter support is not separately enumerated.
    """
    adapter = load_adapter_class(entry)()
    text = _all_text(_install(adapter, entry, tmp_path, populated_profile, monkeypatch))

    # Each sentinel carries the literal "sentinel" stem; a partial render would
    # surface the stem without the full distinctive value.
    for key, value in POPULATED_SENTINELS.items():
        if "sentinel" not in value.lower():
            continue
        # The unique suffix that distinguishes this section's value.
        distinctive = value.split("sentinel-", 1)[-1] if "sentinel-" in value else value
        if distinctive and distinctive != value and distinctive in text:
            assert value in text, (
                f"{entry.public_id}: section '{key}' rendered a partial/wrong "
                f"value (found fragment '{distinctive}' without full '{value}')"
            )


@pytest.mark.parametrize("entry", HARNESS_REGISTRY, ids=lambda e: e.public_id)
def test_omission_is_well_formed_not_stubbed(
    entry, populated_profile, tmp_path, monkeypatch
) -> None:
    """A populated section with no native home is omitted, not crashed or stubbed.

    Installing the populated fixture (which carries an MCP server) into an
    adapter whose ``mcp_servers`` status is not ``native`` renders a well-formed
    config: every JSON config file parses, no empty ``mcp`` / ``mcpServers``
    stub is written, and install raises no error. For native-MCP adapters the
    populated MCP key is permitted and carries the real server, never an empty
    stub.
    """
    import json

    adapter = load_adapter_class(entry)()
    sandbox = _install(adapter, entry, tmp_path, populated_profile, monkeypatch)

    mcp_native = entry.capability_status["mcp_servers"] == "native"

    for path in sandbox.rglob("*.json"):
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)  # well-formed: a parse failure raises here
        if not isinstance(data, dict):
            continue
        for mcp_key in ("mcp", "mcpServers"):
            if mcp_key not in data:
                continue
            value = data[mcp_key]
            # No empty stub in either case: an MCP key, if present, is non-empty.
            assert value, f"{entry.public_id}: empty '{mcp_key}' stub in {path.name}"
            if mcp_native:
                # The native key carries the real server, keyed by its name.
                assert POPULATED_SENTINELS["mcp.name"] in value, (
                    f"{entry.public_id}: native '{mcp_key}' present but missing "
                    f"server '{POPULATED_SENTINELS['mcp.name']}'"
                )
            else:
                pytest.fail(
                    f"{entry.public_id}: non-native adapter emitted an MCP key "
                    f"'{mcp_key}' in {path.name}"
                )
