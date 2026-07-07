# SPDX-License-Identifier: MIT

"""Tests for the root-based standalone-matcher API in ``_grep_base``.

``_grep_base`` hoists two matcher skeletons. The path-based
``GrepResult`` / ``run_grep`` pair is already exercised via the path matchers;
this module pins the root-based counterpart (``RootGrepResult`` / ``read_root``
/ ``run_root_grep``) added for the n-z standalone corpus walkers, so a later
migration onto the shared base has a fixed contract to hold to. No validator is
migrated yet — these tests exercise the base API directly.
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


def test_read_root_returns_argv_path() -> None:
    """``read_root`` returns ``argv[1]`` as a Path when supplied."""
    assert _grep_base.read_root(["prog", "/some/root"]) == Path("/some/root")


def test_read_root_defaults_to_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    """``read_root`` falls back to the current directory when no arg is given."""
    monkeypatch.chdir(Path.cwd())
    assert _grep_base.read_root(["prog"]) == Path.cwd()


def test_run_root_grep_passes_exit_pass() -> None:
    """A passing check prints its report and returns ``EXIT_PASS``."""

    def _check(root: Path) -> _grep_base.RootGrepResult:
        return _grep_base.RootGrepResult(grep="demo-grep", root=str(root), passed=True)

    code = _grep_base.run_root_grep(_check, ["prog", "synthetic/root"])
    assert code == _grep_base.EXIT_PASS


def test_run_root_grep_fails_exit_fail() -> None:
    """A failing check returns ``EXIT_FAIL`` (mirrors ``run_grep``)."""

    def _check(root: Path) -> _grep_base.RootGrepResult:
        return _grep_base.RootGrepResult(
            grep="demo-grep",
            root=str(root),
            passed=False,
            findings=[_Finding(where="x", detail="d")],
        )

    code = _grep_base.run_root_grep(_check, ["prog", "synthetic/root"])
    assert code == _grep_base.EXIT_FAIL


def test_run_root_grep_prints_report(capsys: pytest.CaptureFixture[str]) -> None:
    """The report JSON is printed to stdout by the runner."""
    import json

    def _check(root: Path) -> _grep_base.RootGrepResult:
        return _grep_base.RootGrepResult(grep="demo-grep", root=str(root), passed=True)

    _grep_base.run_root_grep(_check, ["prog", "synthetic/root"])
    printed = json.loads(capsys.readouterr().out)
    assert printed["grep"] == "demo-grep"
    # ``root`` is rendered via ``str(Path(...))`` so it carries the platform
    # separator; compare against the same normalisation rather than a literal.
    assert printed["root"] == str(Path("synthetic/root"))


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
