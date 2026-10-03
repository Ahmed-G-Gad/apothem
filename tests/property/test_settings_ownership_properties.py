# SPDX-License-Identifier: MIT

"""Property tests: operator entries in settings files survive the lifecycle.

For every adapter that merges into a settings file the operator also edits
(Claude Code ``settings.json``, Codex ``hooks.json``, Qwen Code
``settings.json``, OpenCode ``opencode.json``, Open-Claw ``openclaw.json`` and
the Hermes ``config.yaml``), Hypothesis generates an operator config — scalar
keys, permission-style string lists that may include Apothem's own entries,
MCP server maps and foreign hook handlers — and checks:

* after ``install`` and after ``update``, every operator entry is still present
  with its value (list items kept, mapping entries kept);
* after ``uninstall``, the config parses to exactly the operator's seed;
* after ``install`` then ``rollback`` of that install, the file is
  byte-identical to the seed.

The adapters' own native-config and settings writers run unchanged. To keep a
few hundred lifecycle runs fast, the manifest's tree cohorts (agents, skills,
rules, hooks) are trimmed from the rules for the duration of each example: they
never touch the settings file under test.

``derandomize=True`` pins the inputs for deterministic CI runs; ``deadline=None``
removes per-example timing flakiness.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.lib import install_ledger
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class
from apothem.lib.propagation import HarnessRules

TEST_SETTINGS = settings(
    max_examples=12,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)

#: Harness id -> (config path under HOME, file format, the profile used).
_MCP_PROFILE: dict[str, Any] = {
    "mcp_servers": {"apothem-srv": {"transport": "stdio", "command": "apothem-cmd"}}
}
_TARGETS: dict[str, tuple[str, str]] = {
    "claude-code": (".claude/settings.json", "json"),
    "codex": (".codex/hooks.json", "json"),
    "qwen-code": (".qwen/settings.json", "json"),
    "opencode": (".config/opencode/opencode.json", "json"),
    "open-claw": (".openclaw/openclaw.json", "json"),
    "hermes": (".hermes/config.yaml", "yaml"),
}

# Keys the generated operator config may use. Template keys that carry a
# scalar Apothem overwrites (for example ``context.fileName``) are excluded so
# every generated entry is the operator's to keep; list and mapping keys the
# templates also use are included on purpose, because that is where the merge
# used to drop operator entries.
_SCALAR_KEYS = st.sampled_from(["model", "theme", "operatorFlag", "editor"])
_SCALARS = st.one_of(
    st.booleans(),
    st.integers(min_value=-5, max_value=5),
    st.text(alphabet="abcxyz-", min_size=1, max_size=6),
)
_RULES = st.lists(
    st.sampled_from(
        ["Read", "Glob", "Bash(npm test:*)", "Bash(curl:*)", "WebFetch", "Edit"]
    ),
    unique=True,
    max_size=4,
)
_SERVER_NAMES = st.lists(
    st.sampled_from(["mine", "team-db", "local-fs"]), unique=True, max_size=2
)
_FOREIGN_HANDLER = {
    "type": "command",
    "command": "python3 /srv/operator/hooks/dispatch.py --audit",
}


@st.composite
def _operator_config(draw: st.DrawFn, harness_id: str) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for key in draw(st.lists(_SCALAR_KEYS, unique=True, max_size=2)):
        config[key] = draw(_SCALARS)
    if harness_id == "claude-code":
        allow, deny = draw(_RULES), draw(_RULES)
        if allow or deny:
            config["permissions"] = {"allow": allow, "deny": deny}
    servers = {name: {"command": f"{name}-bin"} for name in draw(_SERVER_NAMES)}
    if servers:
        key = {
            "qwen-code": "mcpServers",
            "opencode": "mcp",
            "hermes": "mcp_servers",
        }.get(harness_id)
        if key == "mcp":
            servers = {
                name: {"type": "local", "command": [spec["command"]]}
                for name, spec in servers.items()
            }
        if key is not None:
            config[key] = servers
    if harness_id == "hermes" and draw(st.booleans()):
        config["auxiliary"] = {"compression": {"provider": "openrouter"}}
    if harness_id in {"claude-code", "codex", "qwen-code"} and draw(st.booleans()):
        matcher = {"claude-code": "Write", "codex": "Bash", "qwen-code": "^Bash$"}[
            harness_id
        ]
        config["hooks"] = {
            "PreToolUse": [{"matcher": matcher, "hooks": [dict(_FOREIGN_HANDLER)]}]
        }
    return config


def _dump(config: dict[str, Any], fmt: str) -> str:
    if fmt == "yaml":
        return yaml.safe_dump(config, sort_keys=False)
    return json.dumps(config, indent=2) + "\n"


def _load(path: Path, fmt: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(text) if fmt == "yaml" else json.loads(text)
    return loaded if isinstance(loaded, dict) else {}


def _contains(merged: object, seed: object) -> bool:
    """True when every operator entry of *seed* is present in *merged*."""
    if isinstance(seed, dict):
        return isinstance(merged, dict) and all(
            key in merged and _contains(merged[key], value)
            for key, value in seed.items()
        )
    if isinstance(seed, list):
        if not isinstance(merged, list):
            return False
        if all(isinstance(item, dict) for item in seed):
            # Hook matcher entries: the operator's handlers must survive.
            return all(
                any(_contains(candidate, item) for candidate in merged) for item in seed
            )
        return all(item in merged for item in seed)
    return merged == seed


def _settings_only(harness_name: str) -> HarnessRules:
    """The manifest rules minus the tree cohorts (see the module docstring)."""
    rules = _ORIGINAL_LOAD_RULES(harness_name)
    kept = [
        entry
        for entry in rules.install
        if entry.mode in {"write_text", "sentinel_merge"}
    ]
    return replace(rules, install=kept, stale_sweep=[])


_ORIGINAL_LOAD_RULES = install_driver.load_rules


def _run_lifecycle(harness_id: str, seed: dict[str, Any]) -> None:
    relative, fmt = _TARGETS[harness_id]
    entry = get_harness_entry(harness_id)
    seed_text = _dump(seed, fmt)
    with tempfile.TemporaryDirectory() as scratch, pytest.MonkeyPatch.context() as mp:
        home = Path(scratch) / "home"
        mp.setenv("HOME", str(home))
        mp.delenv("CODEX_HOME", raising=False)
        mp.setattr(install_driver, "load_rules", _settings_only)
        mp.setattr(install_driver, "BACKUP_ROOT", Path(scratch) / "backups")
        mp.setattr(install_ledger, "STATE_ROOT", Path(scratch) / "state")
        config = home / relative
        config.parent.mkdir(parents=True)
        config.write_text(seed_text, encoding="utf-8")
        adapter = load_adapter_class(entry)()

        adapter.install(_MCP_PROFILE)
        assert _contains(_load(config, fmt), seed), "install dropped an entry"
        adapter.update(_MCP_PROFILE)
        assert _contains(_load(config, fmt), seed), "update dropped an entry"
        adapter.uninstall()
        assert config.is_file(), "uninstall deleted the operator's file"
        assert _load(config, fmt) == seed, "uninstall changed operator entries"

        config.write_text(seed_text, encoding="utf-8")
        adapter.install(_MCP_PROFILE)
        record = install_ledger.current_install_record(
            entry.package_key, root=config.parent
        )
        assert record is not None
        result = CliRunner().invoke(
            main,
            [
                "rollback",
                "--harness",
                harness_id,
                "--install-id",
                record.install_id,
                "--yes",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        assert config.read_text(encoding="utf-8") == seed_text, "rollback differs"


@pytest.mark.parametrize("harness_id", sorted(_TARGETS))
def test_operator_entries_survive_the_lifecycle(harness_id: str) -> None:
    @TEST_SETTINGS
    @given(seed=_operator_config(harness_id))
    def run(seed: dict[str, Any]) -> None:
        _run_lifecycle(harness_id, seed)

    run()
