# SPDX-License-Identifier: MIT

"""The required-check contract has no spoofable path.

`ci.yml` runs the REAL `quality / <os> / py<ver>` matrix + `coverage`; the
`ci-docs-stub.yml` workflow echoes those same context names green for
documentation-only PRs so they can satisfy `main`'s branch protection without the full
Python matrix. In `ci.yml` each Windows Python version runs as two shard cells
of the `quality` job, and the `quality-windows` job reports the required
`quality / windows-latest / py<ver>` contexts; two tests pin that the shards
cover the whole suite and that those contexts fail unless every cell passed.

Two mechanisms keep the stub honest, and these tests pin both:

1. The two path sets are EXACT complements (`ci.yml` trigger `paths` ==
   stub `paths-ignore`) and the stub's context names match `ci.yml`'s, so a
   docs-only PR always satisfies the required contexts and a gated surface is
   never simply ignored.
2. `paths` and `paths-ignore` are both ANY-match triggers, so a MIXED docs+code
   PR satisfies both filters and can start the stub alongside the real job on
   the same context names. Each stub job is therefore SELF-GATING: it runs
   `.github/workflows/scripts/assert-docs-only.sh`, which fails when any gated
   surface is in the PR diff, so the stub can never report a required check
   green over a real code or config change.

`ci.yml`'s `coverage` job combines what the `coverage-shard` cells measured,
each on its part of `pytest --shard=K/N`. Three more tests pin that the cells
cover every part and cannot read as passed when they fail, that the job combines
every part's data file by name and enforces the coverage floor with nothing that
lets a failure pass, and that the job runs, and fails, when a shard did not
pass: GitHub would skip it otherwise, and a skipped required check counts as
passed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"

# A set command that turns -e off for the rest of a step: "set +e", "set +xe",
# "set -x +e" or "set +o errexit".
_ERREXIT_OFF = re.compile(r"\bset\b[^\n;&|#]*\+(?:[a-z]*e|o\s+errexit\b)")


def _on(doc: dict) -> dict:
    # YAML 1.1 parses the bare ``on:`` key as the boolean ``True``.
    triggers = doc.get("on", doc.get(True))
    assert isinstance(triggers, dict), "workflow must declare triggers"
    return triggers


def _load(name: str) -> dict:
    return yaml.safe_load((_WORKFLOWS / name).read_text(encoding="utf-8"))


def test_ci_and_docs_stub_pull_request_paths_are_exact_complements() -> None:
    ci_paths = set(_on(_load("ci.yml"))["pull_request"]["paths"])
    stub_ignore = set(_on(_load("ci-docs-stub.yml"))["pull_request"]["paths-ignore"])
    assert ci_paths == stub_ignore, (
        "ci.yml trigger paths and ci-docs-stub paths-ignore must be identical "
        "sets (exact complement), so every PR runs exactly one of the two and no "
        f"gated surface falls through to a fabricated green. "
        f"only-in-ci={sorted(ci_paths - stub_ignore)}; "
        f"only-in-stub={sorted(stub_ignore - ci_paths)}"
    )


def test_gated_surfaces_run_the_real_matrix_not_the_stub() -> None:
    ci_paths = set(_on(_load("ci.yml"))["pull_request"]["paths"])
    # The surfaces EN-6 closed: a change to any of these must run ci.yml's REAL
    # quality+coverage, never only the stub echo.
    for surface in ("scripts/**", ".github/workflows/**", ".pre-commit-config.yaml"):
        assert surface in ci_paths, (
            f"{surface} must be in ci.yml's trigger paths so it runs the real "
            "quality+coverage jobs (not the stub)"
        )


#: The suffix ci.yml's quality job adds to the name of a Windows shard cell.
#: A Linux cell has shard 0, which the expression reads as false: no suffix.
_SHARD_SUFFIX = "${{ matrix.shard && format(' / shard {0} of 2', matrix.shard) || '' }}"


def _cells(matrix: dict) -> list[dict]:
    """Return the cells of a workflow matrix: the product, less exclude, plus include.

    It models only the two include shapes these workflows use, and fails on
    any other: an entry that sets a matrix key to a value that key's list
    lacks (a new Python version) adds a cell of its own, and an entry that
    sets no matrix key and no key an earlier entry set is merged into every
    cell. GitHub's full rule, under which an entry merges into the cells it
    would not overwrite, is not modelled, so a new include shape must extend
    this function before the tests can trust its context names.
    """
    keys = [key for key in matrix if key not in ("include", "exclude")]
    cells: list[dict] = [{}]
    for key in keys:
        cells = [{**cell, key: value} for cell in cells for value in matrix[key]]
    for rule in matrix.get("exclude", []):
        cells = [c for c in cells if any(c.get(k) != v for k, v in rule.items())]
    for extra in matrix.get("include", []):
        if any(k in keys and v not in matrix[k] for k, v in extra.items()):
            cells.append(dict(extra))
            continue
        assert not any(k in keys for k in extra), (
            f"unsupported include {extra!r}: it sets a matrix key to a value "
            "the matrix already has, which _cells does not model"
        )
        assert not any(k in cell for cell in cells for k in extra), (
            f"unsupported include {extra!r}: it sets a key a cell already has"
        )
        for cell in cells:
            cell.update(extra)
    return cells


def test_cells_refuses_an_include_shape_it_does_not_model() -> None:
    matrix = {"os": ["a", "b"], "python-version": ["1"]}
    assert _cells({**matrix, "include": [{"python-version": "2", "x": 1}]})[-1] == {
        "python-version": "2",
        "x": 1,
    }
    assert all(c["x"] == 1 for c in _cells({**matrix, "include": [{"x": 1}]}))
    with pytest.raises(AssertionError, match="unsupported include"):
        _cells({**matrix, "include": [{"os": "a", "x": 1}]})
    with pytest.raises(AssertionError, match="unsupported include"):
        _cells({**matrix, "include": [{"x": 1}, {"x": 2}]})


def _context(template: str, cell: dict) -> str:
    """Return the check name a job *template* reports for one matrix *cell*."""
    shard = cell.get("shard")
    name = template.replace(_SHARD_SUFFIX, f" / shard {shard} of 2" if shard else "")
    for key, value in cell.items():
        name = name.replace(f"${{{{ matrix.{key} }}}}", str(value))
    assert "${{" not in name, name
    return name


def _required_ci_contexts(ci: dict) -> set[str]:
    """Return the quality contexts ci.yml reports, the advisory cell left out."""
    quality = ci["jobs"]["quality"]
    windows = ci["jobs"]["quality-windows"]
    return {
        _context(quality["name"], cell)
        for cell in _cells(quality["strategy"]["matrix"])
        if not cell.get("prerelease")
    } | {
        _context(windows["name"], cell)
        for cell in _cells(windows["strategy"]["matrix"])
    }


def test_stub_reports_the_required_context_names() -> None:
    stub = _load("ci-docs-stub.yml")
    jobs = stub["jobs"]
    assert "quality" in jobs
    assert "coverage" in jobs
    # The stub must report exactly the quality contexts ci.yml reports, each
    # Windows one from quality-windows, so a docs-only pull request satisfies
    # the same required names a code change does.
    ci = _load("ci.yml")
    stub_contexts = {
        _context(jobs["quality"]["name"], cell)
        for cell in _cells(jobs["quality"]["strategy"]["matrix"])
    }
    assert len(stub_contexts) == 10
    assert _required_ci_contexts(ci) == {
        *stub_contexts,
        *(
            f"quality / windows-latest / py{version} / shard {k} of 2"
            for version in ("3.10", "3.11", "3.12", "3.13", "3.14")
            for k in (1, 2)
        ),
    }
    assert jobs["coverage"]["name"] == ci["jobs"]["coverage"]["name"]


def test_each_windows_version_runs_every_shard_and_linux_runs_whole() -> None:
    # The Windows cells split the suite with --shard=K/2. A shard value
    # missing for one Python version would leave part of the suite unrun on
    # it; a Linux cell with a shard would run only part of the suite.
    quality = _load("ci.yml")["jobs"]["quality"]
    [pytest] = [s for s in quality["steps"] if s.get("name") == "Pytest"]
    assert pytest["run"] == (
        "python -m pytest --color=yes "
        "${{ matrix.shard && format('--shard={0}/2', matrix.shard) || '' }}"
    )
    assert "if" not in pytest
    assert quality["name"].endswith(_SHARD_SUFFIX)
    cells = _cells(quality["strategy"]["matrix"])
    for version in ("3.10", "3.11", "3.12", "3.13", "3.14"):
        shards = sorted(
            c["shard"]
            for c in cells
            if c["os"] == "windows-latest" and c["python-version"] == version
        )
        assert shards == [1, 2], version
        linux = [
            c.get("shard")
            for c in cells
            if c["os"] == "ubuntu-latest" and c["python-version"] == version
        ]
        assert linux == [0], version
    # Only the advisory pre-release cell may fail without failing the job.
    assert quality["continue-on-error"] == "${{ matrix.prerelease || false }}"
    assert [c for c in cells if c.get("prerelease")] == [
        {"os": "ubuntu-latest", "python-version": "3.15", "prerelease": True}
    ]
    for step in quality["steps"]:
        assert "continue-on-error" not in step, step.get("name")


def test_the_windows_contexts_fail_unless_every_quality_cell_passed() -> None:
    # As with coverage: GitHub skips a job whose needed job failed or was
    # cancelled, and a skipped required check counts as passed. So the job
    # that reports the required Windows contexts runs always() and fails
    # itself, right after the harden-runner step, unless the quality cells'
    # result is success.
    job = _load("ci.yml")["jobs"]["quality-windows"]
    assert job["name"] == "quality / windows-latest / py${{ matrix.python-version }}"
    assert job["needs"] == ["quality"]
    assert job["if"] == "always()"
    assert "continue-on-error" not in job
    check = job["steps"][1]
    assert "if" not in check
    assert "continue-on-error" not in check
    assert check.get("shell", "bash") == "bash"
    assert check["env"]["QUALITY_RESULT"] == "${{ needs.quality.result }}"
    assert '[ "${QUALITY_RESULT}" != "success" ]' in check["run"]
    assert "exit 1" in check["run"]
    assert not _ERREXIT_OFF.search(check["run"])


def _shard_parts(ci: dict) -> list[int]:
    """Return 1 to N, with N read from the coverage-shard job's --shard=K/N."""
    job = ci["jobs"]["coverage-shard"]
    run = "\n".join(step.get("run", "") for step in job["steps"])
    split = re.search(r"--shard=\$\{\{ matrix\.shard \}\}/(\d+)\b", run)
    assert split, "coverage-shard must run pytest --shard=${{ matrix.shard }}/N"
    return list(range(1, int(split.group(1)) + 1))


def test_the_coverage_shards_cover_every_part_of_the_suite() -> None:
    # Each cell passes its matrix value as K of --shard=K/N. A value of 1 to N
    # missing from the matrix would leave that part's tests unmeasured.
    ci = _load("ci.yml")
    job = ci["jobs"]["coverage-shard"]
    parts = _shard_parts(ci)
    assert job["strategy"]["matrix"]["shard"] == parts
    name = re.fullmatch(
        r"coverage shard \$\{\{ matrix\.shard \}\} of (\d+)", job["name"]
    )
    assert name, job["name"]
    assert int(name.group(1)) == len(parts), "the job name gives another N"
    # continue-on-error would make a failed shard read as success to the
    # coverage job, which would then check the floor without that shard's data.
    assert "continue-on-error" not in job
    for step in job["steps"]:
        assert "continue-on-error" not in step, step.get("name")


def test_the_coverage_check_combines_every_shard_and_enforces_the_floor() -> None:
    # Naming each data file makes a missing one fail the combine; a glob would
    # combine the files that are there, and half the suite can still clear the
    # floor. coverage report takes fail_under = 80 from pyproject, and a
    # --fail-under or an "|| true" would lower or skip that floor.
    # continue-on-error on the job or a step, or a set +e or set +o errexit in a
    # step, would let a missing data file or a floor failure end this required
    # check green. So would a shell without -e, such as "bash {0}": the xml and
    # html commands after a failed report succeed and the step ends green. With
    # no shell, or "bash", GitHub runs the script with -e. An if: on the step
    # would skip it.
    ci = _load("ci.yml")
    parts = _shard_parts(ci)
    job = ci["jobs"]["coverage"]
    steps = job["steps"]
    [step] = [s for s in steps if "coverage combine" in s.get("run", "")]
    assert "if" not in step
    run = step["run"]
    combine = re.search(r"python -m coverage combine (.*)", run)
    assert combine, run
    assert combine.group(1).split() == [
        f"coverage-data/.coverage.shard-{k}" for k in parts
    ]
    # The shards measure all of src/apothem; the report keeps the engine
    # files (tests/scripts/test_metrics_reuses_shard_coverage.py pins the
    # list) and nothing else on the line.
    assert re.search(
        r'^python -m coverage report --include="\$\{engine\}"$', run, re.MULTILINE
    ), run
    assert "--fail-under" not in run
    assert "|| true" not in run
    assert "continue-on-error" not in job
    for each in steps:
        assert "continue-on-error" not in each, each.get("name")
        assert not _ERREXIT_OFF.search(each.get("run", "")), each.get("name")
        assert each.get("shell", "bash") == "bash", each.get("name")
    for defaults in (ci.get("defaults", {}), job.get("defaults", {})):
        assert defaults.get("run", {}).get("shell", "bash") == "bash", defaults


def test_the_coverage_check_fails_unless_every_shard_passed() -> None:
    # GitHub skips a job when a job it needs failed or was cancelled, and a
    # skipped required check counts as passed. The required job runs always()
    # and fails itself, right after the harden-runner step, unless the shards'
    # result is success.
    job = _load("ci.yml")["jobs"]["coverage"]
    assert job["needs"] == ["coverage-shard"]
    assert job["if"] == "always()"
    check = job["steps"][1]
    # An if: on this step would skip the check of the shards' result.
    assert "if" not in check
    assert check["env"]["SHARD_RESULT"] == "${{ needs.coverage-shard.result }}"
    assert '[ "${SHARD_RESULT}" != "success" ]' in check["run"]
    assert "exit 1" in check["run"]


def test_stub_quality_matrix_mirrors_ci_for_context_parity() -> None:
    ci_matrix = _load("ci.yml")["jobs"]["quality"]["strategy"]["matrix"]
    stub_matrix = _load("ci-docs-stub.yml")["jobs"]["quality"]["strategy"]["matrix"]
    # Same os x python-version product -> same set of `quality / <os> / py<ver>`
    # required contexts; if ci.yml's matrix grows, the stub must grow with it.
    assert ci_matrix["os"] == stub_matrix["os"]
    assert ci_matrix["python-version"] == stub_matrix["python-version"]


def test_stub_jobs_are_self_gating_against_mixed_prs() -> None:
    # `paths` and `paths-ignore` are both ANY-match triggers, so a mixed
    # docs+code PR can start the stub alongside ci.yml's real job. Each stub job
    # must run the self-gating guard so it fails rather than fabricating a green
    # over a gated surface.
    stub = _load("ci-docs-stub.yml")
    for job_name in ("quality", "coverage"):
        steps = stub["jobs"][job_name]["steps"]
        guard = [s for s in steps if "assert-docs-only.sh" in s.get("run", "")]
        assert guard, (
            f"ci-docs-stub {job_name} job must run assert-docs-only.sh so a "
            "mixed docs+code PR cannot report the required context green"
        )


def test_self_gating_guard_script_exists() -> None:
    script = _WORKFLOWS / "scripts" / "assert-docs-only.sh"
    assert script.is_file(), (
        "the docs-stub self-gating guard script must exist at "
        ".github/workflows/scripts/assert-docs-only.sh"
    )


def _guard_globs() -> set[str]:
    """Return the guard script's gated surfaces as ci.yml-style path globs."""
    text = (_WORKFLOWS / "scripts" / "assert-docs-only.sh").read_text(encoding="utf-8")
    prefixes = text.split('_GATED_PREFIXES="', 1)[1].split('"', 1)[0].split()
    exact = text.split('_GATED_EXACT="', 1)[1].split('"', 1)[0].split()
    return {f"{prefix}**" for prefix in prefixes} | set(exact)


def test_guard_script_gates_exactly_the_ci_trigger_paths() -> None:
    # The stub's self-gating guard decides "docs-only" from its own prefix
    # list. If ci.yml gains a gated surface the guard does not know, a PR that
    # touches only that surface runs the stub and the guard waves it through.
    ci_paths = set(_on(_load("ci.yml"))["pull_request"]["paths"])
    assert _guard_globs() == ci_paths


def test_eval_suite_changes_run_the_real_ci() -> None:
    # evals/ is validated by tests/unit/test_eval_suite.py (schema, coverage
    # contract, rule-text sync); an evals-only change must run it.
    triggers = _on(_load("ci.yml"))
    assert "evals/**" in triggers["push"]["paths"]
    assert "evals/**" in triggers["pull_request"]["paths"]
