# SPDX-License-Identifier: MIT

"""Contract tests for the central harness registry."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from apothem.harnesses import HarnessAdapter
from apothem.lib import propagation
from apothem.lib.harness_registry import (
    HARNESS_REGISTRY,
    REQUIRED_CAPABILITIES,
    SUPPORTED_HARNESS_COUNT,
    SUPPORTED_HARNESS_IDS,
    SUPPORTED_PACKAGE_KEYS,
    load_adapter_class,
)
from apothem.schemas import profile_schema_path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_SRC_ROOT = _REPO_ROOT / "src" / "apothem"
_COMPATIBILITY_MATRIX = (
    _REPO_ROOT / "src" / "apothem" / "schemas" / ("compatibility-matrix.yaml")
)
_SITE_LANDING_PAGE = _REPO_ROOT / "site" / "app" / "page.tsx"
_BRANCH_POINTED_URL = re.compile(
    r"https?://[^\s)]+/(?:blob|tree)/(?:main|master|HEAD|trunk)(?:/|\b)"
)
_REQUIRED_PIN_FIELDS = (
    "- Snapshot date:",
    "- Adapter source:",
    "- Evidence level:",
    "## Recommended Postfix Rendering",
    "## Long Context and Compaction",
    "## Large-Codebase Practice Projection",
)


def _pyproject_harness_entry_points() -> dict[str, str]:
    pyproject = _PYPROJECT.read_text(encoding="utf-8")
    match = re.search(
        r'^\[project\.entry-points\."apothem\.harnesses"\]\n'
        r"(?P<body>.*?)(?=^\[)",
        pyproject,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    entries: dict[str, str] = {}
    for line in match.group("body").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        entries[key.strip()] = value.strip().strip('"')
    return entries


def _site_supported_tools() -> list[str]:
    """Parse the ``supportedTools`` array from the site landing page.

    Returns the ordered list of harness display names hardcoded in
    ``site/app/page.tsx``. The array is a single-quoted JavaScript string
    literal list; each entry is extracted by its quoted token.
    """
    source = _SITE_LANDING_PAGE.read_text(encoding="utf-8")
    block = re.search(
        r"const supportedTools = \[(?P<body>.*?)\];",
        source,
        flags=re.DOTALL,
    )
    assert block is not None, "supportedTools array not found in page.tsx"
    return re.findall(r"'([^']+)'", block.group("body"))


def test_registry_has_exactly_seventeen_unique_harnesses() -> None:
    assert len(HARNESS_REGISTRY) == SUPPORTED_HARNESS_COUNT == 17
    assert len(set(SUPPORTED_HARNESS_IDS)) == SUPPORTED_HARNESS_COUNT
    assert len(set(SUPPORTED_PACKAGE_KEYS)) == SUPPORTED_HARNESS_COUNT


def test_registry_matches_profile_schema_harness_ids() -> None:
    schema = yaml.safe_load(profile_schema_path().read_text(encoding="utf-8"))

    assert tuple(schema["$defs"]["harnessId"]["enum"]) == SUPPORTED_HARNESS_IDS
    assert tuple(schema["properties"]["harnesses"]["properties"]) == (
        SUPPORTED_HARNESS_IDS
    )


def test_registry_matches_pyproject_entry_points() -> None:
    assert _pyproject_harness_entry_points() == {
        entry.public_id: entry.entry_point for entry in HARNESS_REGISTRY
    }


def test_registry_matches_propagation_manifest_keys() -> None:
    manifest = propagation.load_manifest()
    assert set(manifest) == set(SUPPORTED_PACKAGE_KEYS)


def test_registry_declared_files_exist() -> None:
    for entry in HARNESS_REGISTRY:
        for path in (
            entry.docs_path,
            entry.comparison_docs_path,
            entry.capabilities_path,
            entry.standard_pin_path,
            *entry.fixture_tests,
        ):
            assert (_REPO_ROOT / path).is_file(), f"{entry.public_id}: {path}"


def test_registry_template_sources_exist_and_are_packaged() -> None:
    pyproject = _PYPROJECT.read_text(encoding="utf-8")
    for entry in HARNESS_REGISTRY:
        assert entry.package_data_key == f"apothem.harnesses.{entry.package_key}"
        assert f'"{entry.package_data_key}"' in pyproject
        for source in entry.template_sources:
            assert (_SRC_ROOT / source).is_file(), f"{entry.public_id}: {source}"


def test_registry_capability_matrix_is_complete() -> None:
    required = set(REQUIRED_CAPABILITIES)
    rationale_required = {"unsupported", "discovery-pending"}
    for entry in HARNESS_REGISTRY:
        assert set(entry.capability_status) == required
        missing_rationale = [
            name
            for name, status in entry.capability_status.items()
            if status in rationale_required and name not in entry.unsupported_rationale
        ]
        assert not missing_rationale, (
            f"{entry.public_id} lacks rationale for {missing_rationale}"
        )


def test_capabilities_files_agree_with_registry_contract() -> None:
    for entry in HARNESS_REGISTRY:
        capabilities = yaml.safe_load(
            (_REPO_ROOT / entry.capabilities_path).read_text(encoding="utf-8")
        )
        assert capabilities["standard_convention_pin"] == "STANDARD-CONVENTION-PIN.md"
        assert isinstance(capabilities["tool_surface_restrictions"], list)
        assert capabilities["tool_surface_restrictions"]

        dispatch_status = entry.capability_status["sub_agent_dispatch"]
        if dispatch_status == "unsupported":
            assert capabilities["sub_agent_dispatch"] is False
        else:
            assert capabilities["sub_agent_dispatch"] is True

        # capabilities.yml mcp_servers lists the harness's native MCP *surface*
        # (where MCP lives) — present whenever a file MCP surface exists, whether
        # apothem authors it ('native': opencode/qwen-code/hermes) or only names
        # the operator-owned surface ('discovery-pending'). It is empty only when
        # there is no file MCP surface at all (service/CLI state → unsupported /
        # not-applicable).
        if entry.capability_status["mcp_servers"] in {"native", "discovery-pending"}:
            assert capabilities["mcp_servers"]
        else:
            assert capabilities["mcp_servers"] == []


def test_compatibility_matrix_matches_registry_capabilities() -> None:
    matrix = yaml.safe_load(_COMPATIBILITY_MATRIX.read_text(encoding="utf-8"))
    rows = {row["name"]: row for row in matrix["harnesses"]}
    assert set(rows) == set(SUPPORTED_HARNESS_IDS)

    for entry in HARNESS_REGISTRY:
        row = rows[entry.public_id]
        status = entry.capability_status
        assert row["display"] == entry.display_name
        assert row["config_format"] == entry.output_format
        assert row["supports_hooks"] is (status["hooks"] == "native")
        assert row["supports_agents"] is (status["agents"] != "unsupported")
        assert row["supports_skills"] is (status["skills"] != "unsupported")
        assert row["supports_custom_rules"] is (status["rules"] != "unsupported")
        assert row["supports_output_styles"] is (status["output_styles"] == "native")
        assert row["supports_statuslines"] is (status["statuslines"] == "native")


def test_adapter_classes_match_registry_entries() -> None:
    for entry in HARNESS_REGISTRY:
        adapter = load_adapter_class(entry)()
        assert isinstance(adapter, HarnessAdapter)
        assert adapter.name == entry.public_id
        assert getattr(adapter, "requires_project", False) is (entry.scope == "project")


def test_standard_pins_carry_snapshot_and_adapter_source() -> None:
    for entry in HARNESS_REGISTRY:
        text = (_REPO_ROOT / entry.standard_pin_path).read_text(encoding="utf-8")
        assert "- Snapshot date:" in text
        assert f"- Adapter source: `src/apothem/harnesses/{entry.package_key}/`" in text


def test_standard_pins_carry_required_schema_fields() -> None:
    for entry in HARNESS_REGISTRY:
        text = (_REPO_ROOT / entry.standard_pin_path).read_text(encoding="utf-8")
        missing = [field for field in _REQUIRED_PIN_FIELDS if field not in text]
        assert not missing, f"{entry.public_id} pin missing fields: {missing}"


_DISCOVERY_TARGET = re.compile(
    r"^\s*-\s*Discovery target:\s*(?P<capability>[a-z_]+)\s+by\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2})\b",
    re.MULTILINE,
)


def test_every_discovery_pending_cell_has_a_dated_target_in_its_pin() -> None:
    # A discovery-pending cell is a promise to decide; the pin names the date.
    # scripts/dev/validate_harness_convention_pins.py fails once a date passes.
    mismatched = {}
    for entry in HARNESS_REGISTRY:
        text = (_REPO_ROOT / entry.standard_pin_path).read_text(encoding="utf-8")
        targets = [m.group("capability") for m in _DISCOVERY_TARGET.finditer(text)]
        pending = sorted(
            capability
            for capability, status in entry.capability_status.items()
            if status == "discovery-pending"
        )
        if sorted(targets) != pending:
            mismatched[entry.public_id] = {"pending": pending, "targets": targets}
    assert mismatched == {}


def test_standard_pins_do_not_use_branch_pointed_evidence_urls() -> None:
    for entry in HARNESS_REGISTRY:
        text = (_REPO_ROOT / entry.standard_pin_path).read_text(encoding="utf-8")
        assert not _BRANCH_POINTED_URL.search(text), (
            f"{entry.public_id} pin uses branch-pointed evidence"
        )


def test_site_supported_tools_match_registry_display_names() -> None:
    """The site landing page's hardcoded tool list must equal the registry.

    ``site/app/page.tsx`` hardcodes ``supportedTools`` as a display-name list;
    the registry is the source of truth. A drift (an adapter added to the
    registry but not the page, or vice versa) is a propagation failure caught
    here rather than at render time.
    """
    page_tools = _site_supported_tools()
    registry_names = [entry.display_name for entry in HARNESS_REGISTRY]
    assert len(page_tools) == len(set(page_tools)), "duplicate tool on page"
    assert set(page_tools) == set(registry_names), (
        f"page.tsx ↔ registry drift: "
        f"page-only={set(page_tools) - set(registry_names)}, "
        f"registry-only={set(registry_names) - set(page_tools)}"
    )
