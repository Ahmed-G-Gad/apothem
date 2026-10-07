# SPDX-License-Identifier: MIT

"""The required-check contract has no spoofable path.

`ci.yml` runs the REAL `quality / <os> / py<ver>` matrix + `coverage`; the
`ci-docs-stub.yml` workflow echoes those same context names green for
documentation-only PRs so they can satisfy `main`'s branch protection without the full
Python matrix.

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
"""

from __future__ import annotations

from pathlib import Path

import yaml

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


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


def test_stub_reports_the_required_context_names() -> None:
    stub = _load("ci-docs-stub.yml")
    jobs = stub["jobs"]
    assert "quality" in jobs
    assert "coverage" in jobs
    # The stub's job NAME templates must match ci.yml's so the reported status
    # contexts are byte-identical to the required ones.
    ci = _load("ci.yml")
    assert jobs["quality"]["name"] == ci["jobs"]["quality"]["name"]
    assert jobs["coverage"]["name"] == ci["jobs"]["coverage"]["name"]


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
