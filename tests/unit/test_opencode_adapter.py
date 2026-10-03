# SPDX-License-Identifier: MIT

"""Unit tests for the opencode harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import apothem
import apothem.harnesses.opencode as opencode_pkg
import apothem.harnesses.opencode.materializer as opencode_materializer
from apothem.harnesses import HarnessAdapter
from apothem.harnesses.opencode import OpenCodeAdapter
from apothem.harnesses.opencode.materializer import (
    LEGACY_RULES_GLOB,
    always_on_rule_instructions,
)
from apothem.lib import install_ledger
from apothem.lib.frontmatter import field_value
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget

_ADAPTER_DIR = Path(opencode_pkg.__file__).resolve().parent


def _capabilities() -> dict[str, object]:
    return yaml.safe_load(
        (_ADAPTER_DIR / "capabilities.yml").read_text(encoding="utf-8")
    )


@pytest.fixture
def adapter() -> OpenCodeAdapter:
    return OpenCodeAdapter()


def test_protocol_conformance(adapter: OpenCodeAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: OpenCodeAdapter) -> None:
    assert adapter.name == "opencode"


def test_output_path_is_path(adapter: OpenCodeAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: OpenCodeAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: OpenCodeAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({})  # must not raise


def test_uninstall_noop_when_not_installed(
    adapter: OpenCodeAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nonexistent_config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: missing))
    adapter.uninstall()  # must not raise when output_path does not exist


def test_uninstall_keeps_operator_keys_and_strips_apothem(
    adapter: OpenCodeAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall of the materializer-rendered opencode.json: install,
    # add an operator key, uninstall, and assert the operator key survives while
    # Apothem's keys are stripped — with NO whole-file .bak sibling.
    import json

    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    target = tmp_path / "opencode.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({})
    installed = json.loads(target.read_text(encoding="utf-8"))
    assert "instructions" in installed  # Apothem-authored key
    installed["operatorKey"] = True
    target.write_text(json.dumps(installed, indent=2), encoding="utf-8")

    adapter.uninstall()

    assert target.is_file()  # operator content remains
    remaining = json.loads(target.read_text(encoding="utf-8"))
    assert remaining.get("operatorKey") is True
    assert "$schema" not in remaining
    assert "instructions" not in remaining
    assert not list(tmp_path.glob("opencode.json.*.bak"))


def test_capabilities_declare_native_mcp_and_subagent_dispatch() -> None:
    # OpenCode documents a top-level mcp block and subagent dispatch; the
    # config is rendered directly with no Jinja template (n/a template path).
    capabilities = _capabilities()
    assert capabilities["mcp_servers"]
    assert capabilities["sub_agent_dispatch"] is True
    assert capabilities["system_prompt_template_path"] == "n/a"


# --- Always-on instruction scope -------------------------------------------
#
# OpenCode combines every file its ``instructions`` list resolves to into every
# session (https://opencode.ai/docs/rules/). Only the rules whose frontmatter
# sets ``alwaysApply: true`` may be listed; the path-scoped rules stay installed
# for on-demand reading.

_RULES_SRC = Path(apothem.__file__).resolve().parent / "rules"


def _always_on_rules() -> tuple[int, set[str]]:
    """Return the byte total and file names of the ``alwaysApply`` rules."""
    total = 0
    names: set[str] = set()
    for path in sorted(_RULES_SRC.glob("*.md")):
        if path.name in {"README.md", "AGENTS.md"}:
            continue
        if (field_value(path, "alwaysApply") or "").strip().lower() == "true":
            total += path.stat().st_size
            names.add(path.name)
    return total, names


def _resolve_instruction(entry: str, home: Path) -> list[Path]:
    """Resolve one ``instructions`` entry as OpenCode does for a local path.

    ``~/`` expands against the home directory; an absolute path is matched as a
    glob on its final segment inside its parent directory (OpenCode's
    ``Instruction.systemPaths``). A relative entry resolves against the project
    directory, never the config file, so Apothem must not emit one.
    """
    assert not entry.startswith(("http://", "https://")), entry
    expanded = str(home / entry[2:]) if entry.startswith("~/") else entry
    path = Path(expanded)
    assert path.is_absolute(), f"relative instructions entry: {entry}"
    return sorted(match for match in path.parent.glob(path.name) if match.is_file())


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


def test_instructions_load_at_most_the_always_on_rule_bytes(
    adapter: OpenCodeAdapter, isolated_home: Path
) -> None:
    adapter.install({})

    config = json.loads(adapter.output_path.read_text(encoding="utf-8"))
    loaded = sorted(
        {
            match
            for entry in config["instructions"]
            for match in _resolve_instruction(entry, isolated_home)
        }
    )
    loaded_bytes = sum(path.stat().st_size for path in loaded)
    always_on_bytes, always_on_names = _always_on_rules()

    assert loaded_bytes <= always_on_bytes
    assert {path.name for path in loaded} == always_on_names
    # The path-scoped rules are still installed, for reading on demand.
    support_rules = adapter.output_path.parent / ".apothem" / "support" / "rules"
    installed = {path.name for path in support_rules.glob("*.md")}
    assert always_on_names < installed
    assert config["instructions"] == always_on_rule_instructions()


def _write_legacy_install(target: Path, config: dict[str, object]) -> None:
    """Write *config* plus the install record an earlier release left."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    install_ledger.append_record(
        LedgerRecord.create(
            harness="opencode",
            root=target.parent,
            kind="install",
            targets=(LedgerTarget(str(target), "write_text", "operator-owned"),),
        )
    )


def _legacy_config() -> dict[str, object]:
    return {
        "$schema": "https://opencode.ai/config.json",
        "instructions": ["CONTRIBUTING.md", LEGACY_RULES_GLOB],
        "model": "anthropic/operator-model",
    }


@pytest.mark.parametrize("action", ["install", "update"])
def test_install_and_update_replace_the_legacy_glob(
    adapter: OpenCodeAdapter, isolated_home: Path, action: str
) -> None:
    _write_legacy_install(adapter.output_path, _legacy_config())

    getattr(adapter, action)({})

    config = json.loads(adapter.output_path.read_text(encoding="utf-8"))
    assert config["instructions"] == [
        "CONTRIBUTING.md",
        *always_on_rule_instructions(),
    ]
    assert config["model"] == "anthropic/operator-model"


def test_update_drops_an_owned_legacy_glob(
    adapter: OpenCodeAdapter,
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An install that recorded ownership of the glob (it added it) loses it on
    # update; the operator's entry added afterwards survives.
    with monkeypatch.context() as patch:
        patch.setattr(
            opencode_materializer,
            "always_on_rule_instructions",
            lambda: [LEGACY_RULES_GLOB],
        )
        adapter.install({})
    config = json.loads(adapter.output_path.read_text(encoding="utf-8"))
    assert config["instructions"] == [LEGACY_RULES_GLOB]
    config["instructions"].append("CONTRIBUTING.md")
    adapter.output_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    adapter.update({})

    config = json.loads(adapter.output_path.read_text(encoding="utf-8"))
    assert config["instructions"] == [
        "CONTRIBUTING.md",
        *always_on_rule_instructions(),
    ]


def test_uninstall_removes_the_legacy_glob(
    adapter: OpenCodeAdapter, isolated_home: Path
) -> None:
    _write_legacy_install(adapter.output_path, _legacy_config())

    adapter.uninstall()

    remaining = json.loads(adapter.output_path.read_text(encoding="utf-8"))
    assert remaining == {
        "instructions": ["CONTRIBUTING.md"],
        "model": "anthropic/operator-model",
    }


def test_uninstall_removes_every_always_on_entry(
    adapter: OpenCodeAdapter, isolated_home: Path
) -> None:
    adapter.install({})
    config = json.loads(adapter.output_path.read_text(encoding="utf-8"))
    config["instructions"].insert(0, "CONTRIBUTING.md")
    adapter.output_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    adapter.uninstall()

    remaining = json.loads(adapter.output_path.read_text(encoding="utf-8"))
    assert remaining == {"instructions": ["CONTRIBUTING.md"]}
