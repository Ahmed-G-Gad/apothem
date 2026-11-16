# SPDX-License-Identifier: MIT

"""Driver test for the workflow-concurrency matcher against its fixtures.

The ``pass/`` and ``fail/`` trees beside this file hold workflow files. Each
test copies one tree into a ``.github/workflows/`` folder under ``tmp_path``
and runs ``check(root)``. The pass tree must come out clean. In the fail tree
each job of ``matrix-timeouts.yml`` and ``reusable-caller.yml`` carries one
drift case, so the findings are checked job by job: an integer over the
matrix ceiling, a Windows limit over 120, an other-cell limit over 90, an
expression that is not the one accepted form, and a reusable-workflow caller
whose ``with: timeout-minutes`` breaks the same rules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from apothem.conformity import workflow_concurrency_grep as wcg

_FIXTURE_DIR: Final[Path] = Path(__file__).resolve().parent

_FAIL_JOBS: Final[dict[tuple[str, str], str]] = {
    ("matrix-timeouts.yml", "integer-over"): "job-timeout-exceeds-ceiling",
    ("matrix-timeouts.yml", "windows-over"): "job-timeout-exceeds-ceiling",
    ("matrix-timeouts.yml", "other-over"): "job-timeout-exceeds-ceiling",
    ("matrix-timeouts.yml", "other-os"): "missing-job-timeout",
    ("matrix-timeouts.yml", "extra-term"): "missing-job-timeout",
    ("matrix-timeouts.yml", "input-expression"): "missing-job-timeout",
    ("matrix-timeouts.yml", "no-matrix-conditional"): "missing-job-timeout",
    ("reusable-caller.yml", "caller-windows-over"): "job-timeout-exceeds-ceiling",
    ("reusable-caller.yml", "caller-other-over"): "job-timeout-exceeds-ceiling",
    ("reusable-caller.yml", "caller-expression"): "missing-job-timeout",
    ("reusable-caller.yml", "caller-integer-over"): "job-timeout-exceeds-ceiling",
}


def _stage(tmp_path: Path, which: str) -> Path:
    """Copy every workflow in a fixture tree into ``.github/workflows/``."""
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    sources = sorted((_FIXTURE_DIR / which).glob("*.yml"))
    assert sources, f"no fixtures under {which}/"
    for src in sources:
        (workflows / src.name).write_bytes(src.read_bytes())
    return tmp_path


def _write(tmp_path: Path, body: str) -> Path:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_bytes(body.encode("utf-8"))
    return tmp_path


def test_pass_fixture_passes(tmp_path: Path) -> None:
    result = wcg.check(_stage(tmp_path, "pass"))
    assert result.passed, result.to_json()
    assert result.workflow_count == 4


def test_fail_fixture_flags_each_job(tmp_path: Path) -> None:
    result = wcg.check(_stage(tmp_path, "fail"))
    assert not result.passed
    by_job: dict[tuple[str, str], list[str]] = {}
    for finding in result.findings:
        if finding.job is not None:
            by_job.setdefault((finding.workflow, finding.job), []).append(
                finding.drift_class
            )
    for key, drift_class in _FAIL_JOBS.items():
        assert by_job.get(key) == [drift_class], (key, result.to_json())


def test_fail_details_name_the_ceiling_crossed(tmp_path: Path) -> None:
    result = wcg.check(_stage(tmp_path, "fail"))
    details = {f.job: f.detail for f in result.findings}
    assert "Windows limit 150 exceeds ceiling=120" in details["windows-over"]
    assert "other limit 100 exceeds ceiling=90" in details["other-over"]
    assert details["caller-windows-over"].startswith("with: timeout-minutes")
    assert "other limit 95 exceeds ceiling=90" in details["caller-other-over"]
    assert details["caller-integer-over"] == (
        "with: timeout-minutes=60 exceeds ceiling=30"
    )


def test_ci_quality_job_form_passes(tmp_path: Path) -> None:
    # The exact form ci.yml's quality job and ci-matrix.yml's caller use.
    root = _write(
        tmp_path,
        """\
on: [push, pull_request]
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  quality:
    runs-on: ${{ matrix.os }}
    timeout-minutes: ${{ matrix.os == 'windows-latest' && 120 || 90 }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
    steps:
      - run: python -m pytest
""",
    )
    result = wcg.check(root)
    assert result.passed, result.to_json()


def test_boolean_timeout_is_not_an_integer(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        """\
on: push
concurrency:
  group: ci
  cancel-in-progress: true
jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: true
    steps:
      - run: echo lint
""",
    )
    result = wcg.check(root)
    assert [f.drift_class for f in result.findings] == ["missing-job-timeout"]


def test_caller_with_non_mapping_with_block_is_skipped(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        """\
on: push
concurrency:
  group: ci
  cancel-in-progress: true
jobs:
  call:
    uses: ./.github/workflows/reusable.yml
""",
    )
    assert wcg.check(root).passed


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("${{ matrix.os == 'windows-latest' && 120 || 90 }}", (120, 90)),
        ("${{matrix.os=='windows-latest'&&120||90}}", (120, 90)),
        ("  ${{\tmatrix.os ==  'windows-latest' &&\n 60 || 30 }} ", (60, 30)),
        ('${{ matrix.os == "windows-latest" && 120 || 90 }}', None),
        ("${{ matrix.os == 'windows-2025' && 120 || 90 }}", None),
        ("${{ matrix.os != 'windows-latest' && 120 || 90 }}", None),
        ("${{ runner.os == 'windows-latest' && 120 || 90 }}", None),
        ("${{ matrix.os == 'windows-latest' && 120 }}", None),
        ("${{ matrix.os == 'windows-latest' && 12.5 || 90 }}", None),
        ("${{ matrix.os == 'windows-latest' && -1 || 90 }}", None),
        ("${{ matrix.os == 'windows-latest' && 120 || 90 }} extra", None),
        ("$ {{ matrix.os == 'windows-latest' && 120 || 90 }}", None),
        ("120", None),
    ],
)
def test_parse_windows_conditional(
    value: str, expected: tuple[int, int] | None
) -> None:
    assert wcg._parse_windows_conditional(value) == expected
