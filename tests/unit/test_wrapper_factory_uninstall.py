# SPDX-License-Identifier: MIT

"""Behavior tests for the wrapper-factory uninstall shims.

Covers the H2 project-scope uninstall factory: the direct-module-call fallback
must derive the project root from the adapter's declared ``relative_target``
component count, not a hardcoded ``parents[N]`` magic index, so a manifest
target-depth change can never silently derive the wrong root. Also covers
what every uninstall shim does with an ``error`` result: it raises, so the CLI
does not report a refused uninstall as done. A native-config uninstall that
stops at its native-config step, after its first step removed a file or only
found Apothem's rules file behind a link, or in the shared pass after both
steps, exits as partial and names that link.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from apothem.cli import main
from apothem.harnesses._shared import install_driver, install_driver_written
from apothem.harnesses._shared.install_driver import MaterializationResult
from apothem.harnesses._shared.wrapper_factories import (
    make_native_config_uninstall,
    make_project_scope_uninstall,
    make_uninstall,
)
from apothem.harnesses.antigravity.uninstall import uninstall as antigravity_uninstall
from apothem.harnesses.claude_code.uninstall import uninstall as claude_code_uninstall
from apothem.harnesses.kimi_code.uninstall import uninstall as kimi_code_uninstall
from apothem.harnesses.open_claw import OpenClawAdapter
from apothem.harnesses.opencode import OpenCodeAdapter
from apothem.lib import install_ledger


def _record_project_root(monkeypatch: pytest.MonkeyPatch) -> list[Path | None]:
    """Patch ``run_uninstall`` to record the ``project_root`` it receives."""
    seen: list[Path | None] = []

    def fake_run_uninstall(
        harness_name: str,
        *,
        harness_root: Path | None = None,
        project_root: Path | None = None,
    ) -> list[MaterializationResult]:
        seen.append(project_root)
        return []

    monkeypatch.setattr(install_driver, "run_uninstall", fake_run_uninstall)
    return seen


@pytest.mark.parametrize(
    "relative_target",
    [
        Path(".cursor") / "rules" / "apothem-rules.mdc",  # depth 3
        Path(".github") / "copilot-instructions.md",  # depth 2
        Path("GEMINI.md"),  # depth 1
        Path(".rules"),  # depth 1 (flat dotfile)
        Path("a") / "b" / "c" / "d" / "target.md",  # depth 5 (future manifest depth)
    ],
)
def test_direct_call_derives_project_root_from_relative_target(
    relative_target: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A direct module call (no ``project``) recovers the exact project root.

    The factory ascends ``len(relative_target.parts)`` parents from the resolved
    on-disk target — the same path the adapter's ``resolve_output_path`` joins
    onto the project root — so the derived root equals the project root for any
    target depth, with no hardcoded index to keep in sync.
    """
    seen = _record_project_root(monkeypatch)
    uninstall = make_project_scope_uninstall(
        "some_harness", relative_target=relative_target
    )

    project_root = tmp_path / "operator-project"
    resolved_target = project_root / relative_target

    uninstall(resolved_target)

    assert seen == [project_root]


def test_direct_call_root_is_independent_of_a_hardcoded_depth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two targets at different depths both recover the same project root.

    This is the regression guard for the retired ``output_path.parents[N]``
    fallback: a single hardcoded index cannot be correct for both a depth-2 and
    a depth-4 target, but deriving depth from ``relative_target`` is correct for
    both — proving the derivation is not a fixed magic depth.
    """
    project_root = tmp_path / "operator-root"

    shallow = Path(".github") / "instructions.md"  # depth 2
    deep = Path(".tool") / "nested" / "rules" / "apothem.md"  # depth 4

    seen = _record_project_root(monkeypatch)

    make_project_scope_uninstall("shallow_harness", relative_target=shallow)(
        project_root / shallow
    )
    make_project_scope_uninstall("deep_harness", relative_target=deep)(
        project_root / deep
    )

    assert seen == [project_root, project_root]


def test_explicit_project_takes_precedence_over_derivation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the CLI supplies ``project``, the derivation is bypassed entirely.

    The supplied root is threaded straight through regardless of what
    ``output_path`` would derive, matching the adapter-path contract.
    """
    seen = _record_project_root(monkeypatch)
    relative_target = Path(".cursor") / "rules" / "apothem-rules.mdc"
    uninstall = make_project_scope_uninstall("cursor", relative_target=relative_target)

    explicit = tmp_path / "explicit-project"
    # An output_path that would derive a *different* root if the fallback fired.
    misleading_output = tmp_path / "somewhere" / "else" / relative_target

    uninstall(misleading_output, project=explicit)

    assert seen == [explicit]


def _refusal(path: Path) -> MaterializationResult:
    return MaterializationResult(
        outcome="error",
        operation="surgical_uninstall",
        path=str(path),
        message="target path crosses a link",
    )


def _refusing_run_uninstall(
    monkeypatch: pytest.MonkeyPatch, outcome: str = "error"
) -> None:
    """Patch ``run_uninstall`` to return one result with *outcome*."""

    def fake_run_uninstall(
        harness_name: str, **kwargs: object
    ) -> list[MaterializationResult]:
        del harness_name, kwargs
        result = _refusal(Path("refused"))
        if outcome != "error":
            result = MaterializationResult(
                outcome="skipped", operation="uninstall", path="kept", message="kept"
            )
        return [result]

    monkeypatch.setattr(install_driver, "run_uninstall", fake_run_uninstall)


def test_every_uninstall_shim_returns_its_error_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _refusing_run_uninstall(monkeypatch)
    shims = [
        lambda: make_uninstall("codex")(tmp_path / ".codex" / "AGENTS.md"),
        lambda: make_project_scope_uninstall(
            "cursor", relative_target=Path(".cursor") / "rules" / "a.mdc"
        )(tmp_path / ".cursor" / "rules" / "a.mdc"),
        lambda: make_native_config_uninstall("opencode", lambda profile: "{}")(
            tmp_path / "opencode" / "opencode.json"
        ),
        # The adapters with their own uninstall module return the same run.
        lambda: claude_code_uninstall(tmp_path / ".claude" / "settings.json"),
        lambda: antigravity_uninstall(
            tmp_path / ".gemini" / "config" / "plugins" / "apothem" / "plugin.json"
        ),
        lambda: kimi_code_uninstall(
            tmp_path / "AGENTS.md", project=tmp_path / "project"
        ),
    ]
    for shim in shims:
        run = shim()
        assert [error.message for error in run.errors] == ["target path crosses a link"]

    _refusing_run_uninstall(monkeypatch, outcome="skipped")
    for shim in shims:
        assert not shim().errors


def test_an_error_in_the_native_config_removal_is_returned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The surgical removal of the rendered config refused, the support pass
    # did not: the uninstall still fails.
    seen: list[tuple[MaterializationResult, ...]] = []

    def fake_run_uninstall(
        harness_name: str,
        *,
        harness_root: Path | None = None,
        prior_results: tuple[MaterializationResult, ...] = (),
    ) -> list[MaterializationResult]:
        seen.append(prior_results)
        return []

    target = tmp_path / "opencode" / "opencode.json"
    monkeypatch.setattr(install_driver, "run_uninstall", fake_run_uninstall)
    monkeypatch.setattr(
        install_driver,
        "surgically_remove_materialized_config",
        lambda *args, **kwargs: _refusal(target),
    )

    run = make_native_config_uninstall("opencode", lambda profile: "{}")(target)

    assert [error.path for error in run.errors] == [str(target)]
    assert [len(prior) for prior in seen] == [1]


def test_a_refused_uninstall_is_not_reported_as_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    OpenCodeAdapter().install({})
    _refusing_run_uninstall(monkeypatch)

    result = CliRunner().invoke(main, ["uninstall", "--harness", "opencode", "--yes"])

    assert result.exit_code != 0
    assert "Uninstalled" not in result.output
    assert "uninstall did not finish" in result.output


def _deny_the_native_config(monkeypatch: pytest.MonkeyPatch, config: Path) -> None:
    """Make the native-config step raise, as for a file the system keeps locked."""

    def denied(*_args: object, **_kwargs: object) -> None:
        raise PermissionError(13, "denied", str(config))

    monkeypatch.setattr(install_driver, "surgically_remove_materialized_config", denied)


def _uninstall_open_claw() -> tuple[int, str]:
    result = CliRunner().invoke(
        main, ["uninstall", "--harness", "open-claw", "--yes", "--no-color"]
    )
    return result.exit_code, result.stderr


def test_a_native_uninstall_stopped_after_its_first_step_exits_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An error at ``openclaw.json`` after the rules file went is a partial uninstall.

    The first step took Apothem's rules file out of the workspace, so the CLI
    exits 2 and says the uninstall stopped after removing files, and the
    unfinished uninstall it records names that file's backup.
    """
    workspace = Path.home() / ".openclaw" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "AGENTS.md").write_text("# My agent\n", encoding="utf-8")
    OpenClawAdapter().install({})
    rules = workspace / "apothem" / "AGENTS.md"
    written = rules.read_bytes()
    config = Path.home() / ".openclaw" / "openclaw.json"
    before = config.read_bytes()
    _deny_the_native_config(monkeypatch, config)

    code, stderr = _uninstall_open_claw()

    assert code == 2, stderr
    assert "open-claw uninstall stopped after removing files" in stderr
    assert "denied" in stderr
    assert not rules.exists()
    assert config.read_bytes() == before
    records = install_ledger.read_records("open_claw")
    assert [record.kind for record in records] == ["install", "uninstall-incomplete"]
    backups = {target.path: target.backup_ref for target in records[-1].targets}
    assert backups[str(rules)] is not None
    assert Path(backups[str(rules)]).read_bytes() == written
    assert all(ref is not None and Path(ref).exists() for ref in backups.values())


def test_ctrl_c_after_the_first_step_is_recorded_and_exits_through_click(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ctrl-C at ``openclaw.json`` after the rules file went is recorded unfinished.

    The CLI does not report the interrupt as a stopped uninstall: Click ends
    the command with ``Aborted!`` and exit 1, as for any interrupt, although
    the first step removed the rules file. The ledger says what happened: the
    unfinished uninstall it records names that file's backup.
    """
    workspace = Path.home() / ".openclaw" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "AGENTS.md").write_text("# My agent\n", encoding="utf-8")
    OpenClawAdapter().install({})
    rules = workspace / "apothem" / "AGENTS.md"
    written = rules.read_bytes()

    def interrupted(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(
        install_driver, "surgically_remove_materialized_config", interrupted
    )

    code, stderr = _uninstall_open_claw()

    assert code == 1, stderr
    assert stderr.strip() == "Aborted!"
    assert not rules.exists()
    records = install_ledger.read_records("open_claw")
    assert [record.kind for record in records] == ["install", "uninstall-incomplete"]
    backups = {target.path: target.backup_ref for target in records[-1].targets}
    assert Path(str(backups[str(rules)])).read_bytes() == written


def test_a_native_uninstall_stopped_before_any_change_still_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no rules file to take out, the same error fails the uninstall (exit 1).

    Nothing changed, so nothing is recorded and the error is raised as it is.
    """
    OpenClawAdapter().install({})
    config = Path.home() / ".openclaw" / "openclaw.json"
    _deny_the_native_config(monkeypatch, config)

    code, stderr = _uninstall_open_claw()

    assert code == 1, stderr
    assert "open-claw uninstall failed: [Errno 13] denied" in stderr
    records = install_ledger.read_records("open_claw")
    assert [record.kind for record in records] == ["install"]


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


def _install_with_a_linked_workspace(*, alone: bool = False) -> Path:
    """Install open-claw into two workspaces; link the second one's rules folder.

    Returns the link: the second workspace's ``apothem`` folder, moved aside
    and linked back, so the uninstall cannot take the rules file out of it.
    With *alone*, that workspace is the only one.
    """
    home = Path.home()
    names = ("ws-b",) if alone else ("ws-a", "ws-b")
    for name in names:
        (home / name).mkdir()
        (home / name / "AGENTS.md").write_text("# My agent\n", encoding="utf-8")
    config = home / ".openclaw" / "openclaw.json"
    config.parent.mkdir()
    workspaces: dict[str, object] = {"defaults": {"workspace": "~/ws-b"}}
    if not alone:
        workspaces = {
            "defaults": {"workspace": "~/ws-a"},
            "entries": {"b": {"workspace": "~/ws-b"}},
        }
    config.write_text(json.dumps({"agents": workspaces}), encoding="utf-8")
    OpenClawAdapter().install({})
    link = home / "ws-b" / "apothem"
    moved = home / "ws-b" / "apothem-real"
    link.rename(moved)
    _link_folder(link, moved)
    return link


def _uninstall_open_claw_as(output_format: str) -> Result:
    """Run the open-claw uninstall with plain or JSON output."""
    args = ["uninstall", "--harness", "open-claw", "--yes", "--no-color"]
    return CliRunner().invoke(main, [*args, "--format", output_format])


def _assert_the_link_is_named(
    result: Result, link: Path, output_format: str, *, loaded: bool = True
) -> None:
    """Check that the uninstall named *link*, where it leads and its fix.

    In JSON output the harness's ``results`` row ends its message with the
    link's line and names the link and the folder it leads to in ``detail``.
    In plain output that line follows ``✗ open-claw uninstall did not
    finish:`` on standard error. The line says OpenClaw still loads the rules
    file behind the link when *loaded*: ``openclaw.json`` still names it.
    """
    loads = ", and open-claw still loads them" if loaded else ""
    line = (
        f"1 installed path(s) stay because they are reached through the link {link}"
        f"{loads}; replace the link with a real folder that holds the same files, "
        "then run the command again"
    )
    if output_format == "json":
        row = json.loads(result.stdout)["results"][0]
        assert row["detail"] == {
            "symlink": str(link),
            "leads_to": str(link.parent / "apothem-real"),
        }
        assert " ".join(str(row["message"]).split()).endswith(f"; {line}")
    else:
        flat = " ".join(result.stderr.split())
        assert f"✗ open-claw uninstall did not finish: {line}" in flat


@pytest.mark.parametrize("output_format", ["plain", "json"])
def test_a_stopped_native_uninstall_names_the_rules_file_behind_a_link(
    monkeypatch: pytest.MonkeyPatch, output_format: str
) -> None:
    """A stopped uninstall still reports Apothem's rules file behind a link.

    The first workspace's rules file goes, the second one's is reached
    through a link, and the ``openclaw.json`` step then stops. The report
    names the link, where it leads and its fix, as an uninstall that finished
    its steps does, so the operator does not learn of it only from the next
    run.
    """
    link = _install_with_a_linked_workspace()
    _deny_the_native_config(monkeypatch, Path.home() / ".openclaw" / "openclaw.json")

    result = _uninstall_open_claw_as(output_format)

    assert result.exit_code == 2, result.output
    assert (link / "AGENTS.md").is_file()
    if output_format == "plain":
        assert "open-claw uninstall stopped after removing files" in result.stderr
    _assert_the_link_is_named(result, link, output_format)


@pytest.mark.parametrize("output_format", ["plain", "json"])
def test_a_native_uninstall_stopped_before_any_removal_names_the_link(
    monkeypatch: pytest.MonkeyPatch, output_format: str
) -> None:
    """The link is named when the first step found it and removed nothing.

    The only workspace's rules folder is a link, so the first step changes
    nothing and only finds Apothem's file behind the link; the
    ``openclaw.json`` step then stops. The report names the link, and the CLI
    exits 2, as for an uninstall that ran all its steps and left Apothem's
    files behind a link. Nothing changed, so nothing is recorded.
    """
    link = _install_with_a_linked_workspace(alone=True)
    config = Path.home() / ".openclaw" / "openclaw.json"
    before = config.read_bytes()
    _deny_the_native_config(monkeypatch, config)

    result = _uninstall_open_claw_as(output_format)

    assert result.exit_code == 2, result.output
    assert config.read_bytes() == before
    assert (link / "AGENTS.md").is_file()
    records = install_ledger.read_records("open_claw")
    assert [record.kind for record in records] == ["install"]
    if output_format == "plain":
        flat = " ".join(result.stderr.split())
        assert "✗ open-claw uninstall failed: uninstall stopped: [Errno 13]" in flat
    else:
        assert json.loads(result.stdout)["status"] == "partial"
    _assert_the_link_is_named(result, link, output_format)


def _fail_the_support_tree_backups(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make each backup of a file in the support tree fail, as on a full disk.

    The workspace rules files and ``openclaw.json`` are backed up through
    other code, so the first two steps finish and the shared pass stops.
    """
    real = install_driver_written.backup_existing

    def full(target: Path, **kwargs: object) -> object:
        if ".apothem" in target.parts:
            raise OSError("backup disk full")
        return real(target, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(install_driver_written, "backup_existing", full)


@pytest.mark.parametrize("output_format", ["plain", "json"])
def test_an_uninstall_stopped_in_the_shared_pass_reports_the_steps_before_it(
    monkeypatch: pytest.MonkeyPatch, output_format: str
) -> None:
    """A stop in the shared pass keeps what the two steps before it did.

    The first step took the first workspace's rules file out and found the
    second one's behind a link, and the native step took Apothem's entries out
    of ``openclaw.json``; then a backup in the support tree fails. The CLI
    exits 2 and says the uninstall stopped after removing files, and it names
    the link, as a stop at the native step does. OpenClaw no longer loads the
    file behind the link: ``openclaw.json`` no longer names it.
    """
    link = _install_with_a_linked_workspace()
    config = Path.home() / ".openclaw" / "openclaw.json"
    before = config.read_bytes()
    _fail_the_support_tree_backups(monkeypatch)

    result = _uninstall_open_claw_as(output_format)

    assert result.exit_code == 2, result.output
    assert not (Path.home() / "ws-a" / "apothem" / "AGENTS.md").exists()
    assert config.read_bytes() != before
    assert (link / "AGENTS.md").is_file()
    records = install_ledger.read_records("open_claw")
    assert [record.kind for record in records] == ["install", "uninstall-incomplete"]
    if output_format == "plain":
        flat = " ".join(result.stderr.split())
        stopped = "uninstall stopped after removing files: uninstall stopped: backup"
        assert f"✗ open-claw {stopped} disk full" in flat
    else:
        assert json.loads(result.stdout)["status"] == "partial"
    _assert_the_link_is_named(result, link, output_format, loaded=False)
