# SPDX-License-Identifier: MIT

"""Behavioral pass+fail coverage for the semver-stability matcher.

The matcher's public-surface comparison (``compare_surfaces`` over the
inventories from ``extract_public_surface``) is version-independent and
carries the breaking-change logic; the v1.0.0 gate sits above it. These
tests drive that core directly: a stable surface produces zero findings,
an unstable surface (removed symbol / added required parameter / dropped
``__all__`` entry) produces findings. A separate test confirms the
``--staged`` path bounds git with ``GIT_TIMEOUT_SECONDS`` and turns a
``TimeoutExpired`` into ``GitTimeoutError`` rather than an empty, passing
finding list: a change set that was not read has not been checked.

The cohort-contract tests assert the package exit/payload shape the matcher
was brought onto: a JSON ``GrepResult`` payload on stdout, ``EXIT_FAIL == 2``
(not the legacy ``1``) on findings, ``EXIT_PASS == 0`` on a clean surface,
and the ``_main(argv)`` entry point.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Final, NoReturn

import pytest

from tests._shared.git_env import hermetic_git_env

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "semver_stability_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("semver_stability_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["semver_stability_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()

_STABLE_SRC: Final[str] = "\n".join(
    [
        "__all__ = ['public_fn', 'PublicClass']",
        "",
        "def public_fn(a, b=1):",
        "    return a + b",
        "",
        "class PublicClass:",
        "    def method(self):",
        "        return 1",
    ]
)


def test_identical_surface_passes() -> None:
    old = _MOD.extract_public_surface(_STABLE_SRC)
    new = _MOD.extract_public_surface(_STABLE_SRC)
    assert old is not None
    assert new is not None
    findings = _MOD.compare_surfaces(old, new, "src/apothem/x.py")
    assert findings == []


def test_backward_compatible_addition_passes() -> None:
    # Adding an optional-defaulted parameter and a new function is not breaking.
    new_src = (
        _STABLE_SRC.replace("def public_fn(a, b=1):", "def public_fn(a, b=1, c=2):")
        + "\n\ndef brand_new_fn():\n    return 0\n"
    )
    old = _MOD.extract_public_surface(_STABLE_SRC)
    new = _MOD.extract_public_surface(new_src)
    assert old is not None
    assert new is not None
    findings = _MOD.compare_surfaces(old, new, "src/apothem/x.py")
    assert findings == []


def test_removed_public_function_fails() -> None:
    new_src = _STABLE_SRC.replace("def public_fn(a, b=1):\n    return a + b\n", "")
    old = _MOD.extract_public_surface(_STABLE_SRC)
    new = _MOD.extract_public_surface(new_src)
    assert old is not None
    assert new is not None
    findings = _MOD.compare_surfaces(old, new, "src/apothem/x.py")
    assert findings, "removing a public function must be a breaking change"
    assert any("public_fn" in f.message and "removed" in f.message for f in findings)


def test_added_required_parameter_fails() -> None:
    new_src = _STABLE_SRC.replace("def public_fn(a, b=1):", "def public_fn(a, z, b=1):")
    old = _MOD.extract_public_surface(_STABLE_SRC)
    new = _MOD.extract_public_surface(new_src)
    assert old is not None
    assert new is not None
    findings = _MOD.compare_surfaces(old, new, "src/apothem/x.py")
    assert findings
    assert any("required parameter" in f.message for f in findings)


def test_removed_all_entry_fails() -> None:
    new_src = _STABLE_SRC.replace(
        "__all__ = ['public_fn', 'PublicClass']", "__all__ = ['public_fn']"
    )
    old = _MOD.extract_public_surface(_STABLE_SRC)
    new = _MOD.extract_public_surface(new_src)
    assert old is not None
    assert new is not None
    findings = _MOD.compare_surfaces(old, new, "src/apothem/x.py")
    assert findings
    assert any("__all__" in f.message for f in findings)


def test_check_staged_reports_a_git_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force the v1.0.0 gate open so check_staged reaches the git call,
    # then make the git invocation raise TimeoutExpired. The module's
    # timeout=GIT_TIMEOUT_SECONDS bound is turned into GitTimeoutError, not
    # into an empty finding list that would pass an unread change set.
    from apothem.conformity import _bounded_run
    from apothem.conformity._grep_base import GitTimeoutError

    monkeypatch.setattr(_MOD, "current_version", lambda: "1.2.3")

    def _raise_timeout(*args: object, **kwargs: object) -> NoReturn:
        assert kwargs.get("timeout") == _MOD.GIT_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(cmd="git", timeout=_MOD.GIT_TIMEOUT_SECONDS)

    monkeypatch.setattr(_bounded_run, "run_bounded", _raise_timeout)
    with pytest.raises(GitTimeoutError, match="git diff --cached did not finish"):
        _MOD.check_staged()


_API_BEFORE: Final[str] = (
    "def kept():\n    return 1\n\n\ndef dropped():\n    return 2\n"
)
_API_AFTER: Final[str] = "def kept():\n    return 1\n"


def _init_text(version: str) -> bytes:
    return f'__version__ = "{version}"\n'.encode()


def _hermetic_git(monkeypatch: pytest.MonkeyPatch, global_config: Path) -> None:
    # git in the check reads os.environ: give it the shared hermetic
    # environment, with a temp global config in place of the null device.
    env = hermetic_git_env()
    for name in list(os.environ):
        if name not in env:
            monkeypatch.delenv(name)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))


def _package_below_top(tmp_path: Path) -> tuple[Path, Path]:
    """Commit ``py/src/apothem`` at version 1.0.0 in a new repository.

    Returns the repository top and the package's folder (``py``).
    """
    if shutil.which("git") is None:
        pytest.skip("git not available")
    repo = tmp_path / "repo"
    package = repo / "py" / "src" / "apothem"
    package.mkdir(parents=True)
    (package / "__init__.py").write_bytes(_init_text("1.0.0"))
    (package / "api.py").write_bytes(_API_BEFORE.encode())

    def _git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=str(repo),
            env=hermetic_git_env(),
            check=True,
            capture_output=True,
        )

    _git("-c", "init.defaultBranch=main", "init", "-q")
    _git("config", "user.email", "me@ahmedgad.com")
    _git("config", "user.name", "Ahmed G. Gad")
    _git("config", "maintenance.auto", "false")
    _git("config", "gc.auto", "0")
    _git("add", ".")
    _git("commit", "-q", "-m", "chore: add the package")
    (package / "api.py").write_bytes(_API_AFTER.encode())
    return repo, repo / "py"


def _stage(repo: Path) -> None:
    subprocess.run(
        ["git", "add", "."],
        cwd=str(repo),
        env=hermetic_git_env(),
        check=True,
        capture_output=True,
    )


def test_check_staged_sees_a_major_bump_below_the_top(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # git runs in the package's folder, below the top of the work tree, so
    # the version file is read from there: the MAJOR bump admits the removal.
    # The removal alone is reported first, so the check does read the package.
    repo, folder = _package_below_top(tmp_path)
    _stage(repo)
    _hermetic_git(monkeypatch, Path(os.devnull))
    monkeypatch.chdir(folder)
    findings = _MOD.check_staged()
    assert any("dropped" in f.message for f in findings), findings
    (folder / "src" / "apothem" / "__init__.py").write_bytes(_init_text("2.0.0"))
    _stage(repo)
    assert _MOD.check_staged() == []


def test_check_staged_reads_names_with_diff_relative_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # diff.relative=true prints staged names from the current folder; they
    # must still be read, so a removal with no bump is reported.
    repo, folder = _package_below_top(tmp_path)
    _stage(repo)
    global_config = tmp_path / "gitconfig"
    global_config.write_bytes(b"[diff]\n\trelative = true\n")
    _hermetic_git(monkeypatch, global_config)
    monkeypatch.chdir(folder)
    findings = _MOD.check_staged()
    assert any("dropped" in f.message for f in findings), findings


def test_staged_diff_argv_turns_diff_relative_off_before_the_subcommand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The staged list is read with diff.relative off, set among git's own
    # options. The subcommand comes right after them, so run_git adds its
    # diff options, and git older than 2.28 is never given --no-relative.
    from apothem.conformity import _bounded_run
    from apothem.conformity._git import DIFF_OPTIONS, PROTECTIVE_OPTIONS

    if shutil.which("git") is None:
        pytest.skip("git not available")
    monkeypatch.setattr(_MOD, "current_version", lambda: "1.2.3")
    seen: list[list[str]] = []

    def _record(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(_bounded_run, "run_bounded", _record)
    assert _MOD.check_staged() == []
    argv = seen[0]
    start = 1 + len(PROTECTIVE_OPTIONS)
    assert tuple(argv[1:start]) == PROTECTIVE_OPTIONS
    assert argv[start : start + 1 + len(DIFF_OPTIONS)] == ["diff", *DIFF_OPTIONS]
    pair = argv.index("diff.relative=false")
    assert argv[pair - 1] == "-c"
    assert pair < start
    assert "--no-relative" not in argv


def test_exit_constants_follow_the_cohort_contract() -> None:
    # The cohort exit contract is EXIT_PASS == 0, EXIT_FAIL == 2 — the legacy
    # `return 1` on findings is retired.
    assert _MOD.EXIT_PASS == 0
    assert _MOD.EXIT_FAIL == 2


def test_grep_result_emits_json_payload() -> None:
    findings = [_MOD.Finding("HIGH", "M15", "src/apothem/x.py", "removed foo")]
    result = _MOD.GrepResult(grep=_MOD.GREP_NAME, passed=False, findings=findings)
    payload = json.loads(result.to_json())
    assert payload["grep"] == "semver-stability-grep"
    assert payload["passed"] is False
    assert payload["findings"][0]["severity"] == "HIGH"
    assert payload["findings"][0]["message"] == "removed foo"


def test_dataclasses_are_frozen() -> None:
    # The Finding and PublicSurface dataclasses are frozen per the cohort
    # convention; mutating an instance raises FrozenInstanceError.
    finding = _MOD.Finding("HIGH", "M15", "src/apothem/x.py", "msg")
    with pytest.raises(dataclasses.FrozenInstanceError):
        finding.severity = "LOW"  # type: ignore[misc]


def test_main_exits_fail_two_on_findings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # `_main(argv)` on the --staged path emits a JSON GrepResult and exits
    # EXIT_FAIL (2), not the legacy plain-text-to-stderr `return 1`.
    monkeypatch.setattr(
        _MOD,
        "check_staged",
        lambda: [_MOD.Finding("HIGH", "M15", "src/apothem/x.py", "removed foo")],
    )
    exit_code = _MOD._main(["semver_stability_grep", "--staged"])
    assert exit_code == _MOD.EXIT_FAIL
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is False
    assert payload["findings"]


def test_main_exits_pass_zero_on_clean_surface(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(_MOD, "check_staged", list)
    exit_code = _MOD._main(["semver_stability_grep", "--staged"])
    assert exit_code == _MOD.EXIT_PASS
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    assert payload["findings"] == []


def test_async_function_stored_in_surface() -> None:
    # An async public coroutine is inventoried under functions; the widened
    # dict[str, FunctionDef | AsyncFunctionDef] type covers it.
    src = "async def public_coro():\n    return 1\n"
    surface = _MOD.extract_public_surface(src)
    assert surface is not None
    assert "public_coro" in surface.functions
