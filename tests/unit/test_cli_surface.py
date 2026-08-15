# SPDX-License-Identifier: MIT

"""CLI-surface smoke tests.

Covers the published-CLI verification floor:
- all 14+ surfaces' --help exits 0
- continuous-form aliases (Installing + installing, Updating + updating,
  Uninstalling + uninstalling) resolve symmetrically
- structured-reportable commands emit parseable JSON under --json
- verify exits 1 when the adapter is not installed
- dry-run paths return without mutating
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from apothem.cli import main


def _write_valid_profile(path) -> None:
    path.write_text("identity:\n  name: Example User\n", encoding="utf-8")


def _symlink_or_skip(target: Path, link: Path, *, target_is_directory: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as exc:  # pragma: no cover - platform permission dependent
        pytest.skip(f"symlinks unavailable on this platform: {exc}")


@pytest.mark.parametrize(
    "args",
    [
        ["--help"],
        ["install", "--help"],
        ["uninstall", "--help"],
        ["update", "--help"],
        ["verify", "--help"],
        ["doctor", "--help"],
        ["profile", "--help"],
        ["profile", "init", "--help"],
        ["profile", "show", "--help"],
        ["profile", "set", "--help"],
        ["profile", "edit", "--help"],
        ["harnesses", "--help"],
        ["harnesses", "list", "--help"],
        ["harnesses", "show", "--help"],
        ["Installing", "--help"],
        ["installing", "--help"],
        ["Updating", "--help"],
        ["updating", "--help"],
        ["Uninstalling", "--help"],
        ["uninstalling", "--help"],
    ],
)
def test_help_exits_zero(runner: CliRunner, args: list[str]) -> None:
    result = runner.invoke(main, args)
    assert result.exit_code == 0, result.output


def test_installing_alias_hidden_from_top_level_help(runner: CliRunner) -> None:
    """The continuous-form install aliases are hidden from --help.

    Hiding declutters the command list; the aliases still resolve (proved by
    ``test_installing_help_has_alias_note`` and ``test_help_exits_zero``).
    """
    result = runner.invoke(main, ["--help"])
    assert "Installing" not in result.output
    assert "installing" not in result.output


def test_updating_alias_hidden_from_top_level_help(runner: CliRunner) -> None:
    """The continuous-form update aliases are hidden from --help."""
    result = runner.invoke(main, ["--help"])
    assert "Updating" not in result.output
    assert "updating" not in result.output


def test_uninstalling_alias_hidden_from_top_level_help(runner: CliRunner) -> None:
    """The continuous-form uninstall aliases are hidden from --help."""
    result = runner.invoke(main, ["--help"])
    assert "Uninstalling" not in result.output
    assert "uninstalling" not in result.output


def test_installing_help_has_alias_note(runner: CliRunner) -> None:
    result = runner.invoke(main, ["Installing", "--help"])
    assert "Alias for install" in result.output


def test_updating_help_has_alias_note(runner: CliRunner) -> None:
    result = runner.invoke(main, ["Updating", "--help"])
    assert "Alias for update" in result.output


def test_uninstalling_help_has_alias_note(runner: CliRunner) -> None:
    result = runner.invoke(main, ["Uninstalling", "--help"])
    assert "Alias for uninstall" in result.output


def test_install_dry_run(runner: CliRunner, mock_adapter: MagicMock) -> None:
    with runner.isolated_filesystem():
        profile = "profile.yaml"
        _write_valid_profile(Path(profile))
        with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
            result = runner.invoke(
                main,
                [
                    "install",
                    "--harness",
                    "codex",
                    "--profile",
                    profile,
                    "--dry-run",
                ],
            )
    assert result.exit_code == 0, result.output


def test_install_dry_run_json_uses_lifecycle_envelope(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path
) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(
            main,
            [
                "install",
                "--harness",
                "codex",
                "--profile",
                str(profile),
                "--dry-run",
                "--json",
            ],
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["status"] == "dry_run"
    assert data["command"] == "install"
    assert data["files_written"] == []


def test_install_invalid_profile_fails_before_adapter_write(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path
) -> None:
    profile = tmp_path / "profile.yaml"
    profile.write_text("identity: {}\n", encoding="utf-8")
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(
            main,
            [
                "install",
                "--harness",
                "codex",
                "--profile",
                str(profile),
            ],
        )

    assert result.exit_code != 0
    assert "Apothem validation failed." in result.output
    assert "Files written: none." in result.output
    mock_adapter.install.assert_not_called()
    assert not mock_adapter.output_path.exists()


def test_install_json_output(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path
) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(
            main,
            [
                "install",
                "--harness",
                "codex",
                "--profile",
                str(profile),
                "--json",
            ],
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["status"] == "success"
    assert data["command"] == "install"
    assert data["action"] == "installed"
    assert data["harness"] == "codex"


def test_install_all_applies_profile_exclusions(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path
) -> None:
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        "identity:\n"
        "  name: Example User\n"
        "exclude_harnesses:\n"
        "  - cursor\n"
        "  - gemini-cli\n"
        "  - github-copilot\n"
        "  - windsurf\n"
        "  - kimi-code\n"
        "  - codebuddy\n"
        "  - kiro\n"
        "  - trae\n"
        "  - zed\n"
        "  - glm\n",
        encoding="utf-8",
    )

    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(
            main,
            [
                "install",
                "--harness",
                "all",
                "--profile",
                str(profile),
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["status"] == "success"
    assert data["harness"] == "all"
    assert mock_adapter.install.call_count == 7


def test_verify_all_applies_profile_exclusions(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path
) -> None:
    """verify --harness all honors exclude_harnesses like the install did.

    Right after a green ``install --harness all``, verify must not report
    the excluded harnesses as missing.
    """
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        "identity:\n"
        "  name: Example User\n"
        "exclude_harnesses:\n"
        "  - cursor\n"
        "  - gemini-cli\n"
        "  - github-copilot\n"
        "  - windsurf\n"
        "  - kimi-code\n"
        "  - codebuddy\n"
        "  - kiro\n"
        "  - trae\n"
        "  - zed\n"
        "  - glm\n",
        encoding="utf-8",
    )
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(
            main,
            ["verify", "--harness", "all", "--profile", str(profile), "--json"],
        )
    data = json.loads(result.output.strip())
    names = {row["harness"] for row in data["results"]}
    assert "cursor" not in names
    assert "claude-code" in names
    assert len(names) == 7


def test_install_all_requires_project_when_project_harnesses_selected(
    runner: CliRunner, tmp_path
) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)

    result = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "all",
            "--profile",
            str(profile),
            "--json",
        ],
    )

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["error"]["field"] == "project"
    assert data["files_written"] == []


def test_install_alias_dispatch_via_initial_cap(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path
) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(
            main,
            [
                "Installing",
                "--harness",
                "codex",
                "--profile",
                str(profile),
                "--json",
            ],
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["action"] == "installed"


def test_install_alias_dispatch_via_lowercase(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path
) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(
            main,
            [
                "installing",
                "--harness",
                "codex",
                "--profile",
                str(profile),
                "--json",
            ],
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["action"] == "installed"


def test_update_alias_dispatch_via_initial_cap(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path
) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(
            main,
            [
                "Updating",
                "--harness",
                "codex",
                "--profile",
                str(profile),
                "--json",
            ],
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["action"] == "updated"


def test_update_alias_dispatch_via_lowercase(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path
) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(
            main,
            [
                "updating",
                "--harness",
                "codex",
                "--profile",
                str(profile),
                "--json",
            ],
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["action"] == "updated"


def test_uninstall_alias_dispatch(runner: CliRunner, mock_adapter: MagicMock) -> None:
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(
            main,
            [
                "Uninstalling",
                "--harness",
                "codex",
                "--yes",
                "--json",
            ],
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["status"] == "success"
    assert data["action"] == "uninstalled"


def test_profile_init_creates_valid_profile(runner: CliRunner, tmp_path) -> None:
    profile = tmp_path / "profile.yaml"
    result = runner.invoke(
        main,
        [
            "profile",
            "init",
            "--profile",
            str(profile),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["status"] == "success"
    assert data["files_written"] == [str(profile.resolve())]

    show = runner.invoke(main, ["profile", "show", "--profile", str(profile)])
    assert show.exit_code == 0, show.output


def test_profile_init_force_rejects_symlink_target(
    runner: CliRunner, tmp_path: Path
) -> None:
    outside = tmp_path / "outside-profile.yaml"
    outside.write_text("identity:\n  name: Operator\n", encoding="utf-8")
    profile = tmp_path / "profile.yaml"
    _symlink_or_skip(outside, profile, target_is_directory=False)

    result = runner.invoke(
        main,
        [
            "profile",
            "init",
            "--profile",
            str(profile),
            "--force",
            "--json",
        ],
    )

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["error"]["code"] == "profile.write_failed"
    assert "symlink" in data["error"]["reason"]
    assert outside.read_text(encoding="utf-8") == "identity:\n  name: Operator\n"


def test_profile_set_and_show(runner: CliRunner, tmp_path) -> None:
    profile = tmp_path / "profile.yaml"
    r1 = runner.invoke(
        main,
        [
            "profile",
            "set",
            "identity",
            "{name: Example User}",
            "--profile",
            str(profile),
        ],
    )
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(main, ["profile", "show", "--profile", str(profile)])
    assert r2.exit_code == 0, r2.output


def test_profile_set_rejects_symlink_target(runner: CliRunner, tmp_path: Path) -> None:
    outside = tmp_path / "outside-profile.yaml"
    outside.write_text("identity:\n  name: Operator\n", encoding="utf-8")
    profile = tmp_path / "profile.yaml"
    _symlink_or_skip(outside, profile, target_is_directory=False)

    result = runner.invoke(
        main,
        [
            "profile",
            "set",
            "identity",
            "{name: Example User}",
            "--profile",
            str(profile),
            "--json",
        ],
    )

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["error"]["code"] == "profile.write_failed"
    assert "symlink" in data["error"]["reason"]
    assert outside.read_text(encoding="utf-8") == "identity:\n  name: Operator\n"


def test_profile_set_json(runner: CliRunner, tmp_path) -> None:
    # A real, schema-valid nested set succeeds and emits the success envelope.
    profile = tmp_path / "p.yaml"
    profile.write_text("identity:\n  name: Operator\n", encoding="utf-8")
    result = runner.invoke(
        main,
        [
            "profile",
            "set",
            "preferences.style",
            "concise",
            "--profile",
            str(profile),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["action"] == "set"
    assert data["key"] == "preferences.style"


def test_profile_set_rejects_unknown_key(runner: CliRunner, tmp_path) -> None:
    # The pre-fix bug wrote a flat invalid key and reported success; now an
    # unknown key is rejected and the on-disk profile is left unchanged.
    profile = tmp_path / "p.yaml"
    profile.write_text("identity:\n  name: Operator\n", encoding="utf-8")
    before = profile.read_text(encoding="utf-8")
    result = runner.invoke(
        main,
        ["profile", "set", "model", "gpt-4o", "--profile", str(profile), "--json"],
    )
    assert result.exit_code != 0
    data = json.loads(result.output.strip())
    assert data["error"]["code"] == "profile.unknown_field"
    assert profile.read_text(encoding="utf-8") == before


def test_profile_set_dotted_invalid_target_rejected(
    runner: CliRunner, tmp_path
) -> None:
    profile = tmp_path / "p.yaml"
    profile.write_text("identity:\n  name: Operator\n", encoding="utf-8")
    before = profile.read_text(encoding="utf-8")
    result = runner.invoke(
        main,
        ["profile", "set", "identity.bogus", "x", "--profile", str(profile)],
    )
    assert result.exit_code != 0
    assert profile.read_text(encoding="utf-8") == before


def test_profile_set_preserves_siblings_and_nests(runner: CliRunner, tmp_path) -> None:
    profile = tmp_path / "p.yaml"
    profile.write_text(
        "identity:\n  name: Operator\n  role: engineer\n", encoding="utf-8"
    )
    result = runner.invoke(
        main,
        ["profile", "set", "identity.name", "Ada Lovelace", "--profile", str(profile)],
    )
    assert result.exit_code == 0, result.output
    loaded = yaml.safe_load(profile.read_text(encoding="utf-8"))
    assert loaded["identity"]["name"] == "Ada Lovelace"
    assert loaded["identity"]["role"] == "engineer"  # sibling preserved
    # The mutated profile re-loads without "Additional properties" failure.
    show = runner.invoke(main, ["profile", "show", "--profile", str(profile)])
    assert show.exit_code == 0, show.output


def test_profile_set_does_not_coerce_yaml_scalars(runner: CliRunner, tmp_path) -> None:
    # "no" is the Norway problem; it must stay a literal string, so an invalid
    # enum is rejected (not silently coerced to boolean false and written).
    profile = tmp_path / "p.yaml"
    profile.write_text("identity:\n  name: Operator\n", encoding="utf-8")
    result = runner.invoke(
        main,
        ["profile", "set", "seriousness", "no", "--profile", str(profile)],
    )
    assert result.exit_code != 0
    assert "seriousness" not in yaml.safe_load(profile.read_text(encoding="utf-8"))


def test_profile_set_rejects_malformed_existing_profile(
    runner: CliRunner, tmp_path: Path
) -> None:
    # A malformed existing profile yields a clean diagnostic, never a raw YAML
    # traceback, and the file on disk is left unchanged (the write happens only
    # after validation).
    profile = tmp_path / "p.yaml"
    profile.write_text(": : : not valid\n  - broken\n", encoding="utf-8")
    before = profile.read_text(encoding="utf-8")
    result = runner.invoke(
        main,
        ["profile", "set", "response_style", "concise", "--profile", str(profile)],
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert profile.read_text(encoding="utf-8") == before


def test_profile_set_rejects_non_mapping_existing_profile(
    runner: CliRunner, tmp_path: Path
) -> None:
    # A YAML list (not a mapping) is rejected with the same clean diagnostic.
    profile = tmp_path / "p.yaml"
    profile.write_text("- a\n- b\n", encoding="utf-8")
    result = runner.invoke(
        main,
        [
            "profile",
            "set",
            "response_style",
            "concise",
            "--profile",
            str(profile),
            "--json",
        ],
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert json.loads(result.output)["status"] == "error"


def test_doctor_json(runner: CliRunner, mock_adapter: MagicMock) -> None:
    with patch("apothem.cli._all_adapters", return_value=([mock_adapter], [])):
        result = runner.invoke(main, ["doctor", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert "version" in data
    assert "harnesses" in data
    assert "profile_valid" in data
    assert data["all_ok"] is True


def test_doctor_reports_valid_profile(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path: Path
) -> None:
    """doctor validates a present profile against the schema, not just existence."""
    profile = tmp_path / "profile.yaml"
    init = runner.invoke(main, ["profile", "init", "--profile", str(profile)])
    assert init.exit_code == 0, init.output
    with (
        patch("apothem.cli._all_adapters", return_value=([mock_adapter], [])),
        patch("apothem.cli._cmd_doctor._resolve_profile_path", return_value=profile),
    ):
        result = runner.invoke(main, ["doctor", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["profile_exists"] is True
    assert data["profile_valid"] is True


def test_doctor_flags_invalid_profile(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path: Path
) -> None:
    """A present-but-malformed profile is reported invalid with a non-zero exit."""
    profile = tmp_path / "profile.yaml"
    # A YAML list is well-formed YAML but not a profile mapping, so the shared
    # loader rejects it — exactly the breakage an existence-only check missed.
    profile.write_text("- not\n- a\n- profile\n", encoding="utf-8")
    with (
        patch("apothem.cli._all_adapters", return_value=([mock_adapter], [])),
        patch("apothem.cli._cmd_doctor._resolve_profile_path", return_value=profile),
    ):
        result = runner.invoke(main, ["doctor", "--json"])
    assert result.exit_code != 0, result.output
    data = json.loads(result.output.strip())
    assert data["profile_valid"] is False
    assert "profile_error" in data


def test_harnesses_list_json(runner: CliRunner, mock_adapter: MagicMock) -> None:
    with patch("apothem.cli._all_adapters", return_value=([mock_adapter], [])):
        result = runner.invoke(main, ["harnesses", "list", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert isinstance(data, list)
    assert data[0]["name"] == "test-harness"


def test_harnesses_show_json(runner: CliRunner, mock_adapter: MagicMock) -> None:
    mock_adapter.name = "codex"
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(main, ["harnesses", "show", "codex", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["name"] == "codex"
    assert data["scope"] == "user"


def test_verify_installed_json(runner: CliRunner, mock_adapter: MagicMock) -> None:
    mock_adapter.is_installed.return_value = True
    mock_adapter.verify.return_value = True
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(main, ["verify", "--harness", "codex", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["status"] == "success"
    assert data["installed"] is True
    assert data["verified"] is True


def test_verify_not_installed_exits_1(
    runner: CliRunner, mock_adapter: MagicMock
) -> None:
    mock_adapter.is_installed.return_value = False
    mock_adapter.verify.return_value = False
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(main, ["verify", "--harness", "codex"])
    assert result.exit_code == 1


def test_uninstall_already_gone(runner: CliRunner, mock_adapter: MagicMock) -> None:
    mock_adapter.is_installed.return_value = False
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(main, ["uninstall", "--harness", "codex", "--yes"])
    assert result.exit_code == 0, result.output


def test_unknown_harness_json_error_has_diagnostic_shape(
    runner: CliRunner, tmp_path
) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    result = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "not-a-harness",
            "--profile",
            str(profile),
            "--json",
        ],
    )
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["status"] == "error"
    assert data["error"]["field"] == "harness"
    assert data["error"]["files_written"] == []


def test_rollback_batch_no_record_error_visible_in_plain_mode(
    runner: CliRunner, tmp_path
) -> None:
    """A batch member's no-record failure prints in plain mode.

    The failure must be visible on the error console, not only as a JSON
    result row, and never hidden behind a success line.
    """
    with patch("apothem.cli._cmd_update.install_ledger") as ledger:
        ledger.latest_record.return_value = None
        result = runner.invoke(
            main,
            ["rollback", "--harness", "all", "--project", str(tmp_path), "--yes"],
        )
    assert result.exit_code == 1
    assert "rollback failed" in result.stderr
    assert "Rolled back" not in result.output


def test_status_unreadable_default_profile_reports_unknown_drift(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path
) -> None:
    """An unreadable default profile degrades drift to 'unknown', not 'drift'.

    Comparing an installed harness against an empty profile would misreport
    every install as drifted; without a baseline the verdict is unknown.
    """
    bad_profile = tmp_path / "profile.yaml"
    bad_profile.write_text("identity: [unclosed", encoding="utf-8")
    with (
        patch(
            "apothem.cli._cmd_status._resolve_profile_path",
            return_value=bad_profile,
        ),
        patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter),
    ):
        result = runner.invoke(main, ["status", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    drifts = {row["harness"]: row["drift"] for row in data["results"]}
    assert "unknown" in drifts.values()
    assert "drift" not in drifts.values()


def test_status_unreadable_default_profile_warns_when_nothing_installed(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path
) -> None:
    """A broken baseline is surfaced even when no harness is installed.

    The 'unknown' drift cell is only emitted for an *installed* harness; with
    nothing installed every cell reads 'absent' — true, but it conceals that
    the baseline never loaded. The advisory is then the only channel that
    reports the degradation, and it matters most here: a malformed profile is
    likeliest right after hand-editing a fresh one, when nothing is installed.
    """
    bad_profile = tmp_path / "profile.yaml"
    bad_profile.write_text("identity: [unclosed", encoding="utf-8")
    mock_adapter.is_installed.return_value = False
    with (
        patch(
            "apothem.cli._cmd_status._resolve_profile_path",
            return_value=bad_profile,
        ),
        patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter),
    ):
        result = runner.invoke(main, ["status", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    # No 'unknown' cell exists to carry the signal, so warnings must.
    assert "unknown" not in {row["drift"] for row in data["results"]}

    warnings = data["warnings"]
    assert len(warnings) == 1, warnings
    entry = warnings[0]
    assert entry["operation"] == "drift_baseline_unavailable"
    assert entry["path"] == str(bad_profile)
    # The advisory names the consequence, not merely that something failed.
    assert "unknown" in str(entry["message"])


def test_verify_all_unreadable_default_profile_warns_exclusions_dropped(
    runner: CliRunner, mock_adapter: MagicMock, tmp_path
) -> None:
    """Dropping exclude_harnesses on an unreadable profile is never silent.

    'verify --harness all' loads the default profile only to honour
    exclude_harnesses. Swallowing that failure lets every excluded harness
    back into the selection — and the project-scope ones then demand
    --project, so the run dies on 'project.required' listing harnesses the
    operator deliberately excluded. The error must carry its own cause.
    """
    bad_profile = tmp_path / "profile.yaml"
    bad_profile.write_text("identity: [unclosed", encoding="utf-8")
    with (
        patch(
            "apothem.cli._cmd_verify._resolve_profile_path",
            return_value=bad_profile,
        ),
        patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter),
    ):
        result = runner.invoke(main, ["verify", "--harness", "all", "--json"])
    data = json.loads(result.output.strip())
    # The failure is a consequence of the dropped excludes, not of the
    # harnesses it names.
    assert data["error"]["code"] == "project.required"

    warnings = data["warnings"]
    assert len(warnings) == 1, warnings
    entry = warnings[0]
    assert entry["operation"] == "exclusions_unavailable"
    assert entry["path"] == str(bad_profile)
    assert "exclu" in str(entry["message"]).lower()


def test_harnesses_list_json_load_failure_is_error_row(runner: CliRunner) -> None:
    """A broken adapter is a JSON error row — never styled text on stdout.

    The old module-level console printed a warning straight to stdout,
    corrupting the JSON document and ignoring --quiet/--no-color.
    """
    with patch(
        "apothem.cli._helpers.load_adapter_class", side_effect=ImportError("boom")
    ):
        result = runner.invoke(main, ["harnesses", "list", "--json"])
    assert result.exit_code == 1
    entries = json.loads(result.output.strip())
    assert entries
    assert all(entry["outcome"] == "error" for entry in entries)
    assert all("boom" in entry["message"] for entry in entries)


def test_doctor_json_load_failure_is_error_row(runner: CliRunner) -> None:
    with patch(
        "apothem.cli._helpers.load_adapter_class", side_effect=ImportError("boom")
    ):
        result = runner.invoke(main, ["doctor", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.output.strip())
    assert payload["all_ok"] is False
    assert payload["harnesses"]
    assert all(row.get("error") for row in payload["harnesses"])


def test_install_output_path_with_markup_chars_renders_literally(
    runner: CliRunner, tmp_path
) -> None:
    """A bracketed path segment must not crash or restyle the Rich output.

    Paths are user data, not markup: unescaped, '[bold]' in a directory
    name raises a MarkupError or silently restyles the line.
    """
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    hostile = tmp_path / "[bold]proj"
    hostile.mkdir()
    adapter = MagicMock()
    adapter.name = "test-harness"
    adapter.output_path = hostile / "config [red]x.json"
    adapter.resolve_output_path.return_value = adapter.output_path
    adapter.is_installed.return_value = True
    adapter.install.return_value = None
    with patch("apothem.cli._load_adapter_for_entry", return_value=adapter):
        result = runner.invoke(
            main,
            [
                "install",
                "--harness",
                "codex",
                "--profile",
                str(profile),
                "--dry-run",
            ],
        )
    assert result.exit_code == 0, result.output
    # Join wrapped lines: the rendered path must survive literally, with the
    # bracketed segments printed as text rather than consumed as markup.
    flattened = result.output.replace("\n", "")
    assert "[bold]proj" in flattened
    assert "[red]x.json" in flattened


def test_profile_set_invalid_value_exits_one(runner: CliRunner, tmp_path) -> None:
    """profile set refuses an invalid value with exit 1, as its epilog documents."""
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    result = runner.invoke(
        main,
        [
            "profile",
            "set",
            "seriousness",
            "NOT_A_LEVEL",
            "--profile",
            str(profile),
            "--json",
        ],
    )
    assert result.exit_code == 1, result.output
    data = json.loads(result.output.strip())
    assert data["status"] == "error"
