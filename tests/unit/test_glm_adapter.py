# SPDX-License-Identifier: MIT

"""Unit tests for the glm harness adapter.

Protocol-conformance and install-smoke tests for the adapter. GLM (Z.ai) is a
model backend, not a coding-agent tool: the adapter writes a single
Apothem-owned TOML provider file and authors no coding-agent cohort.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
import yaml

import apothem.harnesses.glm as glm_pkg
from apothem.harnesses import HarnessAdapter
from apothem.harnesses.glm import GlmAdapter

_ADAPTER_DIR = Path(glm_pkg.__file__).resolve().parent


def _capabilities() -> dict[str, object]:
    return yaml.safe_load(
        (_ADAPTER_DIR / "capabilities.yml").read_text(encoding="utf-8")
    )


@pytest.fixture
def adapter() -> GlmAdapter:
    return GlmAdapter()


def test_protocol_conformance(adapter: GlmAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: GlmAdapter) -> None:
    assert adapter.name == "glm"


def test_output_path_is_path(adapter: GlmAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: GlmAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: GlmAdapter,
    tmp_path: Path,
) -> None:
    # Project-scope adapter: the target is resolved under --project.
    adapter.install({}, project=tmp_path)  # must not raise


def test_install_writes_provider_config(
    adapter: GlmAdapter,
    tmp_path: Path,
) -> None:
    # The Apothem-owned provider file lands at the resolved target and is
    # non-empty TOML carrying both backend base URLs.
    adapter.install({}, project=tmp_path)
    target = adapter.resolve_output_path(tmp_path)
    assert target.is_file()
    content = target.read_text(encoding="utf-8")
    assert "https://api.z.ai/api/anthropic" in content
    assert "https://api.z.ai/api/coding/paas/v4" in content


def test_provider_config_lists_the_documented_model_mapping_env(
    adapter: GlmAdapter,
    tmp_path: Path,
) -> None:
    # Z.ai documents the ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL variables
    # that map an Anthropic-compatible agent's model roles to GLM models
    # (https://docs.z.ai/devpack/tool/claude). The env table carries them as
    # placeholders: model ids are version-volatile, so none is pinned.
    # tomllib is stdlib from Python 3.11; the 3.10 floor skips the parse.
    tomllib = pytest.importorskip("tomllib")
    adapter.install({}, project=tmp_path)
    parsed = tomllib.loads(
        adapter.resolve_output_path(tmp_path).read_text(encoding="utf-8")
    )
    env = parsed["backends"]["anthropic_compatible"]["env"]
    for key in (
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    ):
        assert env[key] == "<GLM_MODEL_ID>", key
    assert {"ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "API_TIMEOUT_MS"} <= set(env)


def test_uninstall_noop_when_not_installed(adapter: GlmAdapter, tmp_path: Path) -> None:
    # No config file present under the project root -> uninstall is a noop.
    adapter.uninstall(project=tmp_path)  # must not raise when target absent


def test_uninstall_removes_provider_file(
    adapter: GlmAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Install the Apothem-owned provider file, uninstall, and assert the file is
    # gone and no whole-file .bak sibling is left in the project directory.
    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    adapter.install({}, project=tmp_path)
    target = adapter.resolve_output_path(tmp_path)
    assert target.is_file()

    adapter.uninstall(project=tmp_path)

    assert not target.exists()
    assert not list(target.parent.glob(f"{target.name}.*.bak"))


def test_capabilities_template_path_resolves_to_existing_file() -> None:
    # The declared system-prompt template must name a real on-disk template.
    capabilities = _capabilities()
    template_rel = capabilities["system_prompt_template_path"]
    assert isinstance(template_rel, str)
    assert (_ADAPTER_DIR / template_rel).is_file()


def test_capabilities_declares_no_mcp_surface() -> None:
    # GLM is a model backend; it hosts no MCP servers. The mcp_servers list is
    # empty, consistent with the registry's unsupported mcp_servers cell.
    capabilities = _capabilities()
    assert capabilities["mcp_servers"] == []


def test_capabilities_sub_agent_dispatch_is_false() -> None:
    # A model backend dispatches no sub-agents.
    capabilities = _capabilities()
    assert capabilities["sub_agent_dispatch"] is False


# --- ZCode and the model-mapping conflict -----------------------------------
#
# Z.ai ships a first-party coding tool, ZCode, which its documentation calls an
# "Agentic Development Environment". The adapter configures GLM as a model
# backend and must not say Z.ai has no coding tool of its own. Z.ai's guide to
# the Anthropic-compatible setup also contradicts itself on the role-to-model
# mapping, so the template keeps placeholders and flags the choice for the
# operator instead of picking a side.

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PIN = _ADAPTER_DIR / "STANDARD-CONVENTION-PIN.md"
_DOCS_PAGE = _REPO_ROOT / "site" / "content" / "docs" / "harnesses" / "glm.mdx"
_MANIFEST = _REPO_ROOT / "src" / "apothem" / "lib" / "propagation-manifest.yaml"
_FIRST_PARTY_SOURCES = (
    _ADAPTER_DIR / "__init__.py",
    _ADAPTER_DIR / "capabilities.yml",
    _ADAPTER_DIR / "templates" / "glm.toml",
    _PIN,
    _DOCS_PAGE,
)
# The three vendor statements that disagree, as they must appear in the
# template's TODO(clarify) comment and on the docs page.
_CONFLICTING_VALUES = (
    "glm-5.3[1m]",
    "glm-5.3-flash[1m]",
    "GLM-5.3-Flash",
    "1000000",
    "1048576",
)


def _glm_manifest_comment() -> str:
    """Return the comment lines that open the ``glm:`` manifest block."""
    lines = _MANIFEST.read_text(encoding="utf-8").splitlines()
    start = lines.index("  glm:") + 1
    comment: list[str] = []
    for line in lines[start:]:
        if not line.lstrip().startswith("#"):
            break
        comment.append(line)
    return "\n".join(comment)


@pytest.mark.parametrize("path", _FIRST_PARTY_SOURCES, ids=lambda path: path.name)
def test_adapter_text_does_not_deny_a_first_party_z_ai_coding_tool(path: Path) -> None:
    text = " ".join(path.read_text(encoding="utf-8").split())
    assert "ships no" not in text
    assert "not a first-party coding" not in text
    assert "not a coding tool of its own" not in text


def test_manifest_comment_does_not_deny_a_first_party_z_ai_coding_tool() -> None:
    comment = " ".join(_glm_manifest_comment().split())
    assert "ZCode" in comment
    assert "ships no" not in comment


@pytest.mark.parametrize(
    "path",
    [_ADAPTER_DIR / "templates" / "glm.toml", _PIN, _DOCS_PAGE],
    ids=lambda path: path.name,
)
def test_zcode_is_described_as_a_first_party_z_ai_tool(path: Path) -> None:
    text = " ".join(path.read_text(encoding="utf-8").split())
    assert "ZCode" in text
    assert "first-party coding tool" in text
    assert "Agentic Development Environment" in text


def test_pin_records_zcode_sources_and_a_current_snapshot() -> None:
    text = _PIN.read_text(encoding="utf-8")
    snapshot = re.search(r"^- Snapshot date: (\d{4}-\d{2}-\d{2})$", text, re.MULTILINE)
    assert snapshot is not None
    # The ZCode facts were recorded on 2026-10-24; a later refresh keeps them.
    assert date.fromisoformat(snapshot.group(1)) >= date(2026, 10, 24)
    assert "https://docs.z.ai/devpack/tool/zcode" in text
    assert "## Model Mapping Conflict" in text


def test_template_flags_the_conflicting_model_mapping_for_the_operator(
    adapter: GlmAdapter,
    tmp_path: Path,
) -> None:
    # The TODO(clarify) sits inside the anthropic_compatible env table, above
    # the three mapping variables, and names every conflicting vendor value.
    adapter.install({}, project=tmp_path)
    content = adapter.resolve_output_path(tmp_path).read_text(encoding="utf-8")
    table = content.index("[backends.anthropic_compatible.env]")
    todo = content.index("TODO(clarify)", table)
    first_mapping = content.index("ANTHROPIC_DEFAULT_OPUS_MODEL =", table)
    assert todo < first_mapping
    flagged = content[todo:first_mapping]
    for value in _CONFLICTING_VALUES:
        assert value in flagged, value


def test_docs_page_states_the_model_mapping_conflict_plainly() -> None:
    text = " ".join(_DOCS_PAGE.read_text(encoding="utf-8").split())
    assert "disagree" in text
    assert "does not choose between them" in text
    for value in _CONFLICTING_VALUES:
        assert value in text, value
