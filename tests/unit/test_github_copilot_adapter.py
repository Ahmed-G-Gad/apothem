# SPDX-License-Identifier: MIT

"""Unit tests for the github-copilot harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import apothem.harnesses.github_copilot as github_copilot_pkg
from apothem.harnesses import HarnessAdapter
from apothem.harnesses.github_copilot import GitHubCopilotAdapter

_ADAPTER_DIR = Path(github_copilot_pkg.__file__).resolve().parent


def _capabilities() -> dict[str, object]:
    return yaml.safe_load(
        (_ADAPTER_DIR / "capabilities.yml").read_text(encoding="utf-8")
    )


@pytest.fixture
def adapter() -> GitHubCopilotAdapter:
    return GitHubCopilotAdapter()


def test_protocol_conformance(adapter: GitHubCopilotAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: GitHubCopilotAdapter) -> None:
    assert adapter.name == "github-copilot"


def test_output_path_is_path(adapter: GitHubCopilotAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: GitHubCopilotAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: GitHubCopilotAdapter,
    tmp_path: Path,
) -> None:
    # Project-scope adapter: the target is resolved under --project.
    adapter.install({}, project=tmp_path)  # must not raise


def test_uninstall_noop_when_not_installed(
    adapter: GitHubCopilotAdapter, tmp_path: Path
) -> None:
    # No config file present under the project root -> uninstall is a noop.
    adapter.uninstall(project=tmp_path)  # must not raise when target absent


def test_uninstall_strips_block_and_keeps_operator_prose(
    adapter: GitHubCopilotAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall: operator prose survives, the Apothem managed block
    # is removed, and no whole-file .bak sibling is left in the operator
    # directory (the pre-mutation file is backed up under the Apothem backup root).
    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    target = adapter.resolve_output_path(tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    operator_prose = "# Operator rules\n\nKeep my own guidance.\n"
    target.write_text(operator_prose, encoding="utf-8")

    adapter.install({}, project=tmp_path)
    assert "APOTHEM MANAGED BLOCK" in target.read_text(encoding="utf-8")

    adapter.uninstall(project=tmp_path)

    remainder = target.read_text(encoding="utf-8")
    assert "Keep my own guidance." in remainder
    assert "APOTHEM MANAGED BLOCK" not in remainder
    assert not list(target.parent.glob(f"{target.name}.*.bak"))


def test_capabilities_template_path_resolves_to_existing_file() -> None:
    # The declared system-prompt template must name a real on-disk template,
    # not a non-existent .j2 variant.
    capabilities = _capabilities()
    template_rel = capabilities["system_prompt_template_path"]
    assert isinstance(template_rel, str)
    assert (_ADAPTER_DIR / template_rel).is_file()


def test_capabilities_mcp_is_service_state_not_repo_file() -> None:
    # Copilot MCP lives in service/IDE state, not a repo-writable file, so the
    # adapter authors no MCP entries.
    capabilities = _capabilities()
    assert capabilities["mcp_servers"] == []


def test_capabilities_instructions_only_delivery() -> None:
    # The adapter delivers the repo-wide instructions anchor only; no
    # repo-config sub-agent dispatch is authored.
    capabilities = _capabilities()
    assert capabilities["sub_agent_dispatch"] is False


def test_profile_block_comes_first_in_the_managed_block(
    adapter: GitHubCopilotAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # GitHub's code-review guidance: shorter instruction files are more likely
    # to be fully processed. The operator's own profile is the part that must
    # not be cut, so it leads the Apothem block, ahead of the generic
    # governance text.
    from apothem.harnesses._shared import install_driver
    from apothem.lib.harness_materializer import extract_managed_block

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    profile = {
        "identity": {"name": "Ada Lovelace", "role": "maintainer"},
        "rules": ["Prefer explicit types"],
    }
    adapter.install(profile, project=tmp_path)
    block = extract_managed_block(
        adapter.resolve_output_path(tmp_path).read_text(encoding="utf-8")
    )
    assert block is not None
    profile_at = block.index("# Apothem Shared Profile")
    governance_at = block.index("## Engineering disciplines in force")
    assert profile_at < governance_at
    assert block.index("Ada Lovelace") < 1000
    assert block.index("Prefer explicit types") < 1000


def test_template_makes_no_stale_feature_claims() -> None:
    # Current GitHub docs (retrieved 2026-10-03) state no fixed character cap
    # for code review, and repository instructions do not apply to inline
    # code completions.
    text = (_ADAPTER_DIR / "templates" / "copilot-instructions.md").read_text(
        encoding="utf-8"
    )
    assert "4,000" not in text
    assert "completions" not in text
