# SPDX-License-Identifier: MIT

"""Driver test for the workflow-concurrency matcher against its fixtures.

The ``pass/`` and ``fail/`` trees beside this file hold workflow files. Each
test copies one tree into a ``.github/workflows/`` folder under ``tmp_path``
and runs ``check(root)``. The pass tree must come out clean. In the fail tree
each job of ``matrix-timeouts.yml`` and ``reusable-caller.yml`` carries one
drift case, so the findings are checked job by job: an integer over the
matrix ceiling, a Windows limit over 120, an other-cell limit over 90, an
expression that is not the one accepted form, and a reusable-workflow caller
whose ``with: timeout-minutes`` breaks the same rules. ``ci.yml`` and
``release.yml`` carry the workflow-level cases (job ``None``) and one job
case each.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from apothem.conformity import workflow_concurrency_grep as wcg

_FIXTURE_DIR: Final[Path] = Path(__file__).resolve().parent

_FAIL_JOBS: Final[dict[tuple[str, str | None], str]] = {
    ("ci.yml", None): "missing-concurrency-block",
    ("ci.yml", "lint"): "missing-job-timeout",
    ("release.yml", None): "cancel-in-progress-wrong-value",
    ("release.yml", "publish"): "job-timeout-exceeds-ceiling",
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


def _write(tmp_path: Path, body: str, name: str = "ci.yml") -> Path:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / name).write_bytes(body.encode("utf-8"))
    return tmp_path


_PLAIN_JOB: Final[str] = """\
on: push
concurrency:
  group: ci
  cancel-in-progress: true
jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: {value}
    steps:
      - run: echo lint
"""

_CALLER: Final[str] = """\
on: push
concurrency:
  group: ci
  cancel-in-progress: true
jobs:
  call:
    uses: {uses}
    with:
      timeout-minutes: {value}
"""

_MATRIX_CALLEE: Final[str] = """\
on:
  workflow_call:
    inputs:
      timeout-minutes:
        type: number
jobs:
  run:
    runs-on: ${{ matrix.os }}
    timeout-minutes: ${{ inputs.timeout-minutes }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
    steps:
      - run: echo run
"""


def test_pass_fixture_passes(tmp_path: Path) -> None:
    result = wcg.check(_stage(tmp_path, "pass"))
    assert result.passed, result.to_json()
    assert result.workflow_count == 4


def test_fail_fixture_flags_each_job(tmp_path: Path) -> None:
    result = wcg.check(_stage(tmp_path, "fail"))
    assert not result.passed
    by_job: dict[tuple[str, str | None], list[str]] = {}
    for finding in result.findings:
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


def test_caller_without_with_block_passes(tmp_path: Path) -> None:
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


def test_caller_with_string_with_block_passes(tmp_path: Path) -> None:
    # A plain-string `with:` holds no timeout-minutes key to check.
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
    with: timeout-minutes
""",
    )
    assert wcg.check(root).passed


@pytest.mark.parametrize(
    ("value", "detail"),
    [
        ("0", "timeout-minutes=0 is below 1"),
        ("-5", "timeout-minutes=-5 is below 1"),
        ("\uff19\uff10", "timeout-minutes is not an integer: '\uff19\uff10'"),
    ],
)
def test_integer_timeout_below_one_or_non_ascii_is_drift(
    tmp_path: Path, value: str, detail: str
) -> None:
    result = wcg.check(_write(tmp_path, _PLAIN_JOB.format(value=value)))
    assert [(f.drift_class, f.detail) for f in result.findings] == [
        ("missing-job-timeout", detail)
    ]


def test_caller_limit_below_one_is_drift(tmp_path: Path) -> None:
    root = _write(
        tmp_path, _CALLER.format(uses="./.github/workflows/reusable.yml", value=0)
    )
    result = wcg.check(root)
    assert [(f.drift_class, f.detail) for f in result.findings] == [
        ("missing-job-timeout", "with: timeout-minutes=0 is below 1")
    ]


def test_local_matrix_callee_lifts_caller_integer_ceiling(tmp_path: Path) -> None:
    _write(tmp_path, _MATRIX_CALLEE, name="reusable.yml")
    ok = _write(
        tmp_path, _CALLER.format(uses="./.github/workflows/reusable.yml", value=90)
    )
    assert wcg.check(ok).passed, wcg.check(ok).to_json()
    over = _write(
        tmp_path, _CALLER.format(uses="./.github/workflows/reusable.yml", value=95)
    )
    details = [f.detail for f in wcg.check(over).findings]
    assert details == ["with: timeout-minutes=95 exceeds ceiling=90"]


def test_local_matrix_callee_does_not_admit_caller_conditional(
    tmp_path: Path,
) -> None:
    # `with:` is evaluated in the caller's context, where matrix.os is unset.
    _write(tmp_path, _MATRIX_CALLEE, name="reusable.yml")
    value = "${{ matrix.os == 'windows-latest' && 120 || 90 }}"
    root = _write(
        tmp_path,
        _CALLER.format(uses="./.github/workflows/reusable.yml", value=f'"{value}"'),
    )
    drift = [f.drift_class for f in wcg.check(root).findings]
    assert drift == ["missing-job-timeout"]


@pytest.mark.parametrize(
    "uses",
    [
        "./.github/workflows/missing.yml",
        "./.github/workflows/../workflows/reusable.yml",
        "./.github/workflows/sub/reusable.yml",
        "./.github/workflows/C:reusable.yml",
        "owner/repo/.github/workflows/reusable.yml@v1",
    ],
)
def test_callee_not_read_keeps_caller_ceiling(tmp_path: Path, uses: str) -> None:
    _write(tmp_path, _MATRIX_CALLEE, name="reusable.yml")
    root = _write(tmp_path, _CALLER.format(uses=uses, value=60))
    details = [f.detail for f in wcg.check(root).findings]
    assert details == ["with: timeout-minutes=60 exceeds ceiling=30"]


def test_callee_matrix_job_without_the_input_keeps_caller_ceiling(
    tmp_path: Path,
) -> None:
    callee = _MATRIX_CALLEE.replace("${{ inputs.timeout-minutes }}", "20")
    _write(tmp_path, callee, name="reusable.yml")
    root = _write(
        tmp_path, _CALLER.format(uses="./.github/workflows/reusable.yml", value=60)
    )
    details = [f.detail for f in wcg.check(root).findings]
    assert details == ["with: timeout-minutes=60 exceeds ceiling=30"]


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
        ("${{ matrix.os == 'windows-latest' && 0 || 90 }}", None),
        ("${{ matrix.os == 'windows-latest' && 120 || 0 }}", None),
        ("${{ matrix.os == 'windows-latest' && 00 || 90 }}", None),
        ("${{ matrix.os == 'windows-latest' && 120 || -90 }}", None),
        ("${{ matrix.os == 'windows-latest' && \uff11\uff12\uff10 || 90 }}", None),
        ("${{ matrix.os == 'windows-latest' && 120 || \uff19\uff10 }}", None),
        ("${{ matrix.os == 'windows-latest' && 1 || 1 }}", (1, 1)),
        ("${{ matrix.os == 'windows-latest' && 120 || 90 }} extra", None),
        ("$ {{ matrix.os == 'windows-latest' && 120 || 90 }}", None),
        ("120", None),
    ],
)
def test_parse_windows_conditional(
    value: str, expected: tuple[int, int] | None
) -> None:
    assert wcg._parse_windows_conditional(value) == expected
