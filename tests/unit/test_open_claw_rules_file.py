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
import sys
from pathlib import Path

import pytest

from apothem.harnesses._shared.install_driver import (
    MaterializationResult,
    check_fidelity,
)
from apothem.harnesses._shared.install_driver_jsonmerge import is_handler_map
from apothem.harnesses.open_claw import OpenClawAdapter, rules_file
from apothem.harnesses.open_claw.install import install
from apothem.harnesses.open_claw.materializer import (
    HOOK_NAME,
    MANUAL_ENTRY,
    RULES_FILE_RELATIVE,
    plan_registration,
)
from apothem.harnesses.open_claw.rules_file import (
    Limits,
    candidate_workspaces,
    chars,
    limits_for,
    operator_extras,
    used_chars,
)
from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_END,
    extract_managed_block,
)
from apothem.lib.profile import load_profile_file
from apothem.schemas import profile_minimal_path

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
    assert not any("workspace-later" in r.path for r in run.results)


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
    # Nothing to write is no pending change: no result names the workspace.
    assert not any(r.path.endswith(RULES_FILE_RELATIVE) for r in run.results)
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


def test_a_file_over_the_per_file_limit_is_neither_written_nor_registered(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    _write_config(home, {"agents": {"defaults": {"bootstrapMaxChars": 200}}})

    run = adapter.install({})

    assert not (workspace / RULES_FILE_RELATIVE).exists()
    assert _entry(home) is None
    assert any("bootstrapMaxChars" in message for message in _messages(run))


def test_a_file_that_no_longer_fits_loses_its_copy_and_its_registration(
    adapter: OpenClawAdapter, home: Path
) -> None:
    # A stale copy would stay loaded, and OpenClaw would cut its middle out.
    workspace = _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    config = _config(home)
    config["agents"] = {"defaults": {"bootstrapMaxChars": 200}}
    _write_config(home, config)

    run = adapter.update({})

    assert not (workspace / "apothem").exists()
    assert _entry(home) is None
    assert any("bootstrapMaxChars" in message for message in _messages(run))
    assert (workspace / "AGENTS.md").read_text(encoding="utf-8") == _AGENT_OWN


def test_an_entrys_own_limit_applies_to_its_workspace(
    adapter: OpenClawAdapter, home: Path
) -> None:
    small = _workspace(home / ".openclaw" / "workspace-small")
    large = _workspace(home / ".openclaw" / "workspace-large")
    _write_config(
        home,
        {
            "agents": {
                "entries": {"small": {"bootstrapMaxChars": 200}, "large": {}},
            }
        },
    )

    run = adapter.install({})

    assert not (small / RULES_FILE_RELATIVE).exists()
    assert (large / RULES_FILE_RELATIVE).is_file()
    assert _entry(home) == {"enabled": True, "paths": [RULES_FILE_RELATIVE]}
    assert any(
        "workspace-small" in r.path for r in run.results if r.outcome == "warning"
    )


def test_the_default_profile_fits_the_per_file_limit(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")

    adapter.install({})

    assert chars((workspace / RULES_FILE_RELATIVE).read_text(encoding="utf-8")) < 20_000


def test_a_spent_total_budget_refuses_the_file(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    for name in ("AGENTS.md", "SOUL.md", "IDENTITY.md"):
        (workspace / name).write_text("x" * 20_000, encoding="utf-8")

    run = adapter.install({})

    assert not (workspace / RULES_FILE_RELATIVE).exists()
    assert any("OpenClaw would skip it" in m for m in _messages(run))


def test_the_operators_extra_files_count_against_the_total(
    adapter: OpenClawAdapter, home: Path
) -> None:
    # The operator's own extra files load before Apothem's path.
    workspace = _workspace(home / ".openclaw" / "workspace")
    (workspace / "AGENTS.md").write_text("x" * 20_000, encoding="utf-8")
    (workspace / "SOUL.md").write_text("x" * 20_000, encoding="utf-8")
    (workspace / "docs").mkdir()
    (workspace / "docs" / "AGENTS.md").write_text("y" * 19_000, encoding="utf-8")
    operator = {
        "hooks": {"internal": {"entries": {HOOK_NAME: {"paths": ["docs/*.md"]}}}}
    }
    _write_config(home, operator)

    run = adapter.install({})

    assert not (workspace / RULES_FILE_RELATIVE).exists()
    assert any("other extra files" in m for m in _messages(run))


def test_size_is_counted_in_utf16_units_as_openclaw_counts() -> None:
    assert chars("a\U0001f600") == 3


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

    workspaces, notes = candidate_workspaces(config, home, env={})

    assert [(w.path, w.agent_ids) for w in workspaces] == [
        (home / "agents", ()),
        (home / "agents" / "a", ("a",)),
        (home / "b-space", ("b",)),
    ]
    assert notes == []


def test_a_sole_entry_uses_the_default_workspace_directly(home: Path) -> None:
    workspaces, _ = candidate_workspaces(
        {"agents": {"entries": {"main": {}}}}, home, env={}
    )

    assert [(w.path, w.agent_ids) for w in workspaces] == [
        (home / ".openclaw" / "workspace", ("main",))
    ]


def test_the_workspace_variable_moves_the_default_workspace(home: Path) -> None:
    workspaces, _ = candidate_workspaces(
        {}, home, env={"OPENCLAW_WORKSPACE_DIR": str(home / "ws")}
    )

    assert [w.path for w in workspaces] == [home / "ws"]


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


# --- workspaces that move, links, drift, commented configs ------------------------


def _move_default_workspace(home: Path, to: str) -> None:
    config = _config(home)
    config["agents"] = {"defaults": {"workspace": to}}
    _write_config(home, config)


def test_update_cleans_a_workspace_the_config_moved_away_from(
    adapter: OpenClawAdapter, home: Path
) -> None:
    old = _workspace(home / "ws-a")
    new = _workspace(home / "ws-b")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    assert (old / RULES_FILE_RELATIVE).is_file()

    _move_default_workspace(home, "~/ws-b")
    adapter.update({})

    assert not (old / "apothem").exists()
    assert (new / RULES_FILE_RELATIVE).is_file()
    assert (old / "AGENTS.md").read_text(encoding="utf-8") == _AGENT_OWN

    adapter.uninstall()

    assert not (new / "apothem").exists()
    assert _config(home) == {"agents": {"defaults": {"workspace": "~/ws-b"}}}


def test_uninstall_cleans_a_workspace_the_config_moved_away_from(
    adapter: OpenClawAdapter, home: Path
) -> None:
    old = _workspace(home / "ws-a")
    _workspace(home / "ws-b")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})

    _move_default_workspace(home, "~/ws-b")
    adapter.uninstall()

    assert not (old / "apothem").exists()


def test_cleaning_a_moved_workspace_keeps_the_operators_text(
    adapter: OpenClawAdapter, home: Path
) -> None:
    old = _workspace(home / "ws-a")
    _workspace(home / "ws-b")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    target = old / RULES_FILE_RELATIVE
    target.write_text(
        target.read_text(encoding="utf-8") + "\nMy own note.\n", encoding="utf-8"
    )

    _move_default_workspace(home, "~/ws-b")
    adapter.update({})

    assert target.read_text(encoding="utf-8").strip() == "My own note."


def test_a_dry_run_reports_a_cleanup_and_writes_nothing(
    adapter: OpenClawAdapter, home: Path
) -> None:
    old = _workspace(home / "ws-a")
    _workspace(home / "ws-b")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    _move_default_workspace(home, "~/ws-b")
    before = _snapshot(old)

    run = install(adapter.output_path, {}, dry_run=True)

    assert _snapshot(old) == before
    assert any(r.operation == "retire_anchor" and "ws-a" in r.path for r in run.results)


def _link_folder(link: Path, target: Path) -> None:
    """Create a folder link, a junction on Windows; skip where none can be made."""
    try:
        if sys.platform == "win32":
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
        else:
            link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError) as exc:
        pytest.skip(f"cannot create a folder link here: {exc}")


def test_a_linked_workspace_is_reported_once_and_left_alone(
    adapter: OpenClawAdapter, home: Path
) -> None:
    real = _workspace(home / "real-workspace")
    (home / ".openclaw").mkdir()
    _link_folder(home / ".openclaw" / "workspace", real)

    run = adapter.install({})

    assert not (real / "apothem").exists()
    linked = [m for m in _messages(run) if "through a link" in m]
    assert len(linked) == 1
    assert not any(r.outcome == "error" for r in run.results)
    assert adapter.verify()


def test_status_reports_an_edited_rules_file_as_drift(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    profile = load_profile_file(profile_minimal_path()).to_dict()
    adapter.install(profile)
    root = home / ".openclaw"

    def state() -> str:
        return next(
            r.status
            for r in check_fidelity("open_claw", harness_root=root, profile=profile)
            if r.target.endswith(str(Path(RULES_FILE_RELATIVE)))
        )

    assert state() == "faithful"
    target = workspace / RULES_FILE_RELATIVE
    target.write_text(
        target.read_text(encoding="utf-8").replace("Apothem", "Edited", 2),
        encoding="utf-8",
    )

    assert state() == "drifted"


_COMMENTED = '// mine\n{ skills: { load: { extraDirs: ["~/.openclaw/.apothem/support/skills"] } } }\n'


def test_update_on_a_commented_config_names_the_entry_to_add(
    adapter: OpenClawAdapter, home: Path
) -> None:
    # The skills entry was added by hand, as the earlier docs said; the hook
    # entry cannot be written without dropping the comments.
    workspace = _workspace(home / ".openclaw" / "workspace")
    _config_path(home).write_text(_COMMENTED, encoding="utf-8")

    run = adapter.update({})

    assert _config_path(home).read_text(encoding="utf-8") == _COMMENTED
    assert any(MANUAL_ENTRY in m for m in _messages(run))
    assert (workspace / RULES_FILE_RELATIVE).is_file()
    assert not adapter.verify()


def test_a_commented_config_with_the_entry_added_by_hand_verifies(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _workspace(home / ".openclaw" / "workspace")
    text = _COMMENTED.replace(
        " } } }\n", " } }, " + MANUAL_ENTRY.replace('"hooks":', "hooks:") + " }\n"
    )
    _config_path(home).write_text(text, encoding="utf-8")

    run = adapter.update({})

    assert _config_path(home).read_text(encoding="utf-8") == text
    assert not any("JSON5" in m for m in _messages(run))
    assert adapter.verify()


# --- findings from the adversarial verification ----------------------------------


def test_a_failed_cleanup_is_reported_and_retried_at_uninstall(
    adapter: OpenClawAdapter, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = _workspace(home / "ws-a")
    _workspace(home / "ws-b")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    _move_default_workspace(home, "~/ws-b")

    def stuck(path: Path, **_: object) -> MaterializationResult:
        return MaterializationResult("updated", "retire_anchor", str(path), "removed")

    with monkeypatch.context() as patch:
        patch.setattr(rules_file.install_driver, "strip_managed_anchor", stuck)
        run = adapter.update({})

    assert (old / RULES_FILE_RELATIVE).is_file()
    assert any("could not take the Apothem block out" in m for m in _messages(run))

    adapter.uninstall()

    assert not (old / "apothem").exists()


def test_a_file_the_total_refuses_everywhere_is_not_registered(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    _write_config(home, {"agents": {"defaults": {"bootstrapTotalMaxChars": 1000}}})

    adapter.install({})

    assert not (workspace / RULES_FILE_RELATIVE).exists()
    assert _entry(home) is None


def test_operator_text_beside_the_block_counts_against_the_limit(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    target = workspace / RULES_FILE_RELATIVE
    note = "n" * 19_000
    target.write_text(target.read_text(encoding="utf-8") + note, encoding="utf-8")

    run = adapter.update({})

    assert any("bootstrapMaxChars" in m for m in _messages(run))
    assert target.read_text(encoding="utf-8").strip() == note


def test_a_glob_that_matches_the_rules_file_does_not_count_it_twice(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    (workspace / "AGENTS.md").write_text("x" * 20_000, encoding="utf-8")
    (workspace / "SOUL.md").write_text("x" * 20_000, encoding="utf-8")
    operator = {
        "hooks": {"internal": {"entries": {HOOK_NAME: {"patterns": ["*/AGENTS.md"]}}}}
    }
    _write_config(home, operator)

    adapter.install({})
    adapter.update({})
    adapter.update({})

    assert (workspace / RULES_FILE_RELATIVE).is_file()


def test_line_endings_and_bad_bytes_count_as_openclaw_counts(home: Path) -> None:
    workspace = _workspace(home / "ws")
    (workspace / "AGENTS.md").write_bytes(b"a\r\nb\r\n")
    (workspace / "SOUL.md").write_bytes(b"\xff\xfe\xfd")
    (workspace / "IDENTITY.md").write_text("\U0001f600", encoding="utf-8")

    used = used_chars({}, workspace, Limits())

    marker = chars(f"[MISSING] Expected at: {workspace / 'BOOTSTRAP.md'}")
    assert used == 6 + 3 + 2 + marker


def test_a_missing_workspace_file_counts_its_placeholder(home: Path) -> None:
    workspace = home / "ws"
    workspace.mkdir()

    used = used_chars({}, workspace, Limits())

    assert used == sum(
        chars(f"[MISSING] Expected at: {workspace / name}")
        for name in ("AGENTS.md", "SOUL.md", "IDENTITY.md", "BOOTSTRAP.md")
    )


def test_brace_patterns_count_and_brackets_stay_literal(home: Path) -> None:
    workspace = _workspace(home / "ws")
    for folder in ("docs", "notes", "[x]"):
        (workspace / folder).mkdir()
        (workspace / folder / "AGENTS.md").write_text("abc", encoding="utf-8")
    paths = ["{docs,notes}/AGENTS.md", "[x]/AGENTS.md"]
    config = {"hooks": {"internal": {"entries": {HOOK_NAME: {"paths": paths}}}}}

    extras = operator_extras(config, workspace)

    assert sorted(path.parent.name for path in extras) == ["[x]", "docs", "notes"]


def test_an_invalid_entry_limit_falls_back_as_openclaw_does() -> None:
    config = {
        "agents": {
            "defaults": {"bootstrapMaxChars": 500},
            "entries": {"a": {"bootstrapMaxChars": 0}, "b": {}},
        }
    }

    assert limits_for(config, ["a"]).file_max == 20_000
    assert limits_for(config, ["b"]).file_max == 500


def test_a_rules_file_overwritten_with_non_utf8_bytes_is_left_alone(
    adapter: OpenClawAdapter, home: Path
) -> None:
    old = _workspace(home / "ws-a")
    _workspace(home / "ws-b")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    (old / RULES_FILE_RELATIVE).write_bytes(b"\xff\xfe not text")
    _move_default_workspace(home, "~/ws-b")

    adapter.update({})
    # It holds no Apothem block any more, so it is not Apothem's to remove.
    adapter.uninstall()

    assert (old / RULES_FILE_RELATIVE).read_bytes() == b"\xff\xfe not text"


def test_a_comment_added_after_install_does_not_break_update(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    text = "// mine\n" + _config_path(home).read_text(encoding="utf-8")
    _config_path(home).write_text(text, encoding="utf-8")

    run = adapter.update({})

    assert _config_path(home).read_text(encoding="utf-8") == text
    assert not any("JSON5" in m for m in _messages(run))
    assert adapter.verify()


def test_the_commented_config_warning_names_the_list_the_operator_uses(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _workspace(home / ".openclaw" / "workspace")
    hooks = (
        f'hooks: {{ internal: {{ entries: {{ "{HOOK_NAME}": '
        '{ patterns: ["docs/AGENTS.md"] } } } }'
    )
    text = (
        "// mine\n"
        '{ skills: { load: { extraDirs: ["~/.openclaw/.apothem/support/skills"] } }, '
        f"{hooks} }}\n"
    )
    _config_path(home).write_text(text, encoding="utf-8")

    run = adapter.update({})

    assert any("to the `patterns` list" in m for m in _messages(run))
    assert _config_path(home).read_text(encoding="utf-8") == text


def test_a_workspace_that_became_a_link_is_left_alone_without_errors(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    moved = workspace / "apothem-real"
    (workspace / "apothem").rename(moved)
    _link_folder(workspace / "apothem", moved)

    run = adapter.update({})

    assert not any(r.outcome == "error" for r in run.results)
    assert (moved / "AGENTS.md").is_file()


def test_a_workspace_inside_another_never_gets_its_own_agents_file_changed(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _workspace(home / "agents")
    inner = _workspace(home / "agents" / "apothem")
    entries = {"apothem": {}, "x": {}}
    _write_config(
        home, {"agents": {"defaults": {"workspace": "~/agents"}, "entries": entries}}
    )

    run = adapter.install({})

    assert (inner / "AGENTS.md").read_text(encoding="utf-8") == _AGENT_OWN
    assert any("holds another workspace" in m for m in _messages(run))
    assert (inner / RULES_FILE_RELATIVE).is_file()


# --- second verification round ------------------------------------------------------


def test_an_absolute_or_drive_pattern_does_not_crash_the_install(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    patterns = ["/etc/*/AGENTS.md", "C:/x/*/AGENTS.md", "C:*.md"]
    operator = {"hooks": {"internal": {"entries": {HOOK_NAME: {"paths": patterns}}}}}
    _write_config(home, operator)

    adapter.install({})

    assert (workspace / RULES_FILE_RELATIVE).is_file()


def test_nested_brace_groups_are_expanded(home: Path) -> None:
    workspace = _workspace(home / "ws")
    for folder in ("docs", "a", "b"):
        (workspace / folder).mkdir()
        (workspace / folder / "SOUL.md").write_text("abc", encoding="utf-8")
    paths = ["{docs,{a,b}}/SOUL.md"]
    config = {"hooks": {"internal": {"entries": {HOOK_NAME: {"paths": paths}}}}}

    extras = operator_extras(config, workspace)

    assert sorted(path.parent.name for path in extras) == ["a", "b", "docs"]


def test_an_uninstall_that_cannot_clean_a_file_fails_and_keeps_the_record(
    adapter: OpenClawAdapter, home: Path
) -> None:
    old = _workspace(home / "ws-a")
    _workspace(home / "ws-b")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    moved = old / "apothem-real"
    (old / "apothem").rename(moved)
    _link_folder(old / "apothem", moved)
    _move_default_workspace(home, "~/ws-b")

    run = adapter.uninstall()

    assert any(r.detail.get("blocked") for r in run.results)
    assert (moved / "AGENTS.md").is_file()
    assert install_ledger.active_install_records("open_claw", root=home / ".openclaw")


def test_an_apothem_entry_edited_in_a_commented_config_does_not_break_update(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    config = _config(home)
    config["hooks"]["internal"]["entries"][HOOK_NAME]["note"] = "mine"  # type: ignore[index]
    text = "// mine\n" + json.dumps(config, indent=2) + "\n"
    _config_path(home).write_text(text, encoding="utf-8")

    adapter.update({})

    assert _config_path(home).read_text(encoding="utf-8") == text


def test_with_no_usable_workspace_the_warning_does_not_blame_the_limits(
    adapter: OpenClawAdapter, home: Path
) -> None:
    real = _workspace(home / "real")
    (home / ".openclaw").mkdir()
    _link_folder(home / ".openclaw" / "workspace", real)

    run = adapter.install({})

    assert not any("fits no workspace" in m for m in _messages(run))
    assert adapter.verify()


def test_a_missing_workspace_too_small_in_total_is_not_registered(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _write_config(home, {"agents": {"defaults": {"bootstrapTotalMaxChars": 500}}})

    adapter.install({})

    assert _entry(home) is None


def test_a_folder_where_the_rules_file_goes_is_skipped_with_a_note(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    (workspace / RULES_FILE_RELATIVE).mkdir(parents=True)

    run = adapter.install({})

    assert not any(r.outcome == "error" for r in run.results)
    assert any("is not a file" in m for m in _messages(run))


def test_the_limit_message_names_the_operators_own_text(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    target = workspace / RULES_FILE_RELATIVE
    target.write_text(
        target.read_text(encoding="utf-8") + "n" * 19_000, encoding="utf-8"
    )

    run = adapter.update({})

    assert any("text you keep beside the Apothem block" in m for m in _messages(run))


# --- second review ----------------------------------------------------------------


def test_the_uninstall_command_fails_when_a_rules_file_cannot_be_cleaned(
    adapter: OpenClawAdapter, home: Path
) -> None:
    from click.testing import CliRunner

    from apothem.cli import main

    old = _workspace(home / "ws-a")
    _workspace(home / "ws-b")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    moved = old / "apothem-real"
    (old / "apothem").rename(moved)
    _link_folder(old / "apothem", moved)
    _move_default_workspace(home, "~/ws-b")

    result = CliRunner().invoke(main, ["uninstall", "--harness", "open-claw", "--yes"])

    assert result.exit_code == 2, result.output
    assert "through" in result.output
    assert "link" in result.output


def _commented(home: Path, doc: dict[str, object]) -> str:
    text = "// mine\n" + json.dumps(doc, indent=2) + "\n"
    _config_path(home).parent.mkdir(exist_ok=True)
    _config_path(home).write_text(text, encoding="utf-8")
    return text


@pytest.mark.parametrize(
    "change",
    [
        {"agents": {"defaults": {"bootstrapMaxChars": 300}}},
        {"internal-enabled": False},
        {"entry-enabled": False},
        {"internal-enabled": True},
    ],
    ids=["over-limit", "internal-hooks-off", "entry-off", "open-discovery"],
)
def test_a_commented_config_never_breaks_update_whatever_else_applies(
    adapter: OpenClawAdapter, home: Path, change: dict[str, object]
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    config = _config(home)
    internal = config["hooks"]["internal"]  # type: ignore[index]
    if "internal-enabled" in change:
        internal["enabled"] = change["internal-enabled"]  # type: ignore[index]
    elif "entry-enabled" in change:
        internal["entries"][HOOK_NAME]["enabled"] = change["entry-enabled"]  # type: ignore[index]
    else:
        config.update(change)
    text = _commented(home, config)

    run = adapter.update({})

    assert _config_path(home).read_text(encoding="utf-8") == text
    assert any("remove it there by hand" in m for m in _messages(run))
    if "agents" in change:
        assert not (workspace / RULES_FILE_RELATIVE).exists()


def test_uninstall_names_entries_left_in_a_commented_config(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    text = _commented(home, _config(home))

    run = adapter.uninstall()

    assert [r.outcome for r in run.results] == ["error"]
    assert "by hand" in run.results[0].message
    # Nothing else ran: the file, its comment and the support tree stay.
    assert _config_path(home).read_text(encoding="utf-8") == text
    assert (home / ".openclaw" / ".apothem" / "support").is_dir()
    assert install_ledger.active_install_records("open_claw", root=home / ".openclaw")


def test_entry_ids_are_normalized_as_openclaw_does(home: Path) -> None:
    config = {"agents": {"entries": {"Bob Smith": {}, "../../.ssh": {}}}}

    workspaces, _ = candidate_workspaces(config, home, env={})

    assert [w.path for w in workspaces] == [
        home / ".openclaw" / "workspace",
        home / ".openclaw" / "workspace-bob-smith",
        home / ".openclaw" / "workspace-ssh",
    ]


def test_the_older_agents_list_roster_is_read(home: Path) -> None:
    config = {
        "agents": {"list": [{"id": "ops", "workspace": "~/ops"}, {"id": "dev"}, "junk"]}
    }

    workspaces, _ = candidate_workspaces(config, home, env={})

    assert [(w.path, w.agent_ids) for w in workspaces] == [
        (home / ".openclaw" / "workspace", ()),
        (home / "ops", ("ops",)),
        (home / ".openclaw" / "workspace-dev", ("dev",)),
    ]


def test_an_entry_marked_default_owns_the_default_workspace(home: Path) -> None:
    config = {
        "agents": {
            "entries": {
                "main": {"default": True, "bootstrapMaxChars": 900},
                "ops": {},
            }
        }
    }

    workspaces, _ = candidate_workspaces(config, home, env={})

    assert [(w.path, w.agent_ids) for w in workspaces] == [
        (home / ".openclaw" / "workspace", ("main",)),
        (home / ".openclaw" / "workspace-ops", ("ops",)),
    ]
    assert limits_for(config, workspaces[0].agent_ids).file_max == 900


def test_explicit_ownership_ignores_the_default_marker(home: Path) -> None:
    config = {
        "agents": {
            "ownership": "explicit",
            "entries": {"main": {"default": True}, "ops": {}},
        }
    }

    workspaces, _ = candidate_workspaces(config, home, env={})

    assert workspaces[1].path == home / ".openclaw" / "workspace-main"


def test_a_fractional_limit_is_floored_as_openclaw_does() -> None:
    config = {"agents": {"defaults": {"bootstrapMaxChars": 0.5}}}

    assert limits_for(config, []).file_max == 0


def test_a_linked_rules_file_emptied_by_hand_no_longer_blocks_uninstall(
    adapter: OpenClawAdapter, home: Path
) -> None:
    old = _workspace(home / "ws-a")
    _workspace(home / "ws-b")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    moved = old / "apothem-real"
    (old / "apothem").rename(moved)
    _link_folder(old / "apothem", moved)
    _move_default_workspace(home, "~/ws-b")
    first = adapter.uninstall()
    assert any(
        r.detail.get("blocked") and "through a link" in r.message for r in first.results
    )

    (moved / "AGENTS.md").write_text("", encoding="utf-8")
    adapter.uninstall()

    assert not install_ledger.active_install_records(
        "open_claw", root=home / ".openclaw"
    )


# --- third verification round -------------------------------------------------------


def test_a_commented_config_stops_uninstall_before_any_rules_file_changes(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    rules = (workspace / RULES_FILE_RELATIVE).read_bytes()
    _commented(home, _config(home))

    run = adapter.uninstall()

    assert any(r.outcome == "error" and "by hand" in r.message for r in run.results)
    assert (workspace / RULES_FILE_RELATIVE).read_bytes() == rules


def test_a_commented_file_apothem_created_keeps_its_comment_after_the_hand_fix(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    config = _config(home)
    config["skills"]["load"]["extraDirs"] = []  # type: ignore[index]
    config["hooks"]["internal"]["entries"] = {}  # type: ignore[index]
    text = _commented(home, config)

    adapter.uninstall()

    assert _config_path(home).read_text(encoding="utf-8") == text


def test_ids_that_normalize_alike_still_count_as_two_entries(home: Path) -> None:
    config = {"agents": {"entries": {"Main": {}, "main": {}}}}

    workspaces, _ = candidate_workspaces(config, home, env={})

    assert [w.path for w in workspaces] == [
        home / ".openclaw" / "workspace",
        home / ".openclaw" / "workspace-main",
    ]


def test_a_list_item_without_an_id_is_the_default_id(home: Path) -> None:
    config = {"agents": {"list": [{"workspace": "~/w"}, {"id": "ops"}]}}

    workspaces, _ = candidate_workspaces(config, home, env={})

    assert ("main",) in [w.agent_ids for w in workspaces]


def test_a_null_entries_key_is_an_empty_roster(home: Path) -> None:
    config = {"agents": {"entries": None, "list": [{"id": "ops"}]}}

    workspaces, _ = candidate_workspaces(config, home, env={})

    assert [w.path for w in workspaces] == [home / ".openclaw" / "workspace"]


def test_non_ascii_ids_are_normalized_like_openclaw() -> None:
    from apothem.harnesses.open_claw.rules_file import normalize_agent_id

    assert normalize_agent_id("équipe") == "quipe"
    assert normalize_agent_id(chr(0x212A)) == "k"  # Kelvin sign lowercases to k


def test_a_huge_whole_number_limit_does_not_crash() -> None:
    config = {"agents": {"defaults": {"bootstrapMaxChars": 10**400}}}

    assert limits_for(config, []).file_max == 10**400


def test_the_warning_for_an_apothem_entry_without_the_path_does_not_say_add_entry(
    home: Path,
) -> None:
    config = {"hooks": {"internal": {"entries": {HOOK_NAME: {"enabled": True}}}}}

    registration = plan_registration(config, apothem_entry=True, editable=False)

    assert registration.entry is None
    assert "add this entry" not in (registration.reason or "")
    assert "paths" in (registration.reason or "")


# --- third review nits ----------------------------------------------------------------


def test_an_array_in_the_list_roster_counts_as_an_entry(home: Path) -> None:
    config = {"agents": {"list": [[], {"id": "ops"}]}}

    workspaces, _ = candidate_workspaces(config, home, env={})

    assert [w.agent_ids for w in workspaces] == [(), ("main",), ("ops",)]


def test_a_relative_workspace_variable_is_not_expanded(home: Path) -> None:
    workspaces, notes = candidate_workspaces(
        {}, home, env={"OPENCLAW_WORKSPACE_DIR": "~/ws"}
    )

    assert workspaces == []
    assert any("not an absolute path" in note for note in notes)


def test_a_retired_rules_file_is_not_listed_in_the_new_record(
    adapter: OpenClawAdapter, home: Path
) -> None:
    old = _workspace(home / "ws-a")
    new = _workspace(home / "ws-b")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    _move_default_workspace(home, "~/ws-b")

    adapter.update({})

    record = install_ledger.current_install_record("open_claw", root=home / ".openclaw")
    assert record is not None
    listed = {Path(target.path) for target in record.targets}
    assert old / RULES_FILE_RELATIVE not in listed
    assert new / RULES_FILE_RELATIVE in listed


def test_an_install_recorded_without_digests_still_uninstalls_cleanly(
    adapter: OpenClawAdapter, home: Path
) -> None:
    # A record from before digests (#220): the rules file and openclaw.json are
    # removed surgically, not through the byte-for-byte digest check, so the
    # uninstall finishes instead of keeping them as unproven.
    workspace = _workspace(home / ".openclaw" / "workspace")
    _write_config(home, {"gateway": {"port": 1}})
    adapter.install({})
    ledger = install_ledger.ledger_path("open_claw")
    records = [
        json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
    ]
    for record in records:
        for target in record.get("targets", []):
            target.pop("digest", None)
            target.pop("files", None)
    ledger.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )

    run = adapter.uninstall()

    assert not [r for r in run.results if r.detail.get("kept_reason")]
    assert not (workspace / "apothem").exists()
    assert (workspace / "AGENTS.md").read_text(encoding="utf-8") == _AGENT_OWN
    assert _config(home) == {"gateway": {"port": 1}}
    assert install_ledger.read_records("open_claw")[-1].kind == "uninstall"


# --- follow-up to the #228 merge review ------------------------------------------------


def _linked_old_workspace(adapter: OpenClawAdapter, home: Path) -> Path:
    """Install into ~/ws-a, make its apothem/ folder a link, move to ~/ws-b.

    Returns the real folder the link points to, which holds the rules file.
    """
    old = _workspace(home / "ws-a")
    _workspace(home / "ws-b")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    moved = old / "apothem-real"
    (old / "apothem").rename(moved)
    _link_folder(old / "apothem", moved)
    _move_default_workspace(home, "~/ws-b")
    return moved


def _uninstall_cli() -> tuple[int, str]:
    from click.testing import CliRunner

    from apothem.cli import main

    result = CliRunner().invoke(main, ["uninstall", "--harness", "open-claw", "--yes"])
    return result.exit_code, result.output


def _kinds() -> list[str]:
    return [record.kind for record in install_ledger.read_records("open_claw")]


def test_a_retry_after_editing_beside_the_block_is_still_unfinished(
    adapter: OpenClawAdapter, home: Path
) -> None:
    # The block, not the whole file, is what Apothem wrote: adding a line of
    # your own must not make the retry report "not installed" and close the
    # install while the block stays.
    moved = _linked_old_workspace(adapter, home)
    first, _ = _uninstall_cli()
    target = moved / "AGENTS.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\nmy own line\n", encoding="utf-8"
    )

    code, output = _uninstall_cli()

    assert first == 2
    assert code == 2, output
    assert _kinds()[-1] == "uninstall-incomplete"
    assert "BEGIN APOTHEM MANAGED BLOCK" in target.read_text(encoding="utf-8")


def test_a_linked_rules_file_the_latest_record_lists_is_reported_once(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _linked_old_workspace(adapter, home)

    run = adapter.uninstall()

    assert [r for r in run.results if r.outcome == "error"] == []
    blocked = [r for r in run.results if r.detail.get("blocked")]
    assert len(blocked) == 1
    link = blocked[0].detail["symlink"]
    assert not [
        r
        for r in run.results
        if r is not blocked[0] and (link in r.path or link in r.message)
    ]


def test_a_linked_rules_file_only_an_older_record_lists_still_blocks(
    adapter: OpenClawAdapter, home: Path
) -> None:
    # An update made while ws-a/apothem was a link leaves ws-a out of the
    # latest record, so the blocked warning is the only signal.
    moved = _linked_old_workspace(adapter, home)
    adapter.update({})
    latest = install_ledger.current_install_record("open_claw", root=home / ".openclaw")
    assert latest is not None
    assert all("ws-a" not in target.path for target in latest.targets)

    code, output = _uninstall_cli()

    assert code == 2, output
    assert _kinds()[-1] == "uninstall-incomplete"
    assert (moved / "AGENTS.md").is_file()


def test_the_report_does_not_say_openclaw_still_loads_the_file(
    adapter: OpenClawAdapter, home: Path
) -> None:
    _linked_old_workspace(adapter, home)

    code, output = _uninstall_cli()

    assert code == 2
    flat = " ".join(output.split())
    assert "still loads" not in flat
    assert "reached through the link" in flat


def test_a_strip_that_fails_in_a_later_workspace_records_the_earlier_backup(
    adapter: OpenClawAdapter, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _workspace(home / "ws-a")
    second = _workspace(home / "ws-b")
    _write_config(
        home,
        {
            "agents": {
                "defaults": {"workspace": "~/ws-a"},
                "entries": {"b": {"workspace": "~/ws-b"}, "c": {}},
            }
        },
    )
    adapter.install({})
    real = rules_file.install_driver.strip_managed_anchor

    def stuck_on_b(path: Path, **kwargs: object) -> MaterializationResult | None:
        if "ws-b" in str(path):
            return MaterializationResult("updated", "retire_anchor", str(path), "x")
        return real(path, **kwargs)  # type: ignore[arg-type]

    with monkeypatch.context() as patch:
        patch.setattr(rules_file.install_driver, "strip_managed_anchor", stuck_on_b)
        run = adapter.uninstall()

    errors = [r for r in run.results if r.outcome == "error"]
    assert len(errors) == 1
    assert str(second) in errors[0].message
    assert "AGENTS.md" in errors[0].message
    assert "the earlier rules file" not in errors[0].message
    assert not (first / "apothem").exists()
    assert (second / RULES_FILE_RELATIVE).is_file()
    assert (home / ".openclaw" / ".apothem" / "support").is_dir()
    last = install_ledger.read_records("open_claw")[-1]
    assert last.kind == "uninstall-incomplete"
    assert any(target.backup_ref for target in last.targets)

    adapter.uninstall()

    assert not (second / "apothem").exists()
    assert _kinds()[-1] == "uninstall"


def _unlink_folder(link: Path) -> None:
    link.rmdir() if sys.platform == "win32" else link.unlink()


def _uninstall_json() -> tuple[int, dict[str, object]]:
    from click.testing import CliRunner

    from apothem.cli import main

    result = CliRunner().invoke(
        main, ["uninstall", "--harness", "open-claw", "--yes", "--format", "json"]
    )
    envelope: dict[str, object] = json.loads(result.output)
    return result.exit_code, envelope


def _warning_messages(envelope: dict[str, object]) -> list[str]:
    warnings = envelope.get("warnings")
    assert isinstance(warnings, list)
    return [str(warning["message"]) for warning in warnings]


def test_a_retry_after_replacing_the_link_removes_the_block_and_keeps_your_line(
    adapter: OpenClawAdapter, home: Path
) -> None:
    # The order the merge review first tried: the link is replaced with a real
    # folder and a line of your own is added before the retry, which then
    # finishes, taking the block out and keeping your line.
    moved = _linked_old_workspace(adapter, home)
    first, _ = _uninstall_cli()
    link = moved.parent / "apothem"
    _unlink_folder(link)
    moved.rename(link)
    target = link / "AGENTS.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\nmy own line\n", encoding="utf-8"
    )

    code, output = _uninstall_cli()

    assert first == 2
    assert code == 0, output
    text = target.read_text(encoding="utf-8")
    assert "my own line" in text
    assert "BEGIN APOTHEM MANAGED BLOCK" not in text
    assert _kinds()[-1] == "uninstall"


def _linked_current_workspace(adapter: OpenClawAdapter, home: Path) -> Path:
    """Install into ~/ws-a, then make its apothem/ folder a link; keep ws-a."""
    workspace = _workspace(home / "ws-a")
    if not (home / ".openclaw" / "openclaw.json").exists():
        _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    moved = workspace / "apothem-real"
    (workspace / "apothem").rename(moved)
    _link_folder(workspace / "apothem", moved)
    return moved


def _refuse_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the uninstall fail to change openclaw.json (read-only, say)."""

    def refuse(target: Path, *args: object, **kwargs: object) -> MaterializationResult:
        return MaterializationResult(
            "error", "surgical_uninstall", str(target), "permission denied"
        )

    monkeypatch.setattr(
        rules_file.install_driver, "surgically_remove_materialized_config", refuse
    )


def test_the_report_says_openclaw_still_loads_a_file_whose_path_stays(
    adapter: OpenClawAdapter, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # openclaw.json could not be rewritten, so the hook entry still names the
    # rules file in a workspace OpenClaw still uses: OpenClaw still loads it.
    _linked_current_workspace(adapter, home)
    config = home / ".openclaw" / "openclaw.json"
    before = config.read_bytes()
    _refuse_config(monkeypatch)

    code, output = _uninstall_cli()

    assert code == 2, output
    assert config.read_bytes() == before
    assert "open-claw still loads them" in " ".join(output.split())


def test_the_report_does_not_say_still_loads_for_a_workspace_openclaw_left(
    adapter: OpenClawAdapter, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The hook entry still names the path, but the file is in ws-a and the
    # config now points OpenClaw at ws-b, so OpenClaw does not read it.
    _linked_old_workspace(adapter, home)
    _refuse_config(monkeypatch)

    code, output = _uninstall_cli()

    assert code == 2, output
    flat = " ".join(output.split())
    assert "reached through the link" in flat
    assert "still loads" not in flat


def test_an_operators_own_pattern_keeps_the_file_loading(
    adapter: OpenClawAdapter, home: Path
) -> None:
    # The uninstall takes Apothem's path out, but the operator's own glob
    # still names the rules file, so OpenClaw still loads it.
    _write_config(
        home,
        {
            "agents": {"defaults": {"workspace": "~/ws-a"}},
            "hooks": {
                "internal": {
                    "entries": {"bootstrap-extra-files": {"paths": ["*/AGENTS.md"]}}
                }
            },
        },
    )
    _linked_current_workspace(adapter, home)

    code, output = _uninstall_cli()

    assert code == 2, output
    assert "open-claw still loads them" in " ".join(output.split())


@pytest.mark.parametrize(
    ("internal", "entry", "workspace", "expected"),
    [
        ({}, {"paths": ["apothem/AGENTS.md"]}, "~/ws-a", True),
        ({"enabled": False}, {"paths": ["apothem/AGENTS.md"]}, "~/ws-a", False),
        ({}, {"enabled": False, "paths": ["apothem/AGENTS.md"]}, "~/ws-a", False),
        ({}, {"paths": ["docs/AGENTS.md"]}, "~/ws-a", False),
        ({}, {"paths": [], "patterns": ["apothem/AGENTS.md"]}, "~/ws-a", True),
        ({}, {"paths": ["apothem/AGENTS.md"]}, "~/ws-b", False),
    ],
)
def test_still_loaded_follows_the_hook_and_the_workspace(
    home: Path,
    internal: dict[str, object],
    entry: dict[str, object],
    workspace: str,
    expected: bool,
) -> None:
    config = {
        "agents": {"defaults": {"workspace": workspace}},
        "hooks": {
            "internal": {**internal, "entries": {"bootstrap-extra-files": entry}}
        },
    }
    path = home / "ws-a" / "apothem" / "AGENTS.md"

    assert rules_file.still_loaded(config, path, home) is expected


def test_a_rules_file_whose_block_lost_its_end_marker_is_left_as_it_is(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / "ws-a")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    target = workspace / RULES_FILE_RELATIVE
    text = target.read_text(encoding="utf-8").replace(APOTHEM_BLOCK_END, "")
    target.write_text(text + "my own line\n", encoding="utf-8")
    before = target.read_bytes()

    code, envelope = _uninstall_json()

    assert code == 0, envelope
    assert target.read_bytes() == before
    named = [m for m in _warning_messages(envelope) if APOTHEM_BLOCK_END in m]
    assert len(named) == 1, envelope
    assert str(workspace) in named[0]
    assert _kinds()[-1] == "uninstall"
    assert adapter.is_installed() is False


def test_a_block_without_its_end_behind_a_link_lets_the_uninstall_finish(
    adapter: OpenClawAdapter, home: Path
) -> None:
    moved = _linked_old_workspace(adapter, home)
    target = moved / "AGENTS.md"
    text = target.read_text(encoding="utf-8").replace(APOTHEM_BLOCK_END, "")
    target.write_bytes((text + "my own line\n").encode())
    before = target.read_bytes()

    code, envelope = _uninstall_json()

    assert code == 0, envelope
    assert target.read_bytes() == before
    named = [m for m in _warning_messages(envelope) if APOTHEM_BLOCK_END in m]
    assert len(named) == 1, envelope
    assert _kinds()[-1] == "uninstall"


def test_a_strip_error_names_the_rules_file(
    adapter: OpenClawAdapter, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(home / "ws-a")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})

    def refuse(path: Path, **kwargs: object) -> MaterializationResult:
        return MaterializationResult("error", "retire_anchor", str(path), "denied")

    monkeypatch.setattr(rules_file.install_driver, "strip_managed_anchor", refuse)
    run = adapter.uninstall()

    [error] = [r for r in run.results if r.outcome == "error"]
    assert str(workspace / RULES_FILE_RELATIVE) in error.message


def test_your_line_quoting_the_begin_marker_survives_the_uninstall(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / "ws-a")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    target = workspace / RULES_FILE_RELATIVE
    quoted = "Apothem writes <!-- BEGIN APOTHEM MANAGED BLOCK --> above its rules.\n"
    target.write_bytes(target.read_bytes() + b"\n" + quoted.encode())

    code, output = _uninstall_cli()

    assert code == 0, output
    assert target.read_bytes() == quoted.encode()
    assert _kinds()[-1] == "uninstall"


def test_a_preview_names_a_rules_file_whose_block_lost_its_end(
    adapter: OpenClawAdapter, home: Path
) -> None:
    workspace = _workspace(home / "ws-a")
    _write_config(home, {"agents": {"defaults": {"workspace": "~/ws-a"}}})
    adapter.install({})
    target = workspace / RULES_FILE_RELATIVE
    target.write_bytes(target.read_bytes().replace(APOTHEM_BLOCK_END.encode(), b""))

    results = rules_file.retire_earlier_files(home / ".openclaw", (), dry_run=True)

    assert [r.outcome for r in results] == ["warning"]
    assert APOTHEM_BLOCK_END in results[0].message


def _blocked_run(home: Path) -> object:
    from apothem.harnesses._shared.install_driver import MaterializationRun

    warning = MaterializationResult(
        "warning",
        rules_file.RETIRE,
        str(home / "ws-a" / "apothem" / "AGENTS.md"),
        "reached through a link",
        detail={"symlink": str(home / "ws-a" / "apothem"), "blocked": "1"},
    )
    return MaterializationRun(harness="open_claw", dry_run=False, results=(warning,))


def test_a_config_that_cannot_be_read_keeps_the_still_loads_wording(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Nothing shows what OpenClaw loads, so the report makes no new claim; a
    # config that is gone loads nothing.
    from apothem.harnesses.open_claw import uninstall as module

    config = home / ".openclaw" / "openclaw.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("{ not json5", encoding="utf-8")
    monkeypatch.setattr(module, "_remove", lambda path: _blocked_run(home))

    unreadable = module.uninstall(config)
    config.unlink()
    gone = module.uninstall(config)

    assert "loaded" not in unreadable.results[0].detail
    assert gone.results[0].detail["loaded"] == "0"


def test_a_retry_names_a_rules_file_whose_block_lost_its_end(
    adapter: OpenClawAdapter, home: Path
) -> None:
    moved = _linked_old_workspace(adapter, home)
    first, _ = _uninstall_cli()
    target = moved / "AGENTS.md"
    cut = target.read_bytes().replace(APOTHEM_BLOCK_END.encode(), b"")
    target.write_bytes(cut + b"my own line\n")
    before = target.read_bytes()

    code, envelope = _uninstall_json()

    assert first == 2
    assert code == 0, envelope
    assert target.read_bytes() == before
    assert any(APOTHEM_BLOCK_END in m for m in _warning_messages(envelope)), envelope
    assert _kinds()[-1] == "uninstall"


def test_an_unreadable_ledger_keeps_the_hand_removal_error(
    adapter: OpenClawAdapter, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A commented openclaw.json that still holds Apothem's entries stops the
    # uninstall with what to remove; a ledger that cannot be read must not
    # turn that into a crash.
    _workspace(home / ".openclaw" / "workspace")
    adapter.install({})
    _commented(home, _config(home))

    def unreadable(*args: object, **kwargs: object) -> list[object]:
        raise PermissionError("the ledger is locked")

    monkeypatch.setattr(install_ledger, "read_records", unreadable)
    run = adapter.uninstall()

    assert [r for r in run.results if r.outcome == "error"], run.results
