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
from fnmatch import fnmatchcase
from pathlib import Path

import pytest
import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:  # Python 3.10: tomli is in the dev lock for python_full_version < 3.11.
    import tomli as tomllib

_REPO = Path(__file__).resolve().parents[2]
_CI = _REPO / ".github" / "workflows" / "ci.yml"
# The folder both download steps put the shards' data in, apart from the
# checked-out code.
_DATA_DIR = "coverage-data"
# The jobs that write or read the shards' coverage data.
_DATA_JOBS = ("coverage-shard", "coverage", "metrics")

# A set command that turns -e off for the rest of a step: "set +e", "set +xe",
# "set -x +e" or "set +o errexit".
_ERREXIT_OFF = re.compile(r"\bset\b[^\n;&|#]*\+(?:[a-z]*e|o\s+errexit\b)")


def _jobs() -> dict:
    return yaml.safe_load(_CI.read_text(encoding="utf-8"))["jobs"]


def _run(job: dict) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


def _parts(jobs: dict) -> list[int]:
    split = re.search(
        r"--shard=\$\{\{ matrix\.shard \}\}/(\d+)\b", _run(jobs["coverage-shard"])
    )
    assert split, "coverage-shard must run pytest --shard=${{ matrix.shard }}/N"
    return list(range(1, int(split.group(1)) + 1))


def _shard_files(jobs: dict) -> list[str]:
    return [f"{_DATA_DIR}/.coverage.shard-{k}" for k in _parts(jobs)]


def _step_using(job: dict, action: str) -> dict:
    [step] = [s for s in job["steps"] if s.get("uses", "").startswith(f"{action}@")]
    return step


def _python_version(job: dict) -> str:
    return str(_step_using(job, "actions/setup-python")["with"]["python-version"])


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
    # Naming each file makes a missing one fail the combine, where a glob
    # would report the shards that are there.
    combine = re.search(r"^python -m coverage combine (.*)$", run, re.MULTILINE)
    assert combine, run
    assert combine.group(1).split() == _shard_files(jobs)
    # The JSON covers every package: an --include would drop conformity and
    # audit, which collect_metrics would then report as not measured.
    json_line = re.search(r"^python -m coverage json (.*)$", run, re.MULTILINE)
    assert json_line, run
    # --fail-under=0: without it coverage json checks pyproject's fail_under =
    # 80 against the total over every package, a figure no rule gates, and a
    # failure there would stop the step before collect_metrics runs.
    assert json_line.group(1).split() == ["--fail-under=0", "-o", "coverage-all.json"]
    assert "--coverage-json coverage-all.json" in run
    assert "--check-floors" in run


def test_each_shards_upload_is_what_both_downloads_fetch() -> None:
    # A shard artifact renamed away from the download pattern, or an upload of
    # another path, leaves the combine with no file to read.
    jobs = _jobs()
    upload = _step_using(jobs["coverage-shard"], "actions/upload-artifact")["with"]
    assert upload["include-hidden-files"] is True
    # Each cell must name its artifact and file by its own shard, or the cells
    # would overwrite one another's artifact or upload the same file.
    assert "${{ matrix.shard }}" in upload["name"]
    assert "${{ matrix.shard }}" in upload["path"]
    for name in ("coverage", "metrics"):
        download = _step_using(jobs[name], "actions/download-artifact")["with"]
        assert download["merge-multiple"] is True
        assert download["path"] == _DATA_DIR, name
        for k, combined in zip(_parts(jobs), _shard_files(jobs), strict=True):
            artifact = upload["name"].replace("${{ matrix.shard }}", str(k))
            assert fnmatchcase(artifact, download["pattern"]), (name, artifact)
            # Shard K's file is the one the combine names for shard K.
            uploaded = upload["path"].replace("${{ matrix.shard }}", str(k))
            assert f"{_DATA_DIR}/{uploaded}" == combined, (name, uploaded)


def test_the_data_jobs_share_a_runner_image_and_python() -> None:
    # The data names source files by absolute path, and coverage.py reads the
    # recorded branches against its own parse of the source. A job on another
    # image would miss the checkout path; another Python can report branches
    # that are not there.
    jobs = _jobs()
    assert len({jobs[name]["runs-on"] for name in _DATA_JOBS}) == 1
    assert len({_python_version(jobs[name]) for name in _DATA_JOBS}) == 1


def test_a_failure_in_metrics_cannot_end_green() -> None:
    # continue-on-error, a set +e, an "|| true" or a shell without -e would let
    # a missing shard file or a missed floor pass, and an if: on a step could
    # skip it. Only the upload runs with if: always(), so metrics.json and
    # coverage-all.json are kept from a failed run. metrics is not a required
    # check, but its result is still read.
    doc = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    job = doc["jobs"]["metrics"]
    assert "continue-on-error" not in job
    for defaults in (doc.get("defaults", {}), job.get("defaults", {})):
        assert defaults.get("run", {}).get("shell", "bash") == "bash", defaults
    for step in job["steps"]:
        name = step.get("name")
        run = step.get("run", "")
        assert "continue-on-error" not in step, name
        assert not _ERREXIT_OFF.search(run), name
        assert "|| true" not in run, name
        assert step.get("shell", "bash") == "bash", name
        if step.get("uses", "").startswith("actions/upload-artifact@"):
            assert step.get("if") == "always()", name
        else:
            assert "if" not in step, name
