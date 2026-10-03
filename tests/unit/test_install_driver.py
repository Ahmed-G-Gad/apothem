# SPDX-License-Identifier: MIT

"""Unit tests for the shared harness install driver.

The driver at ``apothem.harnesses._shared.install_driver`` carries the
propagation recipe every harness adapter delegates to. These tests
exercise it directly — user-scope and project-scope round-trips,
plan materialisation, the stale-sweep primitive, and the error paths —
so the consolidated logic is covered independently of any single adapter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.lib.harness_registry import HARNESS_REGISTRY
from apothem.lib.propagation import HarnessRules, InstallEntry


def _symlink_or_skip(target: Path, link: Path, *, target_is_directory: bool) -> None:
    """Create a symlink, or skip when the platform forbids it."""
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as exc:  # pragma: no cover - platform permission dependent
        pytest.skip(f"symlinks unavailable on this platform: {exc}")


def test_load_rules_returns_known_harness() -> None:
    """A registered harness resolves to a rules object with entries."""
    rules = install_driver.load_rules("claude_code")
    assert isinstance(rules, HarnessRules)
    assert rules.install  # claude_code declares a non-empty install list


def test_load_rules_unknown_harness_raises() -> None:
    """An unregistered harness name raises, naming the bad key."""
    with pytest.raises(RuntimeError, match="does_not_exist"):
        install_driver.load_rules("does_not_exist")


def test_resolve_source_under_package_root() -> None:
    """Sources resolve under the package root; a trailing slash is stripped."""
    assert (
        install_driver.resolve_source("rules") == install_driver.APOTHEM_SRC / "rules"
    )
    # trailing slash is stripped before joining
    assert (
        install_driver.resolve_source("rules/") == install_driver.APOTHEM_SRC / "rules"
    )


def test_run_install_user_scope_round_trip(tmp_path: Path) -> None:
    """A user-scope install creates every planned target, twice over."""
    plan = install_driver.build_plan("claude_code", harness_root=tmp_path)
    install_driver.run_install("claude_code", harness_root=tmp_path)
    for entry in plan:
        target = Path(entry["target"])
        if entry["mode"] in {
            "replace_tree",
            "merge_tree_entries",
            "command_skills",
            "codex_agents",
            "gemini_agents",
            "opencode_agents",
            "qwen_agents",
            "gemini_commands",
            "markdown_commands",
            "native_skills",
        }:
            assert target.is_dir()
        elif entry["mode"] == "write_text":
            assert target.is_file()
    # Idempotent: a second run replaces previous content without raising.
    install_driver.run_install("claude_code", harness_root=tmp_path)


def test_run_install_project_scope_round_trip(tmp_path: Path) -> None:
    """A project-scope install creates every planned target."""
    install_driver.run_install("cursor", project_root=tmp_path)
    for entry in install_driver.build_plan("cursor", project_root=tmp_path):
        assert Path(entry["target"]).exists()


def test_run_install_dry_run_returns_structured_results_without_writes(
    tmp_path: Path,
) -> None:
    """A dry run classifies entries as created and writes nothing."""
    result = install_driver.run_install("cursor", project_root=tmp_path, dry_run=True)

    assert result.dry_run is True
    assert result.changed is False
    assert result.files_written == []
    # Every entry is classified prospectively against its (absent) target, so a
    # fresh preview reads "created" — never the old phantom "skipped".
    assert any(item.outcome == "created" for item in result.results)
    assert not any(item.outcome == "skipped" for item in result.results)
    assert not any(tmp_path.iterdir())


def test_run_install_reports_unchanged_on_second_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second install reports unchanged and takes no backup."""
    backup_root = tmp_path / "backups"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)

    first = install_driver.run_install("cursor", project_root=project)
    second = install_driver.run_install("cursor", project_root=project)

    assert first.changed is True
    assert second.changed is False
    assert any(item.outcome == "unchanged" for item in second.results)
    assert not backup_root.exists()


# The five "folding" harnesses render commands/ into the SAME skills/ directory
# their skills/ tree merge writes into (a command_skills entry and a
# merge_tree_entries skills/ entry that resolve to one root). projectify and
# workflow ship as BOTH a command and a standalone skill, so without the manifest's
# per-directory-filters skills exclusion both entries would author
# skills/<name>/SKILL.md with differing bodies — a source collision that rewrites
# itself on every install and never converges. The manifest excludes the standalone
# skill subdirs on these harnesses so the command-as-skill is the sole writer; this
# guard fails if a future same-name command/skill pair (or a dropped filter)
# reopens the collision.
_FOLDING_HARNESSES = ("claude_code", "codex", "antigravity", "hermes", "open_claw")


@pytest.mark.parametrize("harness", _FOLDING_HARNESSES)
def test_run_install_idempotent_for_command_skill_collision(
    harness: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Folding harnesses converge: the second pass writes nothing."""
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    root = tmp_path / harness

    first = install_driver.run_install(harness, harness_root=root)
    second = install_driver.run_install(harness, harness_root=root)

    assert first.changed is True
    # A second pass writes nothing: every install entry already matches on disk.
    # A perpetual command_skills/merge_tree_entries collision over projectify or
    # workflow would surface here as an "updated" outcome that never converges.
    assert second.changed is False
    assert not any(
        result.outcome in {"created", "updated"} for result in second.results
    )


def test_run_install_validates_all_sources_before_first_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One missing source aborts before any target is created."""
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "ok.txt").write_text("ok", encoding="utf-8")
    rules = HarnessRules(
        install=[
            InstallEntry(
                source="ok.txt",
                target="${HARNESS_ROOT}/ok.txt",
                mode="write_text",
            ),
            InstallEntry(
                source="missing.txt",
                target="${HARNESS_ROOT}/missing.txt",
                mode="write_text",
            ),
        ],
        exclude=[],
        stale_sweep=[],
    )
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", package_root)
    monkeypatch.setattr(install_driver, "load_rules", lambda name: rules)
    harness_root = tmp_path / "harness"

    with pytest.raises(install_driver.MaterializationError) as exc_info:
        install_driver.run_install("claude_code", harness_root=harness_root)

    assert exc_info.value.run.errors
    assert not (harness_root / "ok.txt").exists()
    assert not harness_root.exists()


def test_run_install_rejects_target_traversal_before_first_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A target escaping the root aborts before the first write."""
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "payload.txt").write_text("escape", encoding="utf-8")
    rules = HarnessRules(
        install=[
            InstallEntry(
                source="payload.txt",
                target="${HARNESS_ROOT}/../../escape.txt",
                mode="write_text",
            )
        ],
        exclude=[],
        stale_sweep=[],
    )
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", package_root)
    monkeypatch.setattr(install_driver, "load_rules", lambda name: rules)
    harness_root = tmp_path / "home" / ".codex"

    with pytest.raises(install_driver.MaterializationError) as exc_info:
        install_driver.run_install("codex", harness_root=harness_root)

    assert "escapes" in exc_info.value.run.errors[0].message
    assert not (tmp_path / "escape.txt").exists()


def test_run_install_projects_registry_capability_warnings(tmp_path: Path) -> None:
    """Codex projects its unsupported and discovery-pending surfaces."""
    result = install_driver.run_install("codex", harness_root=tmp_path, dry_run=True)
    warning_keys = {
        warning.detail["capability"]
        for warning in result.warnings
        if "capability" in warning.detail
    }

    assert {"statuslines", "output_styles"}.issubset(warning_keys)
    # MCP for codex lives in the operator-owned config.toml mcpServers tables —
    # apothem names the surface but authors no entries (discovery-pending), so it
    # IS projected as a capability-projection warning rather than silently
    # over-claimed as 'native'.
    assert "mcp_servers" in warning_keys


@pytest.mark.parametrize("entry", HARNESS_REGISTRY, ids=lambda entry: entry.public_id)
def test_run_install_warns_for_every_unsupported_capability(
    entry,
    tmp_path: Path,
) -> None:
    """Each harness warns on exactly its non-native capabilities."""
    root = tmp_path / entry.package_key
    if entry.scope == "project":
        root.mkdir()
        result = install_driver.run_install(
            entry.package_key,
            project_root=root,
            dry_run=True,
        )
    else:
        result = install_driver.run_install(
            entry.package_key,
            harness_root=root,
            dry_run=True,
        )
    expected = {
        capability
        for capability, status in entry.capability_status.items()
        if status in {"unsupported", "discovery-pending"}
    }
    warning_keys = {
        warning.detail["capability"]
        for warning in result.warnings
        if "capability" in warning.detail
    }

    assert warning_keys == expected


def test_build_plan_leaves_placeholder_when_no_root() -> None:
    """With no root the plan keeps its literal root placeholder."""
    plan = install_driver.build_plan("cursor")
    assert any("${PROJECT_ROOT}" in entry["target"] for entry in plan)


def test_build_plan_claude_code_includes_conformity_and_schemas(
    tmp_path: Path,
) -> None:
    """The claude_code plan propagates the conformity gate and schema fixtures.

    The settings template's PreToolUse gate entries resolve to
    ``${HARNESS_ROOT}/.apothem/support/conformity/gate.py`` at install time, so
    the plan must carry ``conformity/`` and its sibling ``schemas/`` fixture tree
    under the Apothem support subtree.
    """
    plan = install_driver.build_plan("claude_code", harness_root=tmp_path)
    planned = {
        (Path(entry["target"]), entry["mode"]): entry["source"] for entry in plan
    }
    conformity_key = (
        tmp_path / ".apothem" / "support" / "conformity",
        "merge_tree_entries",
    )
    schemas_key = (
        tmp_path / ".apothem" / "support" / "schemas",
        "merge_tree_entries",
    )
    assert conformity_key in planned
    assert schemas_key in planned
    assert planned[conformity_key].replace("\\", "/").endswith("/conformity")
    assert planned[schemas_key].replace("\\", "/").endswith("/schemas")


def test_run_install_requires_a_root() -> None:
    """An install with neither root raises rather than guessing one."""
    with pytest.raises(ValueError, match="harness_root or project_root"):
        install_driver.run_install("cursor")


def test_sweep_stale_removes_dir_and_file(tmp_path: Path) -> None:
    """The sweep removes stale dirs and files, ignoring absent ones."""
    stale_dir = tmp_path / "olddir"
    stale_dir.mkdir()
    (stale_dir / "child").write_text("x", encoding="utf-8")
    stale_file = tmp_path / "oldfile"
    stale_file.write_text("y", encoding="utf-8")

    install_driver.sweep_stale(["olddir", "oldfile", "absent"], tmp_path)

    assert not stale_dir.exists()
    assert not stale_file.exists()


def test_sweep_stale_backs_up_removed_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A named harness backs up each swept target before removal."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    stale_dir = tmp_path / "olddir"
    stale_dir.mkdir()
    (stale_dir / "child").write_text("x", encoding="utf-8")
    stale_file = tmp_path / "oldfile"
    stale_file.write_text("y", encoding="utf-8")

    install_driver.sweep_stale(
        ["olddir", "oldfile"], tmp_path, harness_name="claude_code"
    )

    assert (backup_root / next(backup_root.iterdir()).name / "claude_code").exists()
    assert next(iter(backup_root.rglob("child"))).read_text(encoding="utf-8") == "x"
    assert next(iter(backup_root.rglob("oldfile"))).read_text(encoding="utf-8") == "y"


def test_write_text_safely_backs_up_before_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An operator-edited target is backed up before it is replaced."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    target = tmp_path / "config.txt"
    target.write_text("operator edit", encoding="utf-8")

    install_driver.write_text_safely(
        target,
        "apothem template",
        install_root=tmp_path,
        harness_name="codex",
    )

    assert target.read_text(encoding="utf-8") == "apothem template"
    backup = next(iter(backup_root.rglob("config.txt")))
    assert backup.read_text(encoding="utf-8") == "operator edit"


def test_write_text_safely_reports_permission_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A denied write reports an error and leaves no partial file."""

    def _raise_permission_error(target: Path, data: bytes) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(
        install_driver, "_write_file_atomically", _raise_permission_error
    )

    result = install_driver.write_text_safely(
        tmp_path / "blocked.txt",
        "content",
        install_root=tmp_path,
        harness_name="codex",
    )

    assert result.outcome == "error"
    assert "could not write target atomically" in result.message
    assert not (tmp_path / "blocked.txt").exists()


def test_write_text_safely_rejects_target_traversal(tmp_path: Path) -> None:
    """A target outside the install root is refused."""
    result = install_driver.write_text_safely(
        tmp_path / ".." / "escape.txt",
        "content",
        install_root=tmp_path,
        harness_name="codex",
    )

    assert result.outcome == "error"
    assert "escapes" in result.message
    assert not (tmp_path.parent / "escape.txt").exists()


def test_write_text_safely_rejects_symlink_file_target(tmp_path: Path) -> None:
    """A symlinked target is refused; the linked file is untouched."""
    outside = tmp_path / "outside.txt"
    outside.write_text("operator content", encoding="utf-8")
    link = tmp_path / "config.txt"
    _symlink_or_skip(outside, link, target_is_directory=False)

    result = install_driver.write_text_safely(
        link,
        "apothem template",
        install_root=tmp_path,
        harness_name="codex",
    )

    assert result.outcome == "error"
    assert "symlink" in result.message
    assert outside.read_text(encoding="utf-8") == "operator content"
    assert link.is_symlink()


def test_write_text_safely_rejects_symlink_parent(tmp_path: Path) -> None:
    """A symlinked parent directory is refused before any write."""
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_root = tmp_path / "linked-root"
    _symlink_or_skip(outside, linked_root, target_is_directory=True)

    result = install_driver.write_text_safely(
        linked_root / "config.txt",
        "apothem template",
        install_root=linked_root,
        harness_name="codex",
    )

    assert result.outcome == "error"
    assert "symlink" in result.message
    assert not (outside / "config.txt").exists()


def test_write_text_safely_merges_json_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """JSON merges keep operator keys and hooks, swapping Apothem's."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    target = tmp_path / "settings.json"
    target.write_text(
        """{
  "permissions": {
    "allow": ["Bash(custom:*)"]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "python -m apothem.hooks.dispatch PreToolUse old"
          },
          {
            "type": "command",
            "command": "python -m custom.hook"
          }
        ]
      }
    ]
  },
  "operatorSetting": true
}
""",
        encoding="utf-8",
    )

    install_driver.write_text_safely(
        target,
        """{
  "permissions": {
    "allow": ["Read"]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["-m", "apothem.hooks.dispatch", "PreToolUse", "new"]
          }
        ]
      }
    ]
  }
}
""",
        install_root=tmp_path,
        harness_name="claude_code",
    )

    merged = json.loads(target.read_text(encoding="utf-8"))
    assert merged["operatorSetting"] is True
    assert merged["permissions"]["allow"] == ["Bash(custom:*)", "Read"]
    write_hooks = merged["hooks"]["PreToolUse"][0]["hooks"]
    commands = [hook["command"] for hook in write_hooks]
    assert "python -m custom.hook" in commands
    assert "python -m apothem.hooks.dispatch PreToolUse old" not in commands
    assert any(
        hook.get("args") == ["-m", "apothem.hooks.dispatch", "PreToolUse", "new"]
        for hook in write_hooks
    )
    assert list(backup_root.rglob("settings.json"))


def test_write_text_safely_can_overlay_managed_json_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Template-authoritative overlay wins on managed keys only."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    target = tmp_path / "opencode.json"
    target.write_text(
        """{
  "_apothem_managed": true,
  "instructions": "old profile",
  "preferences": {
    "language": "python",
    "operatorOnly": true
  },
  "operatorSetting": true
}
""",
        encoding="utf-8",
    )

    install_driver.write_text_safely(
        target,
        """{
  "_apothem_managed": true,
  "instructions": "new profile",
  "preferences": {
    "language": "rust"
  }
}
""",
        install_root=tmp_path,
        harness_name="opencode",
        prefer_existing_json_values=False,
    )

    merged = json.loads(target.read_text(encoding="utf-8"))
    assert merged["instructions"] == "new profile"
    assert merged["preferences"]["language"] == "rust"
    assert merged["preferences"]["operatorOnly"] is True
    assert merged["operatorSetting"] is True
    assert list(backup_root.rglob("opencode.json"))


def test_render_content_tokens_substitutes_harness_root_forward_slashes(
    tmp_path: Path,
) -> None:
    """``${HARNESS_ROOT}`` renders to the forward-slash absolute root path.

    The substituted form must stay valid inside JSON string literals on
    every platform, so the rendered path is the POSIX form even when the
    supplied root is a Windows-style path.
    """
    content = '{"args": ["${HARNESS_ROOT}/.apothem/support/hooks/dispatch.py", "Stop"]}'

    rendered = install_driver.render_content_tokens(content, harness_root=tmp_path)

    root_posix = tmp_path.resolve().as_posix()
    assert f'"{root_posix}/.apothem/support/hooks/dispatch.py"' in rendered
    assert "${HARNESS_ROOT}" not in rendered
    assert "\\" not in rendered
    assert json.loads(rendered)["args"][0] == (
        f"{root_posix}/.apothem/support/hooks/dispatch.py"
    )


def test_render_content_tokens_substitutes_project_root(tmp_path: Path) -> None:
    """``${PROJECT_ROOT}`` renders against the project-scope root."""
    rendered = install_driver.render_content_tokens(
        "rules at ${PROJECT_ROOT}/.cursor/rules",
        harness_root=None,
        project_root=tmp_path,
    )

    assert rendered == f"rules at {tmp_path.resolve().as_posix()}/.cursor/rules"


def test_render_content_tokens_leaves_placeholder_when_root_absent(
    tmp_path: Path,
) -> None:
    """A placeholder with no matching root stays literal in the output."""
    content = "h=${HARNESS_ROOT} p=${PROJECT_ROOT}"

    # No roots at all: the content passes through untouched.
    assert install_driver.render_content_tokens(content, harness_root=None) == content

    # One root present: only its placeholder renders; the other stays literal.
    partial = install_driver.render_content_tokens(content, harness_root=tmp_path)
    assert f"h={tmp_path.resolve().as_posix()}" in partial
    assert "${PROJECT_ROOT}" in partial
    assert "${HARNESS_ROOT}" not in partial


def test_render_content_tokens_passes_through_token_free_content(
    tmp_path: Path,
) -> None:
    """Content with no ``${`` marker is returned unchanged."""
    content = '{"command": "python", "note": "no placeholders here"}'

    assert (
        install_driver.render_content_tokens(content, harness_root=tmp_path) == content
    )


def _claude_code_settings_entry() -> InstallEntry:
    """Return the manifest's claude_code settings.json write_text entry."""
    rules = install_driver.load_rules("claude_code")
    return next(entry for entry in rules.install if entry.mode == "write_text")


def test_apply_write_text_renders_dispatch_paths_into_settings(
    tmp_path: Path,
) -> None:
    """Installing the claude_code settings template renders absolute hook paths.

    The template addresses the dispatcher and the conformity gate via
    ``${HARNESS_ROOT}`` tokens; the installed ``settings.json`` must carry
    the resolved forward-slash absolute paths instead.
    """
    harness_root = tmp_path / "claude"

    install_driver.apply_write_text(
        _claude_code_settings_entry(),
        harness_root=harness_root,
        harness_name="claude_code",
    )

    text = (harness_root / "settings.json").read_text(encoding="utf-8")
    assert "${HARNESS_ROOT}" not in text
    settings = json.loads(text)
    root_posix = harness_root.resolve().as_posix()
    session_args = settings["hooks"]["SessionStart"][0]["hooks"][0]["args"]
    assert session_args == [
        f"{root_posix}/.apothem/support/hooks/dispatch.py",
        "SessionStart",
    ]
    write_entry = next(
        entry
        for entry in settings["hooks"]["PreToolUse"]
        if entry["matcher"] == "Write"
    )
    gate_args = [
        hook["args"]
        for hook in write_entry["hooks"]
        if any("gate.py" in str(arg) for arg in hook["args"])
    ]
    assert gate_args == [
        [f"{root_posix}/.apothem/support/conformity/gate.py", "--hook"]
    ]


def test_apply_write_text_overlay_updates_stale_hooks_preserving_operator_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-install replaces stale Apothem hook args and keeps operator content.

    An existing ``settings.json`` carrying module-form Apothem hook args is
    overlaid template-authoritatively: the Apothem-owned handlers update to
    the rendered template form, while the operator's own hook handlers and
    operator-added top-level keys are preserved (with a backup of the prior
    file).
    """
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    harness_root = tmp_path / "claude"
    harness_root.mkdir()
    target = harness_root / "settings.json"
    target.write_text(
        json.dumps(
            {
                "operatorWorkbench": {"theme": "dark"},
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python",
                                    "args": [
                                        "-m",
                                        "apothem.hooks.dispatch",
                                        "SessionStart",
                                    ],
                                },
                                {
                                    "type": "command",
                                    "command": "python -m operator_tools.session",
                                },
                            ],
                        }
                    ]
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    results = install_driver.apply_write_text(
        _claude_code_settings_entry(),
        harness_root=harness_root,
        harness_name="claude_code",
    )

    assert results[0].outcome == "updated"
    merged = json.loads(target.read_text(encoding="utf-8"))
    # Operator-only keys survive the template-authoritative overlay.
    assert merged["operatorWorkbench"] == {"theme": "dark"}
    session_hooks = merged["hooks"]["SessionStart"][0]["hooks"]
    rendered_dispatch = (
        f"{harness_root.resolve().as_posix()}/.apothem/support/hooks/dispatch.py"
    )
    args_sets = [tuple(hook.get("args", [])) for hook in session_hooks]
    # The stale module-form Apothem handler is replaced by the rendered form.
    assert ("-m", "apothem.hooks.dispatch", "SessionStart") not in args_sets
    assert (rendered_dispatch, "SessionStart") in args_sets
    # The operator's own handler under the same matcher is preserved.
    commands = [hook.get("command") for hook in session_hooks]
    assert "python -m operator_tools.session" in commands
    # Template-carried keys ship to the existing install.
    assert "Read(**/site/dist/**)" in merged["permissions"]["deny"]
    # The pre-overlay operator file was backed up.
    assert list(backup_root.rglob("settings.json"))

    # A further re-install is byte-stable: the rendered path-form handlers
    # are recognized as Apothem-owned and replaced in place, never duplicated.
    second = install_driver.apply_write_text(
        _claude_code_settings_entry(),
        harness_root=harness_root,
        harness_name="claude_code",
    )
    assert second[0].outcome == "unchanged"
    rerun = json.loads(target.read_text(encoding="utf-8"))
    rerun_hooks = rerun["hooks"]["SessionStart"][0]["hooks"]
    assert len(rerun_hooks) == len(session_hooks)


def test_apply_merge_tree_entries_renders_tokens_in_top_level_file_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Top-level file entries render path tokens; token-free bytes pass through.

    The statusline command file embeds ``${HARNESS_ROOT}`` and must be
    rendered at install time, while token-free text and undecodable binary
    siblings propagate byte-identical.
    """
    package_root = tmp_path / "package"
    statuslines = package_root / "statuslines"
    statuslines.mkdir(parents=True)
    (statuslines / "conformity.json").write_text(
        "{\n"
        '  "type": "command",\n'
        '  "command": "python3 \\"${HARNESS_ROOT}/statuslines/render.py\\""\n'
        "}\n",
        encoding="utf-8",
    )
    token_free = b"plain statusline notes with no placeholders\n"
    (statuslines / "statusline.md").write_bytes(token_free)
    # Invalid UTF-8 bytes around a literal "${" marker: the renderer must
    # leave the binary payload byte-identical.
    binary_payload = b"\x89BIN\x00\xff${HARNESS_ROOT}\xfe"
    (statuslines / "badge.bin").write_bytes(binary_payload)
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", package_root)
    harness_root = tmp_path / "harness"

    install_driver.apply_merge_tree_entries(
        InstallEntry(
            source="statuslines/",
            target="${HARNESS_ROOT}/statuslines/",
            mode="merge_tree_entries",
        ),
        install_driver.make_ignore([], {}),
        [],
        harness_root=harness_root,
    )

    target = harness_root / "statuslines"
    rendered = (target / "conformity.json").read_text(encoding="utf-8")
    assert "${HARNESS_ROOT}" not in rendered
    root_posix = harness_root.resolve().as_posix()
    assert f'python3 \\"{root_posix}/statuslines/render.py\\"' in rendered
    assert (target / "statusline.md").read_bytes() == token_free
    assert (target / "badge.bin").read_bytes() == binary_payload


def test_run_install_rejects_unknown_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unrecognized install mode raises rather than no-opping."""
    bogus = HarnessRules(
        install=[
            InstallEntry(source="rules", target="${HARNESS_ROOT}/x", mode="bogus")
        ],
        exclude=[],
        stale_sweep=[],
    )
    monkeypatch.setattr(install_driver, "load_rules", lambda name: bogus)
    with pytest.raises(ValueError, match="unknown install entry mode"):
        install_driver.run_install("claude_code", harness_root=tmp_path)


def test_replace_tree_skips_when_source_absent(tmp_path: Path) -> None:
    """An absent source leaves the destination uncreated."""
    dst = tmp_path / "dst"
    install_driver.replace_tree(
        tmp_path / "no-such-source", dst, install_driver.make_ignore([], {})
    )
    assert not dst.exists()


def test_apply_write_text_skips_when_source_absent(tmp_path: Path) -> None:
    """An absent template writes no file, only the parent dir."""
    entry = InstallEntry(
        source="no-such-template-file.txt",
        target="${HARNESS_ROOT}/out.txt",
        mode="write_text",
    )
    install_driver.apply_write_text(entry, harness_root=tmp_path)
    # The target parent is created, but no file is written when the source
    # template does not exist.
    assert not (tmp_path / "out.txt").exists()


def test_apply_merge_tree_entries_honors_source_root_filters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-directory filters exclude their named files from the copy."""
    package_root = tmp_path / "package"
    statuslines = package_root / "statuslines"
    statuslines.mkdir(parents=True)
    for filename in (
        "__init__.py",
        "conformity.json",
        "render.py",
        "statusline.md",
    ):
        (statuslines / filename).write_text(filename, encoding="utf-8")
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", package_root)

    install_driver.apply_merge_tree_entries(
        InstallEntry(
            source="statuslines/",
            target="${HARNESS_ROOT}/statuslines/",
            mode="merge_tree_entries",
        ),
        install_driver.make_ignore(
            [],
            {"statuslines": ["__init__.py", "conformity.json", "render.py"]},
        ),
        [],
        harness_root=tmp_path / "harness",
    )

    target = tmp_path / "harness" / "statuslines"
    assert (target / "statusline.md").is_file()
    assert not (target / "__init__.py").exists()
    assert not (target / "conformity.json").exists()
    assert not (target / "render.py").exists()


def test_apply_command_skills_preserves_unrelated_skill_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Operator-authored skill directories survive the conversion."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "sample-command.md").write_text(
        '---\nname: "sample-command"\ndescription: "Sample command."\n---\n\nBody.',
        encoding="utf-8",
    )
    fake_package_root = tmp_path / "package"
    commands_src = fake_package_root / "commands"
    commands_src.mkdir(parents=True)
    (commands_src / "sample-command.md").write_text(
        (src / "sample-command.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    target = tmp_path / "skills"
    unrelated = target / "operator-skill"
    unrelated.mkdir(parents=True)
    (unrelated / "SKILL.md").write_text("operator content", encoding="utf-8")
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", fake_package_root)

    install_driver.apply_command_skills(
        InstallEntry(
            source="commands/",
            target="${HARNESS_ROOT}/skills/",
            mode="command_skills",
        ),
        harness_root=tmp_path,
        harness_name="claude_code",
    )

    assert (target / "sample-command" / "SKILL.md").is_file()
    assert (unrelated / "SKILL.md").read_text(encoding="utf-8") == "operator content"


def test_apply_command_skills_excludes_documentation_companions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """README.md and AGENTS.md beside commands never materialize as skills."""
    fake_package_root = tmp_path / "package"
    commands_src = fake_package_root / "commands"
    commands_src.mkdir(parents=True)
    (commands_src / "sample-command.md").write_text(
        '---\nname: "sample-command"\ndescription: "Sample command."\n---\n\nBody.',
        encoding="utf-8",
    )
    (commands_src / "README.md").write_text("# index\n", encoding="utf-8")
    (commands_src / "AGENTS.md").write_text("# companion\n", encoding="utf-8")
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", fake_package_root)

    install_driver.apply_command_skills(
        InstallEntry(
            source="commands/",
            target="${HARNESS_ROOT}/skills/",
            mode="command_skills",
        ),
        harness_root=tmp_path,
        harness_name="claude_code",
    )

    target = tmp_path / "skills"
    assert (target / "sample-command" / "SKILL.md").is_file()
    assert not (target / "README").exists()
    assert not (target / "AGENTS").exists()


def test_apply_command_skills_idempotent_for_plan_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second update pass over a materialized plan-stage skill reports no drift.

    After the /plan decomposition each ``commands/plan-<stage>.md`` converts to
    its own first-class ``plan-<stage>/SKILL.md`` directory; a re-run must
    report ``unchanged`` rather than wipe-and-rewrite (with a backup).
    """
    fake_package_root = tmp_path / "package"
    commands_src = fake_package_root / "commands"
    commands_src.mkdir(parents=True)
    (commands_src / "plan-status.md").write_text(
        '---\nname: "plan-status"\ndescription: "Show plan progress."\n---\n\nBody.',
        encoding="utf-8",
    )
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", fake_package_root)
    entry = InstallEntry(
        source="commands/",
        target="${HARNESS_ROOT}/skills/",
        mode="command_skills",
    )

    first = install_driver.apply_command_skills(
        entry, harness_root=tmp_path, harness_name="claude_code"
    )
    second = install_driver.apply_command_skills(
        entry, harness_root=tmp_path, harness_name="claude_code"
    )

    target = tmp_path / "skills" / "plan-status"
    assert (target / "SKILL.md").is_file()
    assert any(r.outcome == "created" for r in first)
    assert {r.outcome for r in second} == {"unchanged"}


def test_directory_contents_equal_ignores_generated_entries_on_destination(
    tmp_path: Path,
) -> None:
    """Interpreter artifacts in the installed tree do not defeat comparison.

    Hook scripts run in place at the harness root and Python writes
    ``__pycache__`` beside them; the ignore filter must apply to the
    destination side too, or every update re-copies an unchanged directory.
    """
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "events.py").write_text("EVENTS = ()\n", encoding="utf-8")
    (dst / "events.py").write_text("EVENTS = ()\n", encoding="utf-8")
    cache = dst / "__pycache__"
    cache.mkdir()
    (cache / "events.cpython-313.pyc").write_bytes(b"\x00bytecode")
    ignore = install_driver.make_ignore(["__pycache__", "*.pyc"], {})

    assert install_driver._directory_contents_equal(src, dst, ignore)


def test_apply_command_skills_rejects_symlink_generated_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A symlinked skill dir errors instead of being written through."""
    fake_package_root = tmp_path / "package"
    commands_src = fake_package_root / "commands"
    commands_src.mkdir(parents=True)
    (commands_src / "sample-command.md").write_text(
        '---\ndescription: "Sample command."\n---\n\nBody.',
        encoding="utf-8",
    )
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", fake_package_root)
    harness_root = tmp_path / ".codex"
    target_root = tmp_path / ".agents" / "skills"
    target_root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    _symlink_or_skip(
        outside,
        target_root / "sample-command",
        target_is_directory=True,
    )

    results = install_driver.apply_command_skills(
        InstallEntry(
            source="commands/",
            target="${HARNESS_ROOT}/../.agents/skills/",
            mode="command_skills",
        ),
        harness_root=harness_root,
        harness_name="codex",
    )

    assert any(result.outcome == "error" for result in results)
    assert not (outside / "SKILL.md").exists()


def test_codex_command_skill_note_points_hooks_to_codex_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The codex note points hooks at the codex root, rules at ~/.config."""
    fake_package_root = tmp_path / "package"
    commands_src = fake_package_root / "commands"
    commands_src.mkdir(parents=True)
    (commands_src / "sample-command.md").write_text(
        '---\ndescription: "Sample command."\n---\n\nBody.',
        encoding="utf-8",
    )
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", fake_package_root)

    install_driver.apply_command_skills(
        InstallEntry(
            source="commands/",
            target="${HARNESS_ROOT}/../.agents/skills/",
            mode="command_skills",
        ),
        harness_root=tmp_path / ".codex",
        harness_name="codex",
    )

    text = (tmp_path / ".agents" / "skills" / "sample-command" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert f"`hooks/<path>` is `{(tmp_path / '.codex' / 'hooks').as_posix()}/" in text
    support = tmp_path / ".config" / "apothem"
    assert f"`rules/<path>` is `{(support / 'rules').as_posix()}/" in text
    assert f"`templates/<path>` is `{(support / 'templates').as_posix()}/" in text
    assert "schemas/" not in text  # codex installs no schemas


@pytest.mark.parametrize(
    ("harness_name", "harness_root"),
    [
        ("hermes", ".hermes"),
        ("open_claw", ".openclaw"),
    ],
)
def test_command_skill_note_points_to_apothem_support_tree(
    harness_name: str,
    harness_root: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hermes and Open-Claw point every cohort at the .apothem/support tree."""
    fake_package_root = tmp_path / "package"
    commands_src = fake_package_root / "commands"
    commands_src.mkdir(parents=True)
    (commands_src / "sample-command.md").write_text(
        '---\ndescription: "Sample command."\n---\n\nBody.',
        encoding="utf-8",
    )
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", fake_package_root)
    root = tmp_path / harness_root

    install_driver.apply_command_skills(
        InstallEntry(
            source="commands/",
            target="${HARNESS_ROOT}/apothem/skills/",
            mode="command_skills",
        ),
        harness_root=root,
        harness_name=harness_name,
    )

    text = (root / "apothem" / "skills" / "sample-command" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    support = root / ".apothem" / "support"
    for name in ("rules", "templates", "hooks"):
        assert f"`{name}/<path>` is `{(support / name).as_posix()}/" in text
    assert (root / "apothem").as_posix() + "/" not in text


def test_claude_command_skill_note_points_to_apothem_support_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude Code splits native rules from the support-subtree cohorts."""
    fake_package_root = tmp_path / "package"
    commands_src = fake_package_root / "commands"
    commands_src.mkdir(parents=True)
    (commands_src / "sample-command.md").write_text(
        '---\ndescription: "Sample command."\n---\n\nBody.',
        encoding="utf-8",
    )
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", fake_package_root)
    root = tmp_path / ".claude"

    install_driver.apply_command_skills(
        InstallEntry(
            source="commands/",
            target="${HARNESS_ROOT}/skills/",
            mode="command_skills",
        ),
        harness_root=root,
        harness_name="claude_code",
    )

    text = (root / "skills" / "sample-command" / "SKILL.md").read_text(encoding="utf-8")
    assert f"`rules/<path>` is `{(root / 'rules').as_posix()}/" in text
    support = root / ".apothem" / "support"
    for name in ("templates", "schemas", "hooks", "conformity"):
        assert f"`{name}/<path>` is `{(support / name).as_posix()}/" in text


def test_antigravity_command_skill_note_points_to_plugin_support_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Antigravity addresses its cohorts under the plugin root."""
    fake_package_root = tmp_path / "package"
    commands_src = fake_package_root / "commands"
    commands_src.mkdir(parents=True)
    (commands_src / "sample-command.md").write_text(
        '---\ndescription: "Sample command."\n---\n\nBody.',
        encoding="utf-8",
    )
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", fake_package_root)
    root = tmp_path / ".gemini"
    plugin_root = root / "antigravity-cli" / "plugins" / "apothem"

    install_driver.apply_command_skills(
        InstallEntry(
            source="commands/",
            target="${HARNESS_ROOT}/antigravity-cli/plugins/apothem/skills/",
            mode="command_skills",
        ),
        harness_root=root,
        harness_name="antigravity",
    )

    text = (plugin_root / "skills" / "sample-command" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert f"`rules/<path>` is `{(plugin_root / 'rules').as_posix()}/" in text
    support = plugin_root / ".apothem" / "support"
    for name in ("templates", "hooks"):
        assert f"`{name}/<path>` is `{(support / name).as_posix()}/" in text


def test_apply_codex_agents_converts_markdown_to_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Agents convert to TOML and the stale markdown twin is removed."""
    fake_package_root = tmp_path / "package"
    agents_src = fake_package_root / "agents"
    agents_src.mkdir(parents=True)
    (agents_src / "sample-agent.md").write_text(
        '---\nname: "sample-agent"\ndescription: "Sample agent."\n---\n\nAgent body.',
        encoding="utf-8",
    )
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", fake_package_root)
    stale_markdown = tmp_path / "agents" / "sample-agent.md"
    stale_markdown.parent.mkdir(parents=True)
    stale_markdown.write_text("stale", encoding="utf-8")

    install_driver.apply_codex_agents(
        InstallEntry(
            source="agents/",
            target="${HARNESS_ROOT}/agents/",
            mode="codex_agents",
        ),
        harness_root=tmp_path,
        harness_name="codex",
    )

    target = tmp_path / "agents" / "sample-agent.toml"
    assert not stale_markdown.exists()
    text = target.read_text(encoding="utf-8")
    assert 'name = "sample_agent"' in text
    assert 'description = "Sample agent."' in text
    assert "developer_instructions" in text


def test_apply_qwen_agents_converts_tools_and_approval_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tool names and the permission mode map to Qwen's vocabulary."""
    fake_package_root = tmp_path / "package"
    agents_src = fake_package_root / "agents"
    agents_src.mkdir(parents=True)
    (agents_src / "sample-agent.md").write_text(
        "\n".join(
            [
                "---",
                'name: "sample-agent"',
                'description: "Sample agent."',
                'tools: "Read, Glob, Grep, Bash"',
                'disallowedTools: "Write, Edit, TodoWrite"',
                'permissionMode: "default"',
                "---",
                "",
                "Agent body.",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", fake_package_root)

    install_driver.apply_qwen_agents(
        InstallEntry(
            source="agents/",
            target="${HARNESS_ROOT}/agents/",
            mode="qwen_agents",
        ),
        harness_root=tmp_path,
        harness_name="qwen_code",
    )

    text = (tmp_path / "agents" / "sample-agent.md").read_text(encoding="utf-8")
    assert 'approvalMode: "default"' in text
    assert '  - "read_file"' in text
    assert '  - "run_shell_command"' in text
    assert '  - "write_file"' in text
    assert "Agent body." in text


def test_apply_markdown_commands_normalizes_frontmatter_and_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The generated header is dropped and args take the host's form."""
    fake_package_root = tmp_path / "package"
    commands_src = fake_package_root / "commands"
    commands_src.mkdir(parents=True)
    (commands_src / "sample-command.md").write_text(
        "\n".join(
            [
                "---",
                'description: "Sample command."',
                "---",
                "",
                "<!-- generated header -->",
                "",
                "Run with {{args}}.",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", fake_package_root)

    install_driver.apply_markdown_commands(
        InstallEntry(
            source="commands/",
            target="${HARNESS_ROOT}/commands/",
            mode="markdown_commands",
        ),
        harness_root=tmp_path,
        harness_name="opencode",
    )

    text = (tmp_path / "commands" / "sample-command.md").read_text(encoding="utf-8")
    assert text.startswith('---\ndescription: "Sample command."\n---')
    assert "<!-- generated header -->" not in text
    assert "$ARGUMENTS" in text


def _fake_template_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    relative: str,
    body: str,
) -> None:
    """Stand up a fake apothem package carrying one template file."""
    package_root = tmp_path / "package"
    template = package_root / relative
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text(body, encoding="utf-8")
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", package_root)


def test_apply_sentinel_merge_preserves_operator_prose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The managed block lands beside operator prose and is stable."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    _fake_template_package(
        tmp_path,
        monkeypatch,
        relative="anchor.md",
        body="Apothem governance content",
    )
    harness = tmp_path / "harness"
    harness.mkdir()
    anchor = harness / "anchor.md"
    anchor.write_text("# Operator Heading\n\nOperator-authored prose.\n", "utf-8")
    entry = InstallEntry(
        source="anchor.md",
        target="${HARNESS_ROOT}/anchor.md",
        mode="sentinel_merge",
        ownership_class="operator-owned",
    )

    results = install_driver.apply_sentinel_merge(
        entry, harness_root=harness, harness_name="codex"
    )

    text = anchor.read_text(encoding="utf-8")
    assert "Operator-authored prose." in text
    assert "Apothem governance content" in text
    assert results[0].outcome == "updated"
    assert "diff" in results[0].detail
    assert results[0].detail["destructive_gate"] == "required"
    # The operator file was backed up before the merge.
    assert list(backup_root.rglob("anchor.md"))

    # A second pass is a no-op: the managed block is byte-stable.
    second = install_driver.apply_sentinel_merge(
        entry, harness_root=harness, harness_name="codex"
    )
    assert second[0].outcome == "unchanged"


def test_apply_sentinel_merge_creates_anchor_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An absent anchor is created rather than gated."""
    _fake_template_package(
        tmp_path, monkeypatch, relative="anchor.md", body="Apothem block"
    )
    harness = tmp_path / "harness"
    harness.mkdir()
    entry = InstallEntry(
        source="anchor.md",
        target="${HARNESS_ROOT}/anchor.md",
        mode="sentinel_merge",
        ownership_class="operator-owned",
    )

    results = install_driver.apply_sentinel_merge(
        entry, harness_root=harness, harness_name="codex"
    )

    assert results[0].outcome == "created"
    assert "Apothem block" in (harness / "anchor.md").read_text(encoding="utf-8")


def test_apply_sentinel_merge_gate_decline_leaves_file_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A declined gate skips the merge, leaving the file byte-identical."""
    _fake_template_package(
        tmp_path, monkeypatch, relative="anchor.md", body="Apothem block"
    )
    harness = tmp_path / "harness"
    harness.mkdir()
    original = "Operator prose only.\n"
    anchor = harness / "anchor.md"
    anchor.write_text(original, encoding="utf-8")
    entry = InstallEntry(
        source="anchor.md",
        target="${HARNESS_ROOT}/anchor.md",
        mode="sentinel_merge",
        ownership_class="operator-owned",
    )
    seen: list[install_driver.AuthorizationRequest] = []

    def decline(request: install_driver.AuthorizationRequest) -> bool:
        seen.append(request)
        return False

    results = install_driver.apply_sentinel_merge(
        entry, harness_root=harness, harness_name="codex", authorize=decline
    )

    assert results[0].outcome == "skipped"
    assert anchor.read_text(encoding="utf-8") == original
    assert seen
    assert seen[0].ownership_class == "operator-owned"
    assert seen[0].diff


def test_run_install_refuses_vendor_reserved_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A vendor-reserved target aborts the install before any write."""
    _fake_template_package(tmp_path, monkeypatch, relative="payload.txt", body="x")
    rules = HarnessRules(
        install=[
            InstallEntry(
                source="payload.txt",
                target="${HARNESS_ROOT}/vendor.txt",
                mode="write_text",
                ownership_class="vendor-reserved",
            )
        ],
        exclude=[],
        stale_sweep=[],
    )
    monkeypatch.setattr(install_driver, "load_rules", lambda name: rules)
    harness = tmp_path / "harness"

    with pytest.raises(install_driver.MaterializationError) as exc_info:
        install_driver.run_install("cursor", harness_root=harness)

    assert "vendor-reserved" in exc_info.value.run.errors[0].message
    assert not (harness / "vendor.txt").exists()


def test_dry_run_renders_diff_and_gate_for_operator_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A preview renders the diff and marks the gate without writing."""
    _fake_template_package(
        tmp_path, monkeypatch, relative="anchor.md", body="Apothem block"
    )
    rules = HarnessRules(
        install=[
            InstallEntry(
                source="anchor.md",
                target="${HARNESS_ROOT}/anchor.md",
                mode="sentinel_merge",
                ownership_class="operator-owned",
            )
        ],
        exclude=[],
        stale_sweep=[],
    )
    monkeypatch.setattr(install_driver, "load_rules", lambda name: rules)
    harness = tmp_path / "harness"
    harness.mkdir()
    anchor = harness / "anchor.md"
    anchor.write_text("Operator prose.\n", encoding="utf-8")

    run = install_driver.run_install("codex", harness_root=harness, dry_run=True)

    assert run.files_written == []
    assert anchor.read_text(encoding="utf-8") == "Operator prose.\n"
    entry_result = next(r for r in run.results if r.operation == "sentinel_merge")
    assert "diff" in entry_result.detail
    assert entry_result.detail["destructive_gate"] == "required"


def _dry_run_entry_outcomes(run: install_driver.MaterializationRun) -> set[str]:
    """Return the install-entry outcomes of a dry run (skipping non-entry rows)."""
    return {
        result.outcome
        for result in run.results
        if result.operation
        not in {"capability_projection", "data_surface", "sweep_stale"}
    }


def test_dry_run_prospects_created_then_unchanged_after_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh preview reads ``created``; after a real install it reads ``unchanged``.

    This is the dry-run fidelity contract: the preview classifies every entry
    against its real on-disk target, so a re-preview of an installed harness
    reports no-ops instead of the old uniform phantom ``skipped``.
    """
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    project = tmp_path / "project"
    project.mkdir()

    fresh = install_driver.run_install("cursor", project_root=project, dry_run=True)
    assert _dry_run_entry_outcomes(fresh) == {"created"}
    assert fresh.changed is False
    assert fresh.files_written == []

    install_driver.run_install("cursor", project_root=project)

    repreview = install_driver.run_install("cursor", project_root=project, dry_run=True)
    assert _dry_run_entry_outcomes(repreview) == {"unchanged"}
    assert repreview.changed is False
    assert repreview.files_written == []


def test_dry_run_prospects_created_unchanged_updated_per_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An Apothem-owned ``write_text`` reads created / unchanged / updated by state."""
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    _fake_template_package(
        tmp_path, monkeypatch, relative="payload.txt", body="managed\n"
    )
    rules = HarnessRules(
        install=[
            InstallEntry(
                source="payload.txt",
                target="${HARNESS_ROOT}/payload.txt",
                mode="write_text",
                ownership_class="apothem-owned",
            )
        ],
        exclude=[],
        stale_sweep=[],
    )
    monkeypatch.setattr(install_driver, "load_rules", lambda name: rules)
    harness = tmp_path / "harness"
    harness.mkdir()
    target = harness / "payload.txt"

    def write_text_outcome() -> str:
        run = install_driver.run_install("cursor", harness_root=harness, dry_run=True)
        return next(r for r in run.results if r.operation == "write_text").outcome

    # Absent target → created.
    assert write_text_outcome() == "created"
    # Bytes the installer would write (raw, no newline translation) → unchanged.
    target.write_bytes(b"managed\n")
    assert write_text_outcome() == "unchanged"
    # Divergent bytes → updated, and a dry run never reports an actual write.
    target.write_bytes(b"operator edited this\n")
    assert write_text_outcome() == "updated"
    assert target.read_bytes() == b"operator edited this\n"


def test_dry_run_operator_anchor_created_without_gate_on_fresh_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh operator-owned anchor reads ``created`` with no destructive gate."""
    _fake_template_package(
        tmp_path, monkeypatch, relative="anchor.md", body="Apothem block"
    )
    rules = HarnessRules(
        install=[
            InstallEntry(
                source="anchor.md",
                target="${HARNESS_ROOT}/anchor.md",
                mode="sentinel_merge",
                ownership_class="operator-owned",
            )
        ],
        exclude=[],
        stale_sweep=[],
    )
    monkeypatch.setattr(install_driver, "load_rules", lambda name: rules)
    harness = tmp_path / "harness"
    harness.mkdir()

    run = install_driver.run_install("codex", harness_root=harness, dry_run=True)

    result = next(r for r in run.results if r.operation == "sentinel_merge")
    assert result.outcome == "created"
    # Nothing on disk to overwrite, so no gate is required (only an overwrite of
    # differing operator content gates).
    assert "destructive_gate" not in result.detail
    assert run.files_written == []


def test_restore_backup_rolls_back_operator_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Restoring the newest backup returns the operator file verbatim."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    _fake_template_package(
        tmp_path, monkeypatch, relative="anchor.md", body="Apothem block"
    )
    harness = tmp_path / "harness"
    harness.mkdir()
    anchor = harness / "anchor.md"
    original = "Operator prose only.\n"
    anchor.write_text(original, encoding="utf-8")
    entry = InstallEntry(
        source="anchor.md",
        target="${HARNESS_ROOT}/anchor.md",
        mode="sentinel_merge",
        ownership_class="operator-owned",
    )

    install_driver.apply_sentinel_merge(
        entry, harness_root=harness, harness_name="codex"
    )
    assert anchor.read_text(encoding="utf-8") != original

    timestamps = install_driver.list_backup_timestamps("codex")
    assert timestamps
    results = install_driver.restore_backup(
        "codex", timestamps[-1], harness_root=harness
    )

    assert any(r.changed for r in results)
    assert anchor.read_text(encoding="utf-8") == original


def test_list_backup_timestamps_enumerates_in_recency_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Timestamps sort oldest-first, so the tail is the newest set."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    # Two backup sets for the same harness, named by their UTC timestamp
    # slug; the slug sorts lexically by time, so the older slug precedes
    # the newer one.
    older = "20240101T000000Z"
    newer = "20240102T000000Z"
    for stamp in (newer, older):  # created out of order on purpose
        harness_set = backup_root / stamp / "codex"
        harness_set.mkdir(parents=True)
        (harness_set / "AGENTS.md").write_text(stamp, encoding="utf-8")

    timestamps = install_driver.list_backup_timestamps("codex")

    assert timestamps == [older, newer]
    # The newest backup is the last element — the recency tail restore_backup
    # consumes via timestamps[-1].
    assert timestamps[-1] == newer


def test_list_backup_timestamps_filters_by_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each harness sees only its own backup sets."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    codex_set = backup_root / "20240101T000000Z" / "codex"
    codex_set.mkdir(parents=True)
    (codex_set / "AGENTS.md").write_text("x", encoding="utf-8")
    cursor_set = backup_root / "20240102T000000Z" / "cursor"
    cursor_set.mkdir(parents=True)
    (cursor_set / "apothem-rules.mdc").write_text("y", encoding="utf-8")

    assert install_driver.list_backup_timestamps("codex") == ["20240101T000000Z"]
    assert install_driver.list_backup_timestamps("cursor") == ["20240102T000000Z"]


def test_restore_backup_skips_unknown_timestamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unknown timestamp is skipped rather than raising."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    harness = tmp_path / "harness"
    harness.mkdir()

    results = install_driver.restore_backup(
        "codex", "20990101T000000Z", harness_root=harness
    )

    assert results[0].outcome == "skipped"


def test_backup_existing_same_second_collision_resolves_distinct_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two backups that resolve the same timestamp second must not collide:
    # the second one suffixes its leaf rather than raising FileExistsError
    # (Windows WinError 183 from copytree onto an existing directory).
    """Two directory backups in one second land at distinct leaves."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    monkeypatch.setattr(install_driver, "_timestamp_slug", lambda: "20240101T000000Z")

    install_root = tmp_path / "harness"
    target = install_root / "commands"
    target.mkdir(parents=True)
    (target / "sample.md").write_text("v1", encoding="utf-8")

    first = install_driver.backup_existing(
        target, install_root=install_root, harness_name="codex"
    )
    (target / "sample.md").write_text("v2", encoding="utf-8")
    second = install_driver.backup_existing(
        target, install_root=install_root, harness_name="codex"
    )

    assert first is not None
    assert second is not None
    assert first != second
    assert first.is_dir()
    assert second.is_dir()
    # Both backups captured their own snapshot of the target's content.
    assert (first / "sample.md").read_text(encoding="utf-8") == "v1"
    assert (second / "sample.md").read_text(encoding="utf-8") == "v2"
    # The documented layout is preserved for the uncontended first backup.
    assert first == backup_root / "20240101T000000Z" / "codex" / "commands"


def test_backup_existing_same_second_collision_resolves_distinct_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The single-file backup path is collision-proof too: the second backup
    # of the same file within one timestamp second lands at a suffixed leaf.
    """Two file backups in one second land at distinct leaves."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    monkeypatch.setattr(install_driver, "_timestamp_slug", lambda: "20240101T000000Z")

    install_root = tmp_path / "harness"
    install_root.mkdir()
    target = install_root / "settings.json"
    target.write_text("a", encoding="utf-8")

    first = install_driver.backup_existing(
        target, install_root=install_root, harness_name="claude_code"
    )
    target.write_text("b", encoding="utf-8")
    second = install_driver.backup_existing(
        target, install_root=install_root, harness_name="claude_code"
    )

    assert first is not None
    assert second is not None
    assert first != second
    assert first.read_text(encoding="utf-8") == "a"
    assert second.read_text(encoding="utf-8") == "b"


def test_run_uninstall_removes_generated_children_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uninstall removes generated children and spares operator files."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    rules = HarnessRules(
        install=[
            InstallEntry(
                source="commands/",
                target="${HARNESS_ROOT}/commands/",
                mode="markdown_commands",
            )
        ],
        exclude=[],
        stale_sweep=[],
    )
    fake_package_root = tmp_path / "package"
    commands_src = fake_package_root / "commands"
    commands_src.mkdir(parents=True)
    (commands_src / "sample-command.md").write_text("source", encoding="utf-8")
    target = tmp_path / "commands"
    target.mkdir()
    (target / "sample-command.md").write_text("generated", encoding="utf-8")
    (target / "operator-command.md").write_text("operator", encoding="utf-8")
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", fake_package_root)
    monkeypatch.setattr(install_driver, "load_rules", lambda name: rules)

    install_driver.run_uninstall("opencode", harness_root=tmp_path)

    assert not (target / "sample-command.md").exists()
    assert (target / "operator-command.md").read_text(encoding="utf-8") == "operator"
    assert (
        next(backup_root.rglob("sample-command.md")).read_text(encoding="utf-8")
        == "generated"
    )


def test_plan_stages_materialize_as_first_class_skills(tmp_path: Path) -> None:
    """Each plan-<stage> command converts to its own native skill directory.

    ``apply_command_skills`` converts every top-level ``commands/plan-<stage>.md``
    into a first-class ``plan-<stage>/SKILL.md`` directory like any other
    command. The re-introduced thin ``/plan`` orchestrator (``commands/plan.md``)
    likewise materializes as its own ``plan/SKILL.md`` — a single command file,
    so no retired dispatch subtree rides beneath the materialized ``plan/`` skill.
    """
    # Arrange / Act — a directory-propagation harness installs the catalog.
    install_driver.run_install("claude_code", harness_root=tmp_path)

    # Assert — each of the seven stages lands as its own registered skill.
    expected = [
        "plan-audit",
        "plan-design",
        "plan-execute",
        "plan-generate",
        "plan-review",
        "plan-spec",
        "plan-status",
    ]
    for stage in expected:
        assert list(tmp_path.rglob(f"{stage}/SKILL.md")), (
            f"expected a first-class skill directory for {stage}"
        )
    # The thin /plan orchestrator is a first-class command and materializes as
    # its own skill, exactly like any other command.
    plan_skills = list(tmp_path.rglob("plan/SKILL.md"))
    assert plan_skills, (
        "expected a first-class skill directory for the /plan orchestrator"
    )
    # But no retired dispatch subtree rides beneath it: the materialized plan
    # skill is a single SKILL.md with no nested stage tree.
    for plan_skill in plan_skills:
        plan_dir = plan_skill.parent
        nested = [p for p in plan_dir.rglob("SKILL.md") if p.parent != plan_dir]
        assert not nested, f"retired dispatch subtree beneath plan/: {nested}"
