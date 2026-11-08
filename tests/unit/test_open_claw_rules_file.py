# SPDX-License-Identifier: MIT

"""Tests for the Apothem rules file the open-claw install puts in each workspace.

OpenClaw's bundled ``bootstrap-extra-files`` hook loads extra files named like
its six workspace files, resolving each path in the workspace of the session
(https://docs.openclaw.ai/automation/hooks/bundled-hooks, read 2026-11-08). The
install writes ``apothem/AGENTS.md`` into every workspace it finds and names it
in the hook's entry; uninstall takes out only what it wrote.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.harnesses._shared.install_driver_jsonmerge import is_handler_map
from apothem.harnesses.open_claw import OpenClawAdapter
from apothem.harnesses.open_claw.install import install
from apothem.harnesses.open_claw.materializer import (
    HOOK_NAME,
    RULES_FILE_RELATIVE,
    plan_registration,
)
from apothem.harnesses.open_claw.rules_file import candidate_workspaces
from apothem.lib.harness_materializer import extract_managed_block

_AGENT_OWN = "# My agent\n\nNotes the agent keeps.\n"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway home directory; the adapter's output path resolves inside it."""
    root = tmp_path / "home"
    root.mkdir()
    monkeypatch.setenv("HOME", str(root))
    monkeypatch.setenv("USERPROFILE", str(root))
    monkeypatch.delenv("OPENCLAW_WORKSPACE_DIR", raising=False)
    return root


@pytest.fixture
def adapter() -> OpenClawAdapter:
    return OpenClawAdapter()


def _config_path(home: Path) -> Path:
    return home / ".openclaw" / "openclaw.json"


def _write_config(home: Path, doc: dict[str, object]) -> None:
    _config_path(home).parent.mkdir(exist_ok=True)
    _config_path(home).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _config(home: Path) -> dict[str, object]:
    return json.loads(_config_path(home).read_text(encoding="utf-8"))


def _workspace(path: Path) -> Path:
    """Create a workspace OpenClaw has set up: its seeded files exist."""
    path.mkdir(parents=True)
    (path / "AGENTS.md").write_text(_AGENT_OWN, encoding="utf-8")
    (path / "SOUL.md").write_text("soul\n", encoding="utf-8")
    return path


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _entry(home: Path) -> object:
    hooks = _config(home).get("hooks", {})
    return hooks.get("internal", {}).get("entries", {}).get(HOOK_NAME)  # type: ignore[union-attr]


def _messages(run: object) -> list[str]:
    return [result.message for result in run.results if result.outcome == "warning"]  # type: ignore[attr-defined]


def _skipped(run: object) -> list[str]:
    return [result.message for result in run.results if result.outcome == "skipped"]  # type: ignore[attr-defined]


# --- install ---------------------------------------------------------------------


def test_install_writes_the_rules_file_and_leaves_the_workspace_alone(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    before = _snapshot(workspace)

    adapter.install({})

    after = _snapshot(workspace)
    added = set(after) - set(before)
    assert added == {str(Path(RULES_FILE_RELATIVE))}
    assert {name: after[name] for name in before} == before
    text = (workspace / RULES_FILE_RELATIVE).read_text(encoding="utf-8")
    block = extract_managed_block(text)
    assert block is not None
    assert "apothem-rule-index.md" in block
    assert _entry(home) == {"enabled": True, "paths": [RULES_FILE_RELATIVE]}


def test_install_reaches_every_configured_workspace(
    adapter: OpenClawAdapter, home: Path
) -> None:
    default = _workspace(home / ".openclaw" / "workspace")
    own = _workspace(home / "work" / "research")
    implied = _workspace(home / ".openclaw" / "workspace-ops")
    _write_config(
        home,
        {
            "agents": {
                "entries": {
                    "research": {"workspace": "~/work/research"},
                    "ops": {},
                    "later": {},
                }
            }
        },
    )

    run = adapter.install({})

    for workspace in (default, own, implied):
        assert (workspace / RULES_FILE_RELATIVE).is_file()
    missing = home / ".openclaw" / "workspace-later"
    assert not missing.exists()
    assert any("workspace-later" in message for message in _skipped(run))
    assert not any("workspace-later" in message for message in _messages(run))


def test_install_writes_no_workspace_outside_the_home(
    adapter: OpenClawAdapter, home: Path, tmp_path: Path
) -> None:
    outside = _workspace(tmp_path / "elsewhere")
    _write_config(home, {"agents": {"defaults": {"workspace": str(outside)}}})

    run = adapter.install({})

    assert not (outside / RULES_FILE_RELATIVE).exists()
    assert any("outside the home directory" in message for message in _messages(run))


def test_install_does_not_create_a_workspace_openclaw_has_not_set_up(
    adapter: OpenClawAdapter, home: Path
) -> None:
    run = adapter.install({})

    assert not (home / ".openclaw" / "workspace").exists()
    assert any("does not exist yet" in message for message in _skipped(run))
    assert not any("does not exist yet" in message for message in _messages(run))
    assert _entry(home) == {"enabled": True, "paths": [RULES_FILE_RELATIVE]}


def test_dry_run_writes_nothing(adapter: OpenClawAdapter, home: Path) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    before = _snapshot(workspace)

    install(adapter.output_path, {}, dry_run=True)

    assert _snapshot(workspace) == before
    assert not _config_path(home).exists()


def test_update_rewrites_nothing_that_is_current(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    config = _config_path(home).read_bytes()
    rules = (workspace / RULES_FILE_RELATIVE).read_bytes()

    adapter.update({})

    assert _config_path(home).read_bytes() == config
    assert (workspace / RULES_FILE_RELATIVE).read_bytes() == rules


def test_update_restores_an_edited_block(adapter: OpenClawAdapter, home: Path) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    target = workspace / RULES_FILE_RELATIVE
    original = target.read_text(encoding="utf-8")
    target.write_text(original.replace("Apothem", "Edited", 1), encoding="utf-8")

    adapter.update({})

    assert target.read_text(encoding="utf-8") == original


# --- the hook entry and the operator's config ------------------------------------


_OPERATOR_HOOKS: dict[str, object] = {
    "gateway": {"port": 18789},
    "hooks": {
        "internal": {
            "entries": {"session-memory": {"enabled": True}},
            "load": {"extraDirs": []},
        },
        "gmail": {"account": "me"},
    },
}


@pytest.mark.parametrize(
    ("operator", "expected_entry"),
    [
        (_OPERATOR_HOOKS, {"enabled": True, "paths": [RULES_FILE_RELATIVE]}),
        (
            {
                "hooks": {
                    "internal": {"entries": {HOOK_NAME: {"paths": ["docs/AGENTS.md"]}}}
                }
            },
            {"paths": ["docs/AGENTS.md", RULES_FILE_RELATIVE]},
        ),
        (
            {
                "hooks": {
                    "internal": {
                        "entries": {HOOK_NAME: {"patterns": ["pkg/*/AGENTS.md"]}}
                    }
                }
            },
            {"patterns": ["pkg/*/AGENTS.md", RULES_FILE_RELATIVE]},
        ),
        (
            {
                "hooks": {
                    "internal": {
                        "enabled": True,
                        "entries": {
                            HOOK_NAME: {"enabled": True, "files": ["a/AGENTS.md"]}
                        },
                    }
                }
            },
            {"enabled": True, "files": ["a/AGENTS.md", RULES_FILE_RELATIVE]},
        ),
    ],
    ids=["other-hooks", "operator-paths", "operator-patterns", "operator-files"],
)
def test_install_joins_the_list_the_hook_reads_and_uninstall_restores_it(
    adapter: OpenClawAdapter,
    home: Path,
    operator: dict[str, object],
    expected_entry: dict[str, object],
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    _write_config(home, operator)

    adapter.install({})
    adapter.update({})

    assert _entry(home) == expected_entry
    assert adapter.verify()

    adapter.uninstall()

    assert _config(home) == operator
    assert not (workspace / "apothem").exists()
    assert (workspace / "AGENTS.md").read_text(encoding="utf-8") == _AGENT_OWN


def test_uninstall_deletes_a_config_apothem_created(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _workspace(home / ".openclaw" / "workspace")
    adapter.install({})

    adapter.uninstall()

    assert not _config_path(home).exists()


def test_uninstall_keeps_operator_text_beside_the_block(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    target = workspace / RULES_FILE_RELATIVE
    target.write_text(
        target.read_text(encoding="utf-8") + "\nMy own note.\n", encoding="utf-8"
    )

    adapter.uninstall()

    assert target.read_text(encoding="utf-8").strip() == "My own note."


@pytest.mark.parametrize(
    ("operator", "reason"),
    [
        (
            {"hooks": {"internal": {"enabled": False}}},
            "hooks.internal.enabled is false",
        ),
        (
            {"hooks": {"internal": {"entries": {HOOK_NAME: {"enabled": False}}}}},
            f"entries.{HOOK_NAME}.enabled is false",
        ),
        ({"hooks": {"internal": {"enabled": True}}}, "loads every eligible hook"),
    ],
    ids=["internal-hooks-off", "entry-off", "open-discovery"],
)
def test_install_leaves_the_operators_hook_choice_alone(
    adapter: OpenClawAdapter,
    home: Path,
    operator: dict[str, object],
    reason: str,
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    _write_config(home, operator)

    run = adapter.install({})
    adapter.update({})

    assert _config(home)["hooks"] == operator["hooks"]
    assert any(reason in message for message in _messages(run))
    assert (workspace / RULES_FILE_RELATIVE).is_file()
    assert adapter.verify()


def test_open_discovery_with_extra_hook_dirs_still_registers() -> None:
    config = {"hooks": {"internal": {"enabled": True, "load": {"extraDirs": ["~/h"]}}}}

    registration = plan_registration(config, apothem_entry=False)

    assert registration.entry == {"enabled": True, "paths": [RULES_FILE_RELATIVE]}


def test_an_entry_apothem_created_counts_as_absent() -> None:
    config = {
        "hooks": {
            "internal": {
                "enabled": True,
                "entries": {
                    HOOK_NAME: {"enabled": True, "paths": [RULES_FILE_RELATIVE]}
                },
            }
        }
    }

    assert plan_registration(config, apothem_entry=True).entry is None
    assert plan_registration(config, apothem_entry=False).entry == {
        "paths": [RULES_FILE_RELATIVE]
    }


def test_only_an_event_to_list_map_is_a_hook_handler_map() -> None:
    assert is_handler_map({"PreToolUse": [{"matcher": "*", "hooks": []}]})
    assert not is_handler_map({"internal": {"entries": {}}})


# --- OpenClaw's size limits --------------------------------------------------------


def test_a_file_over_the_per_file_limit_is_refused(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    _write_config(home, {"agents": {"defaults": {"bootstrapMaxChars": 200}}})

    run = adapter.install({})

    assert not (workspace / RULES_FILE_RELATIVE).exists()
    skipped = [
        r for r in run.results if r.outcome == "skipped" and "limit" in r.message
    ]
    assert skipped
    assert "bootstrapMaxChars" in skipped[0].message


def test_the_default_profile_fits_the_per_file_limit(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")

    adapter.install({})

    assert len((workspace / RULES_FILE_RELATIVE).read_text(encoding="utf-8")) < 20_000


def test_a_spent_total_budget_is_reported(adapter: OpenClawAdapter, home: Path) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    for name in ("AGENTS.md", "SOUL.md", "IDENTITY.md"):
        (workspace / name).write_text("x" * 20_000, encoding="utf-8")

    run = adapter.install({})

    assert (workspace / RULES_FILE_RELATIVE).is_file()
    assert any("skips the Apothem rules file" in m for m in _messages(run))


# --- verify ---------------------------------------------------------------------


def test_verify_reports_a_missing_rules_file_and_update_repairs_it(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    assert adapter.verify()

    (workspace / RULES_FILE_RELATIVE).unlink()
    assert not adapter.verify()

    adapter.update({})
    assert adapter.verify()


def test_verify_reports_a_workspace_created_after_install(
    adapter: OpenClawAdapter, home: Path
) -> None:
    adapter.install({})
    assert adapter.verify()

    _workspace(home / ".openclaw" / "workspace")
    assert not adapter.verify()


def test_verify_reports_a_removed_registration(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    config = _config(home)
    config["hooks"]["internal"]["entries"][HOOK_NAME]["paths"] = []  # type: ignore[index]
    _write_config(home, config)

    assert not adapter.verify()


# --- workspace resolution ----------------------------------------------------------


def test_workspaces_follow_openclaws_resolution(home: Path) -> None:
    config = {
        "agents": {
            "defaults": {"workspace": "~/agents"},
            "entries": {"a": {}, "b": {"workspace": "~/b-space"}},
        }
    }

    paths, notes = candidate_workspaces(config, home, env={})

    assert paths == [home / "agents", home / "agents" / "a", home / "b-space"]
    assert notes == []


def test_the_workspace_variable_moves_the_default_workspace(home: Path) -> None:
    paths, _ = candidate_workspaces(
        {}, home, env={"OPENCLAW_WORKSPACE_DIR": str(home / "ws")}
    )

    assert paths == [home / "ws"]


def test_update_keeps_an_entry_the_operator_turned_off_after_install(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    config = _config(home)
    config["hooks"]["internal"]["entries"][HOOK_NAME]["enabled"] = False  # type: ignore[index]
    _write_config(home, config)

    run = adapter.update({})

    assert _entry(home) == {"enabled": False}
    assert any("enabled is false" in message for message in _messages(run))

    adapter.uninstall()

    assert _config(home) == {
        "hooks": {"internal": {"entries": {HOOK_NAME: {"enabled": False}}}}
    }


def test_a_workspace_path_that_is_a_file_is_skipped(
    adapter: OpenClawAdapter, home: Path
) -> None:
    target = home / ".openclaw" / "workspace"
    target.parent.mkdir()
    target.write_text("not a folder\n", encoding="utf-8")

    run = adapter.install({})

    assert target.read_text(encoding="utf-8") == "not a folder\n"
    assert any("is not a folder" in message for message in _messages(run))


def test_an_entry_id_that_is_not_a_folder_name_names_no_workspace(home: Path) -> None:
    config = {"agents": {"entries": {"../../.ssh": {}, "ops": {}}}}

    paths, notes = candidate_workspaces(config, home, env={})

    assert paths == [
        home / ".openclaw" / "workspace",
        home / ".openclaw" / "workspace-ops",
    ]
    assert any("not a plain folder name" in note for note in notes)
