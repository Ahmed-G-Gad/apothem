# SPDX-License-Identifier: MIT

"""Per-adapter partial-failure isolation in read/remove/inspect commands.

A single adapter raising must not abort `uninstall` / `verify` / `harnesses list`
/ `doctor`: the bad harness becomes a structured error result, the rest complete,
and the command emits a populated envelope with a documented non-zero exit code —
never a bare traceback or empty `--json` output.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem import cli


class _GoodAdapter:
    """Adapter double whose lifecycle calls all succeed.

    Paired with a failing double so the sweep can be observed isolating one
    adapter's failure without disturbing its neighbours.
    """

    name = "alpha"

    @property
    def output_path(self) -> Path:
        return Path(tempfile.gettempdir()) / "alpha-config"

    def is_installed(self) -> bool:
        return True

    def verify(self) -> bool:
        return True

    def uninstall(self) -> None:
        return None


def _make_faulty(fault: str) -> object:
    class _FaultyAdapter:
        """Adapter double that raises from the one lifecycle call named by *fault*.

        Parameterising the failure point keeps a single double covering every
        lifecycle method, so the sweep's isolation is exercised per entry point
        rather than only where a hand-written double happened to break.
        """

        name = "omega"

        @property
        def output_path(self) -> Path:
            return Path(tempfile.gettempdir()) / "omega-config"

        def is_installed(self) -> bool:
            if fault == "is_installed":
                raise OSError("injected is_installed fault")
            return True

        def verify(self) -> bool:
            if fault == "verify":
                raise OSError("injected verify fault")
            return True

        def uninstall(self) -> None:
            if fault == "uninstall":
                raise OSError("injected uninstall fault")
            return

    return _FaultyAdapter()


def _patch_selection(
    monkeypatch: pytest.MonkeyPatch, good: object, faulty: object
) -> None:
    """Make uninstall/verify resolve to [good, faulty] by harness id."""
    fakes = {"alpha": good, "omega": faulty}
    monkeypatch.setattr(
        cli, "_selected_harness_ids", lambda *a, **k: ["alpha", "omega"]
    )
    monkeypatch.setattr(cli, "get_harness_entry", lambda hid: hid)
    monkeypatch.setattr(cli, "_load_adapter_for_entry", lambda entry: fakes[entry])
    monkeypatch.setattr(cli, "_require_project_for_selection", lambda ids, root: None)


def test_uninstall_isolates_one_failing_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_selection(monkeypatch, _GoodAdapter(), _make_faulty("uninstall"))
    result = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "all", "--yes", "--format", "json"]
    )
    assert result.exit_code == cli._EXIT_PARTIAL  # one removed, one errored
    assert "Traceback" not in result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "partial"
    by_harness = {r["harness"]: r for r in envelope["results"]}
    assert by_harness["alpha"]["outcome"] == "updated"
    assert by_harness["omega"]["outcome"] == "error"
    assert "injected uninstall fault" in by_harness["omega"]["message"]


def test_verify_isolates_one_failing_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_selection(monkeypatch, _GoodAdapter(), _make_faulty("verify"))
    result = CliRunner().invoke(
        cli.main, ["verify", "--harness", "all", "--format", "json"]
    )
    assert result.exit_code == cli._EXIT_EXPECTED
    assert "Traceback" not in result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "error"
    by_harness = {r["harness"]: r for r in envelope["results"]}
    assert by_harness["alpha"]["outcome"] == "unchanged"
    assert by_harness["omega"]["outcome"] == "error"


def test_harnesses_list_isolates_one_failing_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli,
        "_all_adapters",
        lambda: ([_GoodAdapter(), _make_faulty("is_installed")], []),
    )
    result = CliRunner().invoke(cli.main, ["harnesses", "list", "--format", "json"])
    assert result.exit_code == cli._EXIT_PARTIAL  # one listed, one errored
    assert "Traceback" not in result.output
    entries = json.loads(result.output)
    by_name = {e["name"]: e for e in entries}
    assert by_name["alpha"]["installed"] is True
    assert by_name["omega"]["outcome"] == "error"


def test_doctor_isolates_one_failing_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli,
        "_all_adapters",
        lambda: ([_GoodAdapter(), _make_faulty("is_installed")], []),
    )
    result = CliRunner().invoke(cli.main, ["doctor", "--format", "json"])
    assert result.exit_code == cli._EXIT_EXPECTED
    assert "Traceback" not in result.output
    payload = json.loads(result.output)
    assert payload["all_ok"] is False
    by_name = {h["name"]: h for h in payload["harnesses"]}
    assert by_name["alpha"]["installed"] is True
    assert "error" in by_name["omega"]


def test_emit_expected_error_plain_preserves_partial_exit_code() -> None:
    # A partial outcome must exit with _EXIT_PARTIAL (2) in plain mode too,
    # matching the JSON branch — click.ClickException would hard-code exit 1.
    from apothem.cli._helpers import _CliUserError, _emit_expected_error

    err = _CliUserError(
        code="install.partial",
        message="Apothem install partially completed.",
        field="install",
        reason="one harness failed after others were written",
        fix="Re-run install for the failed harness.",
    ).to_dict()
    with pytest.raises(SystemExit) as exc:
        _emit_expected_error(
            command="install", fmt="plain", error=err, exit_code=cli._EXIT_PARTIAL
        )
    assert exc.value.code == cli._EXIT_PARTIAL


def test_emit_expected_error_plain_default_stays_exit_one() -> None:
    # The default (expected) error path still raises ClickException (exit 1).
    import click

    from apothem.cli._helpers import _CliUserError, _emit_expected_error

    err = _CliUserError(
        code="x.y", message="m", field="f", reason="r", fix="z"
    ).to_dict()
    with pytest.raises(click.ClickException):
        _emit_expected_error(command="install", fmt="plain", error=err)


def test_get_error_console_is_stderr_and_never_quiet() -> None:
    # The error console honors the --quiet contract ("only errors are emitted")
    # by writing to stderr and never being quiet.
    from apothem.cli._common_flags import get_error_console

    err_con = get_error_console()
    assert err_con.stderr is True
    assert err_con.quiet is False


def test_quiet_still_surfaces_batch_errors_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # --quiet suppresses informational output, but a faulty adapter's failure
    # must still surface — on stderr (the error console ignores --quiet).
    _patch_selection(monkeypatch, _GoodAdapter(), _make_faulty("verify"))
    result = CliRunner().invoke(cli.main, ["verify", "--harness", "all", "--quiet"])
    assert "omega" in result.stderr
    assert "verify failed" in result.stderr
