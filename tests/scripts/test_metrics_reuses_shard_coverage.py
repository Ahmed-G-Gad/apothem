# SPDX-License-Identifier: MIT

"""The suite runs under coverage once per CI run, in the coverage shards.

`ci.yml`'s `coverage-shard` jobs each run their part of `pytest --shard=K/N`
and measure all of `src/apothem`. Two jobs read that data instead of running
the suite again:

* `coverage`, the required check, reports the engine files only (the folders
  in `[tool.coverage.run] source` in `pyproject.toml`) and holds them to the
  80% floor. `tests/scripts/test_required_check_coverage.py` pins its combine
  and its floor; this file pins which files its reports keep.
* `metrics` combines the same data over every package and hands it to
  `scripts/dev/collect_metrics.py`, which holds the conformity and audit
  packages to their own floors.

These tests pin that shape: the shards measure the whole package, the
required check's reports keep exactly the engine folders, and `metrics` runs
no tests and combines every shard's data file by name.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:  # Python 3.10: tomli is in the dev lock for python_full_version < 3.11.
    import tomli as tomllib

_REPO = Path(__file__).resolve().parents[2]
_CI = _REPO / ".github" / "workflows" / "ci.yml"


def _jobs() -> dict:
    return yaml.safe_load(_CI.read_text(encoding="utf-8"))["jobs"]


def _run(job: dict) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


def _shard_files(jobs: dict) -> list[str]:
    split = re.search(
        r"--shard=\$\{\{ matrix\.shard \}\}/(\d+)\b", _run(jobs["coverage-shard"])
    )
    assert split, "coverage-shard must run pytest --shard=${{ matrix.shard }}/N"
    return [f".coverage.shard-{k}" for k in range(1, int(split.group(1)) + 1)]


def test_the_shards_measure_the_whole_package() -> None:
    # A bare --cov would measure the engine folders alone, and metrics would
    # then report the conformity and audit packages as not measured.
    run = _run(_jobs()["coverage-shard"])
    pytest_line = next(line for line in run.splitlines() if "pytest" in line)
    assert "--cov=src/apothem " in pytest_line + " ", pytest_line


@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="the command uses tomllib; the coverage job runs it on Python 3.12",
)
def test_the_coverage_reports_keep_exactly_the_engine_folders() -> None:
    # Run the command the coverage job uses to build its --include list and
    # check it names every engine folder from pyproject and nothing more. A
    # list that dropped a folder would hide its files from the 80% floor; one
    # that took in conformity or audit would change the engine figure.
    run = _run(_jobs()["coverage"])
    command = re.search(r"^engine=\"\$\(python -c '([^']+)'\)\"$", run, re.MULTILINE)
    assert command, run
    printed = subprocess.run(
        [sys.executable, "-c", command.group(1)],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    with (_REPO / "pyproject.toml").open("rb") as handle:
        source = tomllib.load(handle)["tool"]["coverage"]["run"]["source"]
    assert printed.split(",") == [f"{folder}/*" for folder in source]
    for report in ("report", "xml", "html"):
        lines = [
            line
            for line in run.splitlines()
            if line.startswith(f"python -m coverage {report}")
        ]
        assert lines, report
        for line in lines:
            assert '--include="${engine}"' in line, line


def test_metrics_reads_the_shards_data_instead_of_running_the_suite() -> None:
    jobs = _jobs()
    job = jobs["metrics"]
    # needs: coverage-shard starts metrics after both shards pass. metrics is
    # not a required check, so being skipped when a shard fails is fine.
    assert job["needs"] == ["coverage-shard"]
    run = _run(job)
    assert "pytest" not in run, "metrics must not run the suite again"
    [download] = [
        step
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/download-artifact@")
    ]
    assert download["with"]["pattern"] == "coverage-data-*"
    assert download["with"]["merge-multiple"] is True
    # Naming each file makes a missing one fail the combine, where a glob
    # would report the shards that are there.
    combine = re.search(r"^python -m coverage combine (.*)$", run, re.MULTILINE)
    assert combine, run
    assert combine.group(1).split() == _shard_files(jobs)
    # The JSON covers every package: an --include would drop conformity and
    # audit, which collect_metrics would then report as not measured.
    json_line = re.search(r"^python -m coverage json (.*)$", run, re.MULTILINE)
    assert json_line, run
    assert json_line.group(1).split() == ["-o", "coverage-all.json"]
    assert "--coverage-json coverage-all.json" in run
    assert "--check-floors" in run
