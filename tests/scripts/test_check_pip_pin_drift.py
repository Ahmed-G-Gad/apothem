# SPDX-License-Identifier: MIT

"""Tests for scripts/dev/check_pip_pin_drift.py.

CI installs pip from one hash-locked file, ``scripts/ci/requirements-ci-pip.txt``,
and every other Python dependency from a hash-locked file beside it. The checker
holds that file and every workflow's pip install line to the contract (rules a
to c for the pip lock, rule d for OpenSSF Scorecard's definition of a pinned
install); these tests pin its verdicts on small trees built under ``tmp_path``
and on the committed tree.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import check_pip_pin_drift  # noqa: E402

LOCK = check_pip_pin_drift.LOCK_RELPATH
HASH_A = "a" * 64
HASH_B = "b" * 64
# Built in two pieces so the REUSE parser does not read this literal as a licence tag.
SPDX_LINE = "# SPDX-License-" + "Identifier: MIT"
GOOD_INSTALL = f"python -m pip install --require-hashes -r {LOCK}"


def _lock_text(
    requirement: str = "pip==26.2.1",
    hashes: tuple[str, ...] = (HASH_A, HASH_B),
    extra: str = "",
) -> str:
    lines = [SPDX_LINE, "", "# a comment", f"{requirement} \\"]
    for index, digest in enumerate(hashes):
        tail = " \\" if index < len(hashes) - 1 else ""
        lines.append(f"    --hash=sha256:{digest}{tail}")
    if not hashes:
        lines[-1] = requirement
    return "\n".join(lines) + "\n" + extra


def _workflow_text(install_line: str) -> str:
    return (
        "name: sample\n"
        "on: push\n"
        "jobs:\n"
        "  job:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: |\n"
        f"          {install_line}\n"
        "          python -m pip install --no-deps -e .\n"
    )


def _build_tree(
    root: Path,
    lock: str | None = None,
    workflows: dict[str, str] | None = None,
) -> Path:
    if lock is not None:
        path = root / LOCK
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(lock, encoding="utf-8", newline="\n")
    workflow_dir = root / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    for name, text in (workflows or {}).items():
        (workflow_dir / name).write_text(text, encoding="utf-8", newline="\n")
    return root


def _problems(root: Path) -> list[str]:
    return check_pip_pin_drift.check(root).problems


def _good_tree(root: Path) -> Path:
    return _build_tree(root, _lock_text(), {"ci.yml": _workflow_text(GOOD_INSTALL)})


def test_committed_tree_passes() -> None:
    report = check_pip_pin_drift.check(REPO_ROOT)
    assert report.problems == []
    assert report.version is not None
    assert report.hash_count >= 1
    assert report.install_sites >= 1
    assert report.judged_installs >= 1


def test_script_exits_zero_on_the_committed_tree() -> None:
    script = REPO_ROOT / "scripts" / "dev" / "check_pip_pin_drift.py"
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "pip lock coherent" in result.stdout


def test_good_tree_has_no_problems(tmp_path: Path) -> None:
    report = check_pip_pin_drift.check(_good_tree(tmp_path))
    assert report.problems == []
    assert report.version == "26.2.1"
    assert report.hash_count == 2
    assert report.install_sites == 1


def test_main_reports_a_failure_on_stderr_and_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _build_tree(tmp_path, None, {"ci.yml": _workflow_text(GOOD_INSTALL)})
    monkeypatch.setattr(check_pip_pin_drift, "_REPO_ROOT", root)
    assert check_pip_pin_drift.main() == 1
    captured = capsys.readouterr()
    assert "pip lock drift detected" in captured.err
    assert LOCK in captured.err
    assert captured.out == ""


def test_main_prints_the_summary_and_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_pip_pin_drift, "_REPO_ROOT", _good_tree(tmp_path))
    assert check_pip_pin_drift.main() == 0
    captured = capsys.readouterr()
    assert "pip==26.2.1" in captured.out
    assert captured.err == ""


# --- rule (a): the lock file -------------------------------------------------


def test_missing_lock_file_is_reported(tmp_path: Path) -> None:
    root = _build_tree(tmp_path, None, {"ci.yml": _workflow_text(GOOD_INSTALL)})
    problems = _problems(root)
    assert len(problems) == 1
    assert "missing" in problems[0]
    assert LOCK in problems[0]


def test_lock_with_two_requirements_is_reported(tmp_path: Path) -> None:
    extra = f"build==1.5.0 \\\n    --hash=sha256:{HASH_A}\n"
    root = _build_tree(tmp_path, _lock_text(extra=extra), {})
    problems = _problems(root)
    assert any("2 requirement lines" in problem for problem in problems)


def test_empty_lock_is_reported(tmp_path: Path) -> None:
    root = _build_tree(tmp_path, SPDX_LINE + "\n# only comments\n", {})
    assert any("0 requirement lines" in problem for problem in _problems(root))


@pytest.mark.parametrize(
    "requirement", ["pip>=26.2", "pip", "setuptools==80.0.0", "pip==latest"]
)
def test_lock_requirement_must_be_an_exact_pip_pin(
    tmp_path: Path, requirement: str
) -> None:
    root = _build_tree(tmp_path, _lock_text(requirement=requirement), {})
    assert any("is not `pip==X.Y.Z`" in problem for problem in _problems(root))


def test_lock_without_hashes_is_reported(tmp_path: Path) -> None:
    root = _build_tree(tmp_path, _lock_text(hashes=()), {})
    problems = _problems(root)
    assert any("no `--hash=sha256" in problem for problem in problems)


@pytest.mark.parametrize("digest", ["a" * 63, "A" * 64, "g" * 64])
def test_lock_hash_must_be_64_lowercase_hex(tmp_path: Path, digest: str) -> None:
    root = _build_tree(tmp_path, _lock_text(hashes=(digest,)), {})
    problems = _problems(root)
    assert any("unexpected" in problem for problem in problems)
    assert any("no `--hash=sha256" in problem for problem in problems)


@pytest.mark.parametrize("version", ["26.1.9", "26.1", "25.3", "9.9.9", "1.0"])
def test_lock_below_the_cve_floor_is_reported(tmp_path: Path, version: str) -> None:
    root = _build_tree(tmp_path, _lock_text(requirement=f"pip=={version}"), {})
    problems = _problems(root)
    assert any("CVE-2026-13346" in problem for problem in problems)
    assert any("26.2" in problem for problem in problems)


@pytest.mark.parametrize(
    "version", ["26.2.0", "26.2.1", "26.2.10", "26.3", "26.10.0", "27.0.1"]
)
def test_lock_at_or_above_the_cve_floor_passes(tmp_path: Path, version: str) -> None:
    root = _build_tree(tmp_path, _lock_text(requirement=f"pip=={version}"), {})
    assert _problems(root) == []


def test_cve_floor_constant_is_26_2() -> None:
    assert check_pip_pin_drift.PIP_CVE_FLOOR == (26, 2)


# --- rule (b): the retired env pin --------------------------------------------


def test_retired_env_name_in_a_workflow_is_reported(tmp_path: Path) -> None:
    text = 'env:\n  PIP_PIN_VERSION: "26.2.1"\n' + _workflow_text(GOOD_INSTALL)
    root = _build_tree(tmp_path, _lock_text(), {"ci.yml": text})
    problems = _problems(root)
    assert len(problems) == 1
    assert ".github/workflows/ci.yml:2" in problems[0]
    assert "PIP_PIN_VERSION" in problems[0]


def test_retired_env_name_in_a_comment_is_reported(tmp_path: Path) -> None:
    text = "# PIP_PIN_VERSION was removed\n" + _workflow_text(GOOD_INSTALL)
    root = _build_tree(tmp_path, _lock_text(), {"other.yaml": text})
    assert any("other.yaml:1" in problem for problem in _problems(root))


def test_retired_env_name_in_a_readme_is_not_scanned(tmp_path: Path) -> None:
    root = _good_tree(tmp_path)
    (root / ".github" / "workflows" / "README.md").write_text(
        "PIP_PIN_VERSION is retired.\n", encoding="utf-8", newline="\n"
    )
    assert _problems(root) == []


# --- rule (c): pip installs go through the lock ------------------------------


@pytest.mark.parametrize(
    "line",
    [
        'python -m pip install "pip==26.2.1"',
        "python -m pip install pip==26.2.1",
        'python -m pip install "pip==${PIP_VERSION}"',
        'python -m pip install "pip==$env:PIP_VERSION"',
        "python -m pip install --upgrade pip",
        "python -m pip install -U pip",
        "python -m pip install pip",
        'python -m pip install "pip>=26.2"',
        'python -m pip install "pip~=26.2"',
        'python -m pip install "pip==26.2.1" # comment',
        '"$APOTHEM_PYTHON" -m pip install "pip==26.2.1"',
        f"python -m pip install -r {LOCK}",
        f"python -m pip install --no-deps -r {LOCK}",
        "python -m pip install --require-hashes -r scripts/release/requirements-build-linux.txt pip",
        f"python -m pip install --require-hashes {LOCK}",
        "python -m pip install --require-hashes -r scripts/ci/other-pip.txt pip",
    ],
)
def test_pip_install_without_the_lock_is_reported(tmp_path: Path, line: str) -> None:
    root = _build_tree(tmp_path, _lock_text(), {"ci.yml": _workflow_text(line)})
    problems = _problems(root)
    assert len(problems) == 1, problems
    assert ".github/workflows/ci.yml:8" in problems[0]
    assert f"--require-hashes -r {LOCK}" in problems[0]


def test_continued_install_line_is_joined(tmp_path: Path) -> None:
    text = _workflow_text('python -m pip install \\\n            "pip==26.2.1"')
    root = _build_tree(tmp_path, _lock_text(), {"ci.yml": text})
    problems = _problems(root)
    assert len(problems) == 1
    assert "ci.yml:8" in problems[0]


@pytest.mark.parametrize(
    "line",
    [
        GOOD_INSTALL,
        f'"$APOTHEM_PYTHON" -m pip install --require-hashes -r {LOCK}',
        f"python -m pip install --require-hashes -r {LOCK} # hash-locked",
        f'python -m pip install --require-hashes -r "{LOCK}"',
        f"python -m pip install --require-hashes \\\n            -r {LOCK}",
    ],
)
def test_pip_install_through_the_lock_passes(tmp_path: Path, line: str) -> None:
    root = _build_tree(tmp_path, _lock_text(), {"ci.yml": _workflow_text(line)})
    assert _problems(root) == []
    assert check_pip_pin_drift.check(root).install_sites == 1


@pytest.mark.parametrize(
    "line",
    [
        "python -m pip install dist/*.whl",
        "python -m pip install --require-hashes -r scripts/release/requirements-build-linux.txt",
        "python -m pip install --require-hashes -r scripts/ci/requirements-ci-dev.txt",
        'grep -q -- "-m pip install" prereq.err',
        "python -m pip --version",
        "# python -m pip install pip==26.2.1",
    ],
)
def test_other_pip_commands_are_not_flagged(tmp_path: Path, line: str) -> None:
    root = _build_tree(tmp_path, _lock_text(), {"ci.yml": _workflow_text(line)})
    report = check_pip_pin_drift.check(root)
    assert report.problems == []
    assert report.install_sites == 0


@pytest.mark.parametrize(
    "line",
    [
        'python -m pip install "pip-audit==2.10.1"',
        'python -m pip install "pip-licenses==5.5.5"',
        "python -m pip install pip-licenses==5.5.5",
        'python -m pip install -e ".[dev]"',
        "python -m pip install click rich pyyaml jsonschema",
        'python -m pip install "pre-commit==4.7.0"',
    ],
)
def test_rule_c_leaves_other_installs_to_rule_d(tmp_path: Path, line: str) -> None:
    root = _build_tree(tmp_path, _lock_text(), {"ci.yml": _workflow_text(line)})
    report = check_pip_pin_drift.check(root)
    assert not any("installs pip without the lock" in p for p in report.problems)
    assert report.install_sites == 0


@pytest.mark.parametrize("separator", ["&&", "||", ";", "|"])
def test_chained_unhashed_pip_install_is_reported(
    tmp_path: Path, separator: str
) -> None:
    line = f"{GOOD_INSTALL} {separator} python -m pip install pip==25.0"
    root = _build_tree(tmp_path, _lock_text(), {"ci.yml": _workflow_text(line)})
    problems = _problems(root)
    assert len(problems) == 1, problems
    assert "ci.yml:8" in problems[0]
    assert check_pip_pin_drift.check(root).install_sites == 2


def test_chained_installs_through_the_lock_pass(tmp_path: Path) -> None:
    line = f"{GOOD_INSTALL} && {GOOD_INSTALL}"
    root = _build_tree(tmp_path, _lock_text(), {"ci.yml": _workflow_text(line)})
    assert _problems(root) == []
    assert check_pip_pin_drift.check(root).install_sites == 2


def test_comment_line_inside_a_run_block_is_skipped(tmp_path: Path) -> None:
    text = _workflow_text(
        f"# python -m pip install pip==26.2.1\n          {GOOD_INSTALL}"
    )
    root = _build_tree(tmp_path, _lock_text(), {"ci.yml": text})
    assert _problems(root) == []


def test_every_problem_in_a_tree_is_listed(tmp_path: Path) -> None:
    root = _build_tree(
        tmp_path,
        _lock_text(requirement="pip==25.3", hashes=()),
        {
            "a.yml": 'env:\n  PIP_PIN_VERSION: "25.3"\n'
            + _workflow_text('python -m pip install "pip==25.3"'),
            "b.yml": _workflow_text(GOOD_INSTALL),
        },
    )
    problems = _problems(root)
    assert len(problems) == 4, problems
    assert sum("a.yml" in problem for problem in problems) == 2
    assert not any("b.yml" in problem for problem in problems)


def test_missing_workflow_directory_is_reported(tmp_path: Path) -> None:
    lock = tmp_path / LOCK
    lock.parent.mkdir(parents=True)
    lock.write_text(_lock_text(), encoding="utf-8", newline="\n")
    problems = _problems(tmp_path)
    assert len(problems) == 1
    assert "workflow directory not found" in problems[0]


# --- rule (d): installs are pinned the way Scorecard counts them -------------

DEV_LOCK_INSTALL = (
    "python -m pip install --require-hashes -r scripts/ci/requirements-ci-dev.txt"
)


def _rule_d(problems: list[str]) -> list[str]:
    return [problem for problem in problems if "OpenSSF Scorecard" in problem]


def _install_problems(tmp_path: Path, line: str, name: str = "ci.yml") -> list[str]:
    root = _build_tree(tmp_path, _lock_text(), {name: _workflow_text(line)})
    return _rule_d(_problems(root))


@pytest.mark.parametrize(
    "line",
    [
        DEV_LOCK_INSTALL,
        "python -m pip install --require-hashes -r scripts/ci/requirements-ci-runtime.txt",
        "pip install --require-hashes -r scripts/ci/requirements-ci-test.txt",
        "python -m pip install --no-deps -e .",
        'python -m pip install --no-deps -e ".[dev]"',
        "python -m pip install --no-deps -e ./packages/engine",
        "python -m pip install --no-deps --editable .",
        "python -m pip install dist/*.whl",
        "python -m pip install dist/apothem-1.5.0-py3-none-any.whl",
        f'"$APOTHEM_PYTHON" -m pip install --require-hashes -r {LOCK}',
        "python -m pip install --require-hashes -r scripts/ci/requirements-ci-dev.txt # locked",
        'grep -q -- "-m pip install" prereq.err',
        'echo "run python -m pip install foo"',
        "run: python -m pip install --no-deps -e .",
        "- run: python -m pip install dist/*.whl",
    ],
)
def test_rule_d_accepts_scorecard_pinned_installs(tmp_path: Path, line: str) -> None:
    assert _install_problems(tmp_path, line) == []


def test_rule_d_counts_the_installs_it_judged(tmp_path: Path) -> None:
    root = _build_tree(
        tmp_path, _lock_text(), {"ci.yml": _workflow_text(DEV_LOCK_INSTALL)}
    )
    assert check_pip_pin_drift.check(root).judged_installs == 2


@pytest.mark.parametrize(
    "line",
    [
        "python -m pip install click rich pyyaml jsonschema",
        "python -m pip install -r requirements.txt",
        "python -m pip install -r scripts/ci/requirements-ci-dev.txt",
        "python -m pip install pytest==9.2.0",
        'python -m pip install "click==8.4.2" "rich==15.0.0"',
        "python -m pip install -e .",
        'python -m pip install -e ".[dev]"',
        "python -m pip install .",
        "python -m pip install --no-deps .",
        "python -m pip install --no-deps -e git+https://example.com/x.git#egg=x",
        "python -m pip install --no-deps -e . pytest",
        "python -m pip install dist/*.whl pytest",
        "python -m pip install --upgrade build",
        'python -m pip install "pip-licenses==5.5.5"',
        "python -m pip install",
        "pip3 install pytest",
        "python3 -m pip3 install pytest",
        "sudo python -m pip install pytest",
        "sudo -H pip install pytest",
        "env FOO=1 python -m pip install pytest",
        "FOO=1 python -m pip install pytest",
        "sudo env FOO=1 pip3 install pytest",
    ],
)
def test_rule_d_reports_installs_scorecard_flags(tmp_path: Path, line: str) -> None:
    problems = _install_problems(tmp_path, line)
    assert len(problems) == 1, problems
    assert "ci.yml:8" in problems[0]
    assert "--require-hashes -r scripts/ci/requirements-ci-" in problems[0]
    assert "refresh_ci_locks.py" in problems[0]


def test_rule_d_reports_an_unhashed_requirement_file_install(tmp_path: Path) -> None:
    root = _build_tree(
        tmp_path,
        _lock_text(),
        {
            "ci.yml": _workflow_text(
                "python -m pip install -r scripts/ci/requirements-ci-dev.txt"
            )
        },
    )
    problems = _problems(root)
    assert len(problems) == 1
    assert "-r scripts/ci/requirements-ci-dev.txt" in problems[0]


def test_rule_d_reports_an_editable_install_without_no_deps(tmp_path: Path) -> None:
    problems = _install_problems(tmp_path, "python -m pip install -e .")
    assert len(problems) == 1
    assert "pip install -e ." in problems[0]


def test_rule_d_reports_a_plain_project_install(tmp_path: Path) -> None:
    problems = _install_problems(tmp_path, "python -m pip install .")
    assert len(problems) == 1
    assert "pip install ." in problems[0]


@pytest.mark.parametrize(
    ("name", "line"),
    [
        ("ci.yml", 'python -m pip install "bandit[toml]==1.9.4"'),
        ("ci.yml", 'python -m pip install "pip-audit==2.10.1"'),
        ("conformity.yml", "python -m pip install ruff==0.15.20"),
        ("license-audit.yml", "python -m pip install pip-licenses==5.5.5"),
        ("markdown-lint.yml", 'python -m pip install "pre-commit==4.7.0"'),
        ("pip-audit.yml", 'python -m pip install "pip-audit==2.10.1"'),
        ("npm-shim.yml", '"$APOTHEM_PYTHON" -m pip install "${specs[@]}"'),
    ],
)
def test_rule_d_allows_the_listed_tool_pins(
    tmp_path: Path, name: str, line: str
) -> None:
    assert _install_problems(tmp_path, line, name) == []


@pytest.mark.parametrize(
    ("name", "line"),
    [
        # A version bump of a listed tool is a new pin: the list moves with it.
        ("conformity.yml", "python -m pip install ruff==0.16.0"),
        ("ci.yml", 'python -m pip install "pip-audit==2.11.0"'),
        # A listed requirement is allowed only in its own workflow.
        ("ci.yml", "python -m pip install ruff==0.15.20"),
        ("conformity.yml", 'python -m pip install "pip-audit==2.10.1"'),
        # The allow-list covers a requirement, not a mixed install.
        ("ci.yml", 'python -m pip install "pip-audit==2.10.1" pytest==9.2.0'),
        ("ci.yml", 'python -m pip install -e . "pip-audit==2.10.1"'),
        # Another exact pin that is not listed.
        ("ci.yml", "python -m pip install pytest==9.2.0"),
        ("npm-shim.yml", 'python -m pip install "$other"'),
    ],
)
def test_rule_d_rejects_a_pin_that_is_not_listed(
    tmp_path: Path, name: str, line: str
) -> None:
    problems = _install_problems(tmp_path, line, name)
    assert len(problems) == 1, problems


def test_the_allow_list_names_only_exact_single_tool_pins() -> None:
    listed = {
        (name, requirement)
        for table in (
            check_pip_pin_drift.STEP_D_TOOL_PINS,
            check_pip_pin_drift.ENGINE_PREREQUISITE_INSTALLS,
        )
        for name, requirements in table.items()
        for requirement in requirements
    }
    assert ("ci.yml", "bandit[toml]==1.9.4") in listed
    assert ("pip-audit.yml", "pip-audit==2.10.1") in listed
    for name, requirement in listed:
        assert name.endswith(".yml")
        assert "==" in requirement or requirement.startswith("${")


def test_rule_d_judges_each_chained_install(tmp_path: Path) -> None:
    line = f"{DEV_LOCK_INSTALL} && python -m pip install pytest"
    root = _build_tree(tmp_path, _lock_text(), {"ci.yml": _workflow_text(line)})
    problems = _rule_d(_problems(root))
    assert len(problems) == 1
    assert "pip install pytest" in problems[0]


def test_rule_d_does_not_double_report_a_pip_itself_install(tmp_path: Path) -> None:
    root = _build_tree(
        tmp_path,
        _lock_text(),
        {"ci.yml": _workflow_text('python -m pip install "pip==26.2.1"')},
    )
    problems = _problems(root)
    assert len(problems) == 1
    assert "installs pip without the lock" in problems[0]
    assert _rule_d(problems) == []


def test_rule_d_applies_to_powershell_lines(tmp_path: Path) -> None:
    root = _build_tree(
        tmp_path,
        _lock_text(),
        {"ci.yml": _workflow_text('python -m pip install "click==$env:CLICK_VERSION"')},
    )
    assert len(_rule_d(_problems(root))) == 1
