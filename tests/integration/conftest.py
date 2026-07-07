# SPDX-License-Identifier: MIT

"""Integration-suite fixtures.

The suite-wide ``sys.path`` bootstrap and the autouse install-ledger
isolation live in the root ``tests/conftest.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from apothem.harnesses import HarnessAdapter
from apothem.harnesses._shared import install_driver
from apothem.lib.harness_registry import HARNESS_REGISTRY, load_adapter_class

# Registry-derived adapter roster. Sourced from the authoritative
# ``HARNESS_REGISTRY`` (mirroring the registry-derived roster in
# ``test_clean_machine_install.py``) rather than a hand-maintained import list,
# so adding an adapter to the registry extends the parametrized parity coverage
# with no edit to this file. The count invariant is asserted in
# ``test_multi_harness_parity.py`` against ``SUPPORTED_HARNESS_COUNT``.
ALL_ADAPTERS: list[HarnessAdapter] = [
    load_adapter_class(entry)() for entry in HARNESS_REGISTRY
]

# Backend-provider harnesses: adapters that materialize a backend / model-routing
# config rather than rule-bearing instruction content. GLM (Z.ai) is a model
# BACKEND — an Anthropic-compatible or OpenAI-compatible coding agent is pointed
# at it by setting backend env vars — not a coding agent that consumes rules,
# preferences, or opted-in behaviors. Its adapter writes a static valid-TOML
# provider config via ``write_text`` and projects NO shared-profile content, so
# the rule-bearing-content contract walls (universal-section verbatim render,
# two-profiles-yield-distinct-output) do not apply: there is no profile content
# to render and two distinct profiles correctly yield identical backend config.
# These adapters are exempt from those rule-bearing contract assertions ONLY;
# every install / uninstall / verify / lifecycle / ownership contract still binds.
BACKEND_PROVIDER_HARNESSES: frozenset[str] = frozenset({"glm"})


def is_project_scope(adapter: HarnessAdapter) -> bool:
    """Return True when the adapter materializes under a project root."""
    return bool(getattr(adapter, "requires_project", False))


def install_into_sandbox(
    adapter: HarnessAdapter,
    sandbox: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    profile: dict[str, Any] | None = None,
    redirect_backup_root: bool = True,
) -> tuple[dict[str, Any], Path]:
    """Install *adapter* into *sandbox* and return ``(scope_kwargs, root)``.

    The single typed sandbox-install helper the integration suite shares. User-
    scope adapters expose an absolute ``output_path`` the install driver derives
    the harness root from; it is monkeypatched onto the sandbox. Project-scope
    adapters thread a ``project=`` keyword. The returned ``scope_kwargs`` is the
    per-scope keyword mapping the lifecycle methods (``update`` / ``verify`` /
    ``uninstall``) take, and ``root`` is the directory a file-set snapshot walks.

    ``redirect_backup_root`` controls whether ``install_driver.BACKUP_ROOT`` is
    redirected under the sandbox: the lifecycle parity suite redirects it so no
    real HOME backup state is touched, while the content-fidelity suites install
    with backups left at their default (each call site's original behavior is
    preserved — this flag never silently unifies the two).
    """
    if redirect_backup_root:
        monkeypatch.setattr(install_driver, "BACKUP_ROOT", sandbox / "backups")
    if is_project_scope(adapter):
        project = sandbox / "project"
        project.mkdir(parents=True, exist_ok=True)
        adapter.install({} if profile is None else profile, project=project)
        return {"project": project}, project
    # User-scope adapters derive their harness root from ``output_path.parent``
    # and write the primary config file at ``output_path``. Reuse the adapter's
    # real config basename so the manifest's ``${HARNESS_ROOT}/<basename>``
    # target coincides with the monkeypatched ``output_path`` — the harness root
    # becomes ``sandbox`` and the primary file lands where the lifecycle methods
    # look for it.
    target = sandbox / adapter.output_path.name
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({} if profile is None else profile)
    return {}, sandbox


# Distinctive, greppable sentinel value for every projected profile section.
# Each token is unique so a per-section fidelity assertion can prove the exact
# section reached the rendered surface (not a stale or wrong value). The MCP
# server name and its stdio command are deliberately distinct so the omission
# contract can separate "name appears as a managed-block reference" from "the
# native server spec was materialized".
POPULATED_SENTINELS: dict[str, str] = {
    "identity.name": "Zephyr-Sentinel-Name",
    "identity.role": "principal reliability engineer",
    "identity.email": "sentinel@fidelity.invalid",
    "identity.website": "https://sentinel.fidelity.invalid",
    "identity.github": "sentinel-handle",
    "preferences.language": "sentinel-lang-zig",
    "preferences.style": "verbose",
    "rules": "sentinel-rule-validate-input-before-write",
    "seriousness": "PUBLIC_LAUNCH",
    "enforcement.label": "Sprint apparatus",
    "mcp.name": "sentinel-mcp-srv",
    "mcp.command": "sentinel-mcp-cmd",
}


@pytest.fixture
def populated_profile() -> dict:
    """A schema-valid profile carrying a unique sentinel in every projected section.

    Every top-level projected section (identity with all contact fields,
    preferences, rules, seriousness, enforcement, mcp_servers) holds a
    distinctive greppable value drawn from ``POPULATED_SENTINELS``. The fixture
    validates against the packaged ``profile.schema.json`` before any test sees
    it, so a drift between this fixture and the schema fails loudly here rather
    than producing a misleading downstream fidelity failure.
    """
    from apothem.lib.profile import validate_profile

    profile: dict = {
        "identity": {
            "name": POPULATED_SENTINELS["identity.name"],
            "role": POPULATED_SENTINELS["identity.role"],
            "email": POPULATED_SENTINELS["identity.email"],
            "website": POPULATED_SENTINELS["identity.website"],
            "github": POPULATED_SENTINELS["identity.github"],
        },
        "preferences": {
            "language": POPULATED_SENTINELS["preferences.language"],
            "style": POPULATED_SENTINELS["preferences.style"],
        },
        "rules": [POPULATED_SENTINELS["rules"]],
        "seriousness": POPULATED_SENTINELS["seriousness"],
        "enforcement": {"sprints": True},
        "mcp_servers": {
            POPULATED_SENTINELS["mcp.name"]: {
                "transport": "stdio",
                "command": POPULATED_SENTINELS["mcp.command"],
            }
        },
    }
    # Fail loudly if the fixture drifts from the schema it must satisfy.
    validate_profile(profile)
    return profile
