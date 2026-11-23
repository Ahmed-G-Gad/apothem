# SPDX-License-Identifier: MIT

"""``--shard=K/N`` splits the suite into N parts that cover each test once.

``tests/conftest.py`` adds the option. The CI ``coverage`` check runs the suite
in two parts on two runners and combines their coverage data, so the parts must
not overlap or leave a test out, and every process must agree on them: each
xdist worker collects the whole suite and deselects on its own, and the two
runners split the suite in separate runs.

``test_the_pytester_cases_pass`` starts ``python -m pytest -p pytester`` on a
copy of this file, as ``test_real_home_guard.py`` does, so the ``pytester``
plugin stays out of the suite's own session. That session collects only the
``case_*`` functions. Each case writes a small suite with pytester and runs it
with ``-p tests.conftest``, which loads that file as a plugin: the option, and
the isolation fixtures for the one run that executes the tests. ``PYTHONPATH``
names the repo root, so ``tests.conftest`` imports in that session, in the
pytest processes a case starts and in their xdist workers.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
#: The functions the pytester session collects, and the suite does not.
_CASE_PREFIX = "case_"

#: Each module holds 13 tests: ten parametrized cases, two methods and a function.
_MODULE = """
import pytest


@pytest.mark.parametrize("number", range(10))
def test_number(number):
    pass


class TestPair:
    def test_first(self):
        pass

    def test_second(self):
        pass


def test_plain():
    pass
"""
_MODULES = ("test_alpha", "test_beta", "test_gamma")
_TESTS = 13 * len(_MODULES)
#: Values that are not ``K/N`` with ``1 <= K <= N``, in plain ASCII digits.
#: ``int`` alone takes the sign, the spaces, the ``_`` and the full-width digits.
_BAD_VALUES = (
    "0/2",
    "3/2",
    "1/0",
    "2",
    "a/b",
    "1/2/3",
    "+1/2",
    " 1/2",
    "1/2 ",
    "1_0/20",
    "\uff11/\uff12",  # full-width digits 1/2
)


def test_the_pytester_cases_pass(tmp_path: Path) -> None:
    """Run the ``case_*`` functions below in a pytester session of their own."""
    session = tmp_path / "session"
    session.mkdir()
    module = session / Path(__file__).name
    shutil.copyfile(__file__, module)
    # An empty ini roots the session here, away from the repo's pytest settings.
    (session / "pytest.ini").write_bytes(b"[pytest]\n")
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("PYTEST_")
    }
    env["PYTHONPATH"] = str(_REPO_ROOT)
    # Keeps the sessions from writing bytecode next to tests/conftest.py.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "pytester",
            "-p",
            "no:cacheprovider",
            "-o",
            f"python_functions={_CASE_PREFIX}*",
            "-q",
            "--basetemp",
            str(tmp_path / "basetemp"),
            module.name,
        ],
        cwd=session,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        check=False,
    )
    report = f"{done.stdout}\n{done.stderr}"
    cases = [name for name in globals() if name.startswith(_CASE_PREFIX)]
    assert done.returncode == 0, report
    assert f"{len(cases)} passed" in done.stdout, report


# --- In the pytester session --------------------------------------------------


@pytest.fixture
def suite(pytester: pytest.Pytester) -> pytest.Pytester:
    """Write three test modules, 39 tests, and an empty ini into the probe folder."""
    pytester.makeini("[pytest]\n")
    pytester.makepyfile(**dict.fromkeys(_MODULES, _MODULE))
    return pytester


def _args(*args: str) -> tuple[str, ...]:
    return ("-p", "tests.conftest", "-p", "no:cacheprovider", *args)


def _kept(result: pytest.RunResult) -> set[str]:
    """Return the node ids a ``--collect-only -q`` run listed."""
    assert result.ret == pytest.ExitCode.OK, (
        f"{result.stdout.str()}\n{result.stderr.str()}"
    )
    return {line for line in result.outlines if "::" in line}


def case_the_parts_cover_each_test_once(suite: pytest.Pytester) -> None:
    """For each N, the N parts hold every test, none twice, and none is empty."""
    plain = suite.runpytest(*_args("--collect-only", "-q"))
    everything = _kept(plain)
    assert len(everything) == _TESTS
    assert "deselected" not in plain.stdout.str()
    for count in (1, 2, 3):
        parts = []
        for index in range(1, count + 1):
            result = suite.runpytest(
                *_args("--collect-only", "-q", f"--shard={index}/{count}")
            )
            part = _kept(result)
            assert part, f"part {index} of {count} is empty"
            if len(part) < _TESTS:
                # Reported through pytest_deselected, as -k and -m report theirs.
                dropped = _TESTS - len(part)
                summary = (
                    f"{len(part)}/{_TESTS} tests collected ({dropped} deselected)*"
                )
                result.stdout.fnmatch_lines([summary])
            parts.append(part)
        assert set().union(*parts) == everything, f"a test is in none of {count} parts"
        assert sum(map(len, parts)) == _TESTS, f"a test is in two of {count} parts"


def _part(node_id: str, count: int) -> int:
    """Return the part of ``count`` that the docs say a node id belongs to."""
    return int.from_bytes(sha256(node_id.encode()).digest(), "big") % count + 1


def case_a_test_part_comes_from_its_node_id(suite: pytest.Pytester) -> None:
    """Each part holds exactly the tests whose node id hashes to it.

    The cover-once and same-in-every-process cases also hold for a split by
    collection order, such as round robin. This one pins the rule the docs give,
    so a test keeps its part when ``-k``, ``-m``, a path or a new test changes
    what is collected.
    """
    everything = _kept(suite.runpytest(*_args("--collect-only", "-q")))
    for count in (2, 3):
        for index in range(1, count + 1):
            expected = {i for i in everything if _part(i, count) == index}
            result = suite.runpytest(
                *_args("--collect-only", "-q", f"--shard={index}/{count}")
            )
            assert _kept(result) == expected, f"part {index} of {count}"


def case_a_conftest_that_star_imports_still_splits(suite: pytest.Pytester) -> None:
    """A star import registers the shard hooks twice, and the split still holds.

    The second ``--shard`` registration is ignored, and the second deselection
    pass finds nothing more to drop, so pytest reports each dropped test once.
    """
    suite.makeconftest("from tests.conftest import *\n")
    everything = _kept(suite.runpytest(*_args("--collect-only", "-q")))
    assert len(everything) == _TESTS
    parts = []
    for index in (1, 2):
        result = suite.runpytest(*_args("--collect-only", "-q", f"--shard={index}/2"))
        part = _kept(result)
        dropped = _TESTS - len(part)
        result.stdout.fnmatch_lines(
            [f"{len(part)}/{_TESTS} tests collected ({dropped} deselected)*"]
        )
        parts.append(part)
    assert parts[0].isdisjoint(parts[1]), "a test is in both parts"
    assert parts[0] | parts[1] == everything, "a test is in neither part"


def case_another_plugin_shard_option_still_fails(suite: pytest.Pytester) -> None:
    """Only this file's own second ``--shard`` is ignored.

    A plugin that adds its own ``--shard`` before ``tests/conftest.py`` loads
    makes the run fail with pytest's duplicate-option error. Were it ignored too,
    the shard hook would read that plugin's value as ``K/N``.
    """
    suite.makepyfile(
        other_shard='def pytest_addoption(parser):\n    parser.addoption("--shard")\n'
    )
    suite.syspathinsert()

    result = suite.runpytest("-p", "other_shard", *_args("--collect-only", "-q"))

    assert result.ret != pytest.ExitCode.OK
    output = f"{result.stdout.str()}\n{result.stderr.str()}"
    assert "already added" in output, output
    assert "--shard" in output, output


def case_every_process_picks_the_same_part(
    suite: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Separate runs, and the xdist workers of one run, keep the same tests.

    Python's own ``hash`` of a string changes with ``PYTHONHASHSEED``, so a part
    picked with it would differ between the two runs below, and between xdist
    workers, which stops the run because they collected different tests.
    """
    first = _kept(suite.runpytest(*_args("--collect-only", "-q", "--shard=1/2")))
    for seed in ("1", "2"):
        monkeypatch.setenv("PYTHONHASHSEED", seed)
        again = suite.runpytest_subprocess(
            *_args("--collect-only", "-q", "--shard=1/2")
        )
        assert _kept(again) == first, f"PYTHONHASHSEED={seed}"
    monkeypatch.delenv("PYTHONHASHSEED")

    result = suite.runpytest(*_args("-n", "2", "--shard=1/2"))

    result.assert_outcomes(passed=len(first))


def case_a_bad_value_is_a_usage_error(suite: pytest.Pytester) -> None:
    for value in _BAD_VALUES:
        result = suite.runpytest(*_args("--collect-only", f"--shard={value}"))

        assert result.ret == pytest.ExitCode.USAGE_ERROR, value
        result.stderr.fnmatch_lines([f"*argument --shard: expected K/N*{value!r}"])
