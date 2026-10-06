# SPDX-License-Identifier: MIT

"""Tests for the root-based standalone-matcher API in ``_grep_base``.

``_grep_base`` hoists two matcher skeletons. The path-based
``GrepResult`` / ``run_grep`` pair is already exercised via the path matchers;
this module pins the root-based counterpart (``RootGrepResult`` /
``parse_root_args`` / ``run_root_grep`` / ``finish_root_report``) every
standalone validator's command-line entry runs through: the root resolves to
an absolute path, a missing root is a usage error, and a run that inspected
nothing cannot pass unless it declares an expected empty scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from apothem.conformity import _grep_base


@dataclass(frozen=True)
class _Finding:
    """A minimal finding shape for the root-result serialisation test."""

    where: str
    detail: str


def test_root_result_json_shape_and_advisory_default() -> None:
    """``to_json`` emits ``{grep, root, passed, advisory, findings}`` exactly."""
    result = _grep_base.RootGrepResult(
        grep="demo-grep", root="synthetic/root/x", passed=True
    )
    import json

    payload = json.loads(result.to_json())
    assert payload == {
        "grep": "demo-grep",
        "root": "synthetic/root/x",
        "passed": True,
        "advisory": False,
        "findings": [],
    }


def test_root_result_serialises_findings_and_advisory_flag() -> None:
    """A failing advisory result carries the findings and the advisory flag."""
    import json

    result = _grep_base.RootGrepResult(
        grep="demo-grep",
        root="synthetic/root/x",
        passed=False,
        advisory=True,
        findings=[_Finding(where="a.py", detail="d")],
    )
    payload = json.loads(result.to_json())
    assert payload["advisory"] is True
    assert payload["passed"] is False
    assert payload["findings"] == [{"where": "a.py", "detail": "d"}]


def test_parse_root_args_resolves_a_relative_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A relative root resolves to the same absolute path as its full form."""
    (tmp_path / "sub").mkdir()
    monkeypatch.chdir(tmp_path)
    args = _grep_base.parse_root_args(["prog", "sub"], prog="demo-grep")
    assert args.root == (tmp_path / "sub").resolve()


def test_parse_root_args_defaults_to_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With no root argument the current directory is inspected."""
    monkeypatch.chdir(tmp_path)
    assert _grep_base.parse_root_args(["prog"], prog="demo-grep").root == (
        tmp_path.resolve()
    )


def test_parse_root_args_missing_root_is_a_usage_error(tmp_path: Path) -> None:
    """A root that does not exist exits ``EXIT_USAGE``, never a silent pass."""
    with pytest.raises(SystemExit) as excinfo:
        _grep_base.parse_root_args(["prog", str(tmp_path / "absent")], prog="demo")
    assert excinfo.value.code == _grep_base.EXIT_USAGE


def test_parse_root_args_unknown_flag_is_a_usage_error(tmp_path: Path) -> None:
    """An unknown flag exits ``EXIT_USAGE`` (argparse's own code would be 2)."""
    with pytest.raises(SystemExit) as excinfo:
        _grep_base.parse_root_args(["prog", "--bogus", str(tmp_path)], prog="demo")
    assert excinfo.value.code == _grep_base.EXIT_USAGE


def test_run_root_grep_passes_exit_pass(tmp_path: Path) -> None:
    """A passing check that inspected something returns ``EXIT_PASS``."""

    def _check(root: Path) -> _grep_base.RootGrepResult:
        return _grep_base.RootGrepResult(
            grep="demo-grep", root=str(root), passed=True, inspected=3
        )

    code = _grep_base.run_root_grep(_check, ["prog", str(tmp_path)])
    assert code == _grep_base.EXIT_PASS


def test_run_root_grep_fails_exit_fail(tmp_path: Path) -> None:
    """A failing check returns ``EXIT_FAIL`` (mirrors ``run_grep``)."""

    def _check(root: Path) -> _grep_base.RootGrepResult:
        return _grep_base.RootGrepResult(
            grep="demo-grep",
            root=str(root),
            passed=False,
            findings=[_Finding(where="x", detail="d")],
            inspected=1,
        )

    code = _grep_base.run_root_grep(_check, ["prog", str(tmp_path)])
    assert code == _grep_base.EXIT_FAIL


def test_run_root_grep_prints_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The report JSON, stamped with ``inspected``, is printed to stdout."""
    import json

    def _check(root: Path) -> _grep_base.RootGrepResult:
        return _grep_base.RootGrepResult(
            grep="demo-grep", root=str(root), passed=True, inspected=2
        )

    _grep_base.run_root_grep(_check, ["prog", str(tmp_path)])
    printed = json.loads(capsys.readouterr().out)
    assert printed["grep"] == "demo-grep"
    assert printed["root"] == str(tmp_path.resolve())
    assert printed["inspected"] == 2
    assert "empty_scope_expected" not in printed


def test_run_root_grep_nothing_inspected_is_not_a_pass(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A clean verdict over zero targets is reported as a failure."""
    import json

    def _check(root: Path) -> _grep_base.RootGrepResult:
        return _grep_base.RootGrepResult(grep="demo-grep", root=str(root), passed=True)

    code = _grep_base.run_root_grep(_check, ["prog", str(tmp_path)])
    printed = json.loads(capsys.readouterr().out)
    assert code == _grep_base.EXIT_FAIL
    assert printed["passed"] is False
    assert printed["inspected"] == 0
    assert printed["empty_scope_expected"] is False


def test_finish_root_report_declared_empty_scope_passes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A validator that declares an empty scope expected may pass over nothing."""
    import json

    code = _grep_base.finish_root_report(
        json.dumps({"grep": "demo", "passed": True}),
        passed=True,
        inspected=0,
        empty_scope_expected=True,
    )
    printed = json.loads(capsys.readouterr().out)
    assert code == _grep_base.EXIT_PASS
    assert printed["passed"] is True
    assert printed["empty_scope_expected"] is True


def test_finish_root_report_vacuous_advisory_still_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An advisory validator that inspected nothing exits ``EXIT_FAIL``."""
    import json

    code = _grep_base.finish_root_report(
        json.dumps({"grep": "demo", "passed": True, "advisory": True}),
        passed=True,
        inspected=0,
        advisory=True,
    )
    capsys.readouterr()
    assert code == _grep_base.EXIT_FAIL


def test_root_api_mirrors_existing_root_standalone_shape() -> None:
    """The base payload matches a live root-standalone's payload shape.

    ``no_toplevel_docs_grep`` is one of the n-z root standalones the base is
    modelled on; its ``to_json`` keys must be exactly the base's keys so a later
    migration is a drop-in.
    """
    import json

    from apothem.conformity import no_toplevel_docs_grep as ntd

    live = json.loads(ntd.check(Path.cwd()).to_json())
    base = json.loads(
        _grep_base.RootGrepResult(grep="x", root=str(Path.cwd()), passed=True).to_json()
    )
    assert set(live) == set(base)
