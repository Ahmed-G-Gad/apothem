# SPDX-License-Identifier: MIT

"""Behavior tests for the wrapper-factory uninstall shims.

Covers the H2 project-scope uninstall factory: the direct-module-call fallback
must derive the project root from the adapter's declared ``relative_target``
component count, not a hardcoded ``parents[N]`` magic index, so a manifest
target-depth change can never silently derive the wrong root. Also covers
what every uninstall shim does with an ``error`` result: it raises, so the CLI
does not report a refused uninstall as done. A native-config uninstall whose
native-config step raises after its first step removed files exits as partial.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
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
