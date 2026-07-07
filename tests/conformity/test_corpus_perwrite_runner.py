# SPDX-License-Identifier: MIT

"""The ``--all-perwrite`` corpus runner over a git-tracked fixture tree.

Why these tests exist. The corpus mode routes every git-tracked file through
every per-Write matcher in ``GREP_MODULES`` with per-suffix applicability, the
plans-tree / fixture exemptions, and the ratified blocking-vs-advisory
partition. Under ``--strict`` the run exits non-zero iff a **blocking** matcher
flags a finding; **advisory** matchers report (so drift is never silent) but
never gate.

These tests are HERMETIC: each constructs a throwaway git repository in a
``tmp_path`` (the runner enumerates the corpus via ``git ls-files``, so the
fixture must be a real work tree) and never touches the live apothem repo. The
fixtures plant one violation per representative matcher class — a blocking
``unpinned-action`` (to drive the strict FAIL), plus advisory ``bare-except``,
``magic-number``, ``hedging``, and ``file-header`` (SPDX) violations — and assert
both the aggregate strict verdict and the per-suffix scoping invariant (a
Markdown file is never bare-except-scanned; a Python file is).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from apothem.conformity import gate

# The canonical SPDX header lines the fixtures prepend so the planted fixture
# files pass the file-header matcher. Held as standalone constants (no trailing
# newline adjacent to the identifier token) so the REUSE linter parses a clean
# ``MIT`` expression rather than ``MIT\n\n``. The fixture block below is bracketed
# by REUSE-Ignore markers regardless, since these embedded header lines are test
# DATA, not this file's own license declaration (which is the line-1 header).
#
# REUSE-IgnoreStart
_SPDX_HASH = "# SPDX-License-Identifier: MIT"
_SPDX_HTML = "<!-- SPDX-License-Identifier: MIT -->"

# A GitHub Actions ``uses:`` ref pinned by 40-char commit SHA — the
# unpinned-action matcher's GREEN form. Its unpinned counterpart (``@v4``) is
# the blocking violation the FAIL fixtures plant.
_PINNED_USES = "actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1"
_UNPINNED_USES = "actions/checkout@v4"

# A workflow body that is clean for the blocking unpinned-action matcher.
_CLEAN_WORKFLOW = (
    f"{_SPDX_HASH}\n\n"
    "name: ci\non: [push]\n"
    "jobs:\n  build:\n    runs-on: ubuntu-latest\n"
    f"    steps:\n      - uses: {_PINNED_USES}\n"
)
# Same workflow with the unpinned ``@v4`` ref — trips the BLOCKING matcher.
_BLOCKING_WORKFLOW = (
    f"{_SPDX_HASH}\n\n"
    "name: ci\non: [push]\n"
    "jobs:\n  build:\n    runs-on: ubuntu-latest\n"
    f"    steps:\n      - uses: {_UNPINNED_USES}\n"
)

# Python source carrying a bare ``except:`` — trips the ADVISORY bare-except
# matcher (and is a deterministic, suffix-scoped check that must NOT fire on
# a Markdown file).
_BARE_EXCEPT_PY = (
    f"{_SPDX_HASH}\n\n"
    "def f() -> None:\n    try:\n        pass\n    except:\n        pass\n"
)
# Python source with a repeated magic number — trips the ADVISORY magic-number
# matcher (the literal 4242 appears twice; 0/1/2/-1 are exempt).
_MAGIC_NUMBER_PY = (
    f"{_SPDX_HASH}\n\n"
    "def g(x: int) -> int:\n    a = x * 4242\n    b = x + 4242\n    return a + b\n"
)
# Markdown prose carrying hedging vocabulary AND the token ``except:`` — the
# hedging matcher (ADVISORY) fires on "usually"/"typically"; the bare-except
# matcher must NOT fire on this Markdown file (per-suffix scoping).
_HEDGING_MD = (
    f"{_SPDX_HTML}\n\n"
    "# Notes\n\n"
    "This usually works and is typically fine. Prose mentioning except: inline.\n"
)
# A Python file with NO SPDX header — trips the ADVISORY file-header matcher.
_HEADERLESS_PY = 'x = "no header here"\n'

# A clean Python body used by the clean-tree fixtures.
_CLEAN_PY = f"{_SPDX_HASH}\n\ndef h(x: int) -> int:\n    return x\n"
# REUSE-IgnoreEnd


def _git(repo: Path, *args: str) -> None:
    """Run a git subcommand in *repo* (test-local; never the live tree)."""
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        encoding="utf-8",
    )


def _seed_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a throwaway git repo at *tmp_path* with *files* committed.

    The runner enumerates the corpus via ``git ls-files``, so every fixture
    file must be tracked — hence the init + add + commit. gpg signing is
    disabled so the commit never blocks on a signing key in CI.
    """
    for rel, body in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@apothem.invalid")
    _git(tmp_path, "config", "user.name", "apothem-test")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "seed corpus fixture")
    return tmp_path


def _run(repo: Path) -> dict[str, object]:
    """Invoke ``_run_all_perwrite`` over *repo*; return the parsed payload."""
    blocking_clean, payload = gate._run_all_perwrite(repo)
    parsed: dict[str, object] = json.loads(payload)
    # The boolean return and the payload ``passed`` field must agree.
    assert parsed["passed"] is blocking_clean
    return parsed


def _advisory_matchers(payload: dict[str, object]) -> set[str]:
    advisory = payload["advisory"]
    assert isinstance(advisory, list)
    return {entry["matcher"] for entry in advisory}


def _advisory_files(payload: dict[str, object], matcher: str) -> list[str]:
    advisory = payload["advisory"]
    assert isinstance(advisory, list)
    for entry in advisory:
        if entry["matcher"] == matcher:
            return list(entry["files"])
    return []


# --- Aggregate strict verdict: FAIL on a blocking finding -------------------


def test_strict_fail_on_blocking_violation(tmp_path: Path) -> None:
    """A planted unpinned-action (BLOCKING) makes the corpus run not-clean."""
    repo = _seed_repo(
        tmp_path,
        {
            "workflow.yml": _BLOCKING_WORKFLOW,
            "src/planted.py": _BARE_EXCEPT_PY,
            "src/magic.py": _MAGIC_NUMBER_PY,
            "docs/notes.md": _HEDGING_MD,
            "src/headerless.py": _HEADERLESS_PY,
        },
    )
    payload = _run(repo)
    assert payload["passed"] is False
    assert payload["blocking_findings_present"] is True
    blocking = payload["blocking"]
    assert isinstance(blocking, list)
    blocking_matchers = {entry["matcher"] for entry in blocking}
    assert "unpinned_action_grep" in blocking_matchers


def test_strict_exit_nonzero_on_blocking_violation(tmp_path: Path) -> None:
    """``main(--all-perwrite <repo> --strict)`` exits non-zero on a block."""
    repo = _seed_repo(tmp_path, {"workflow.yml": _BLOCKING_WORKFLOW})
    exit_code = gate.main(["gate", gate.ALL_PERWRITE_FLAG, str(repo), gate.STRICT_FLAG])
    assert exit_code == gate.EXIT_FAIL


# --- Representative advisory violations are reported (never silent) ----------


def test_advisory_violations_reported_not_gating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The planted bare-except / magic-number / hedging / SPDX violations
    surface in the ADVISORY set but do NOT flip the blocking verdict.

    ``file_header_grep`` (and the other anchor-scoped matchers) resolve a file
    relative to the apothem repo root OR a configured conformity scope; the
    throwaway repo is neither by default, so the test points the conformity
    scope at it via the ``APOTHEM_CONFORMITY_SCOPE`` seam — exactly how a
    per-write hook scopes a write under a hook-capable harness root.
    """
    monkeypatch.setenv("APOTHEM_CONFORMITY_SCOPE", str(tmp_path))
    repo = _seed_repo(
        tmp_path,
        {
            # No blocking violation in this tree — workflow is SHA-pinned.
            "workflow.yml": _CLEAN_WORKFLOW,
            "src/planted.py": _BARE_EXCEPT_PY,
            "src/magic.py": _MAGIC_NUMBER_PY,
            "docs/notes.md": _HEDGING_MD,
            "src/headerless.py": _HEADERLESS_PY,
        },
    )
    payload = _run(repo)
    # The blocking set is clean → the strict verdict passes.
    assert payload["passed"] is True
    assert payload["blocking"] == []
    # Yet every planted advisory violation is reported.
    advisory = _advisory_matchers(payload)
    assert "bare_except_grep" in advisory
    assert "magic_number_grep" in advisory
    assert "hedging_grep" in advisory
    assert "file_header_grep" in advisory
    assert payload["advisory_findings_present"] is True


# --- Per-suffix scoping invariant -------------------------------------------


def test_per_suffix_scoping_md_not_bare_except_scanned(tmp_path: Path) -> None:
    """A Markdown file containing ``except:`` in prose is NOT bare-except-
    scanned; the sibling Python file IS."""
    repo = _seed_repo(
        tmp_path,
        {
            "src/planted.py": _BARE_EXCEPT_PY,
            "docs/notes.md": _HEDGING_MD,  # carries "except:" in prose
        },
    )
    payload = _run(repo)
    be_files = _advisory_files(payload, "bare_except_grep")
    # The Python file is scanned and flagged...
    assert any(f.endswith("planted.py") for f in be_files)
    # ...the Markdown file is NOT (per-suffix applicability excludes it).
    assert not any(f.endswith("notes.md") for f in be_files)


def test_matcher_applies_to_honors_suffix_map() -> None:
    """Unit-level: the applicability predicate gates bare-except to Python."""
    assert gate._matcher_applies_to("bare_except_grep", Path("x.py")) is True
    assert gate._matcher_applies_to("bare_except_grep", Path("x.pyi")) is True
    assert gate._matcher_applies_to("bare_except_grep", Path("x.md")) is False
    assert gate._matcher_applies_to("unpinned_action_grep", Path("ci.yml")) is True
    assert gate._matcher_applies_to("unpinned_action_grep", Path("x.py")) is False
    # A matcher absent from the map is always applicable (self-gates inside).
    assert gate._matcher_applies_to("hedging_grep", Path("x.md")) is True


# --- Clean-tree case: PASS --------------------------------------------------


def test_clean_tree_passes_strict(tmp_path: Path) -> None:
    """A tree with no blocking violation passes the strict corpus run."""
    repo = _seed_repo(
        tmp_path,
        {
            "workflow.yml": _CLEAN_WORKFLOW,
            "src/clean.py": _CLEAN_PY,
        },
    )
    payload = _run(repo)
    assert payload["passed"] is True
    assert payload["blocking"] == []
    assert payload["blocking_findings_present"] is False
    exit_code = gate.main(["gate", gate.ALL_PERWRITE_FLAG, str(repo), gate.STRICT_FLAG])
    assert exit_code == gate.EXIT_PASS


# --- Exemptions: .apothem/plans/ and conformity fixtures not corpus-scanned -


def test_plan_suite_and_fixture_paths_exempt(tmp_path: Path) -> None:
    """A planted bare-except under the canonical ``.apothem/plans/`` tree or a
    conformity fixture tree is not corpus-scanned (the exemptions mirror the
    per-write hook)."""
    repo = _seed_repo(
        tmp_path,
        {
            ".apothem/plans/suite/draft.py": _BARE_EXCEPT_PY,
            "tests/conformity/bare-except-grep/fail.py": _BARE_EXCEPT_PY,
            "tests/fixtures/sample.py": _BARE_EXCEPT_PY,
        },
    )
    payload = _run(repo)
    # No file is corpus-scanned for bare-except → matcher absent from advisory.
    assert "bare_except_grep" not in _advisory_matchers(payload)


# --- Classification integrity -----------------------------------------------


def test_blocking_and_advisory_partition_grep_modules() -> None:
    """The blocking and advisory sets partition GREP_MODULES exactly — the
    import-time assertion is re-exercised here so the contract is a test."""
    # Should not raise.
    gate._assert_perwrite_partition()
    classified = gate._BLOCKING_PER_WRITE_GREPS | gate._ADVISORY_PER_WRITE_GREPS
    assert classified == set(gate.GREP_MODULES)
    assert not (gate._BLOCKING_PER_WRITE_GREPS & gate._ADVISORY_PER_WRITE_GREPS)


def test_advisory_set_has_rationale_for_every_member() -> None:
    """Every advisory matcher carries a (reason, owner) rationale pair so the
    classification is visible and auditable."""
    for matcher in gate._ADVISORY_PER_WRITE_GREPS:
        reason, owner = gate._ADVISORY_RATIONALE[matcher]
        assert reason.strip()
        assert owner.strip()


@pytest.mark.parametrize("matcher", sorted(gate._BLOCKING_PER_WRITE_GREPS))
def test_blocking_matchers_green_over_clean_tree(tmp_path: Path, matcher: str) -> None:
    """Each blocking matcher is GREEN over a minimal clean tree — the
    invariant that a matcher is blocking ONLY once it is green."""
    repo = _seed_repo(
        tmp_path,
        {
            "workflow.yml": _CLEAN_WORKFLOW,
            "src/clean.py": _CLEAN_PY,
        },
    )
    payload = _run(repo)
    flagged = {entry["matcher"] for entry in payload["blocking"]}  # type: ignore[union-attr]
    assert matcher not in flagged


# --- the strict split — advisory drift is load-bearing but non-gating -------


def test_advisory_findings_present_reads_payload_flag() -> None:
    """The load-bearing accessor reflects the payload's top-level flag."""
    assert gate.advisory_findings_present({"advisory_findings_present": True})
    assert not gate.advisory_findings_present({"advisory_findings_present": False})
    assert not gate.advisory_findings_present({})  # absent → False


def test_strict_exit_advisory_drift_does_not_gate() -> None:
    """PINNED CHOICE (advisory posture): under --strict, an advisory finding does
    NOT change the exit code — only a blocking failure gates. Promoting an
    advisory matcher to gating must be a deliberate classification change, not
    an accidental flip of this behavior."""
    # Blocking clean + advisory drift present + strict → still PASS.
    assert (
        gate._strict_exit_with_advisory(
            blocking_passed=True, advisory_present=True, strict=True
        )
        == gate.EXIT_PASS
    )
    # Blocking failed + strict → FAIL regardless of advisory.
    assert (
        gate._strict_exit_with_advisory(
            blocking_passed=False, advisory_present=False, strict=True
        )
        == gate.EXIT_FAIL
    )
    # Non-strict → advisory never gates and blocking findings are reported-only.
    assert (
        gate._strict_exit_with_advisory(
            blocking_passed=False, advisory_present=True, strict=False
        )
        == gate.EXIT_PASS
    )


def test_corpus_strict_passes_despite_advisory_findings(tmp_path: Path) -> None:
    """End-to-end: a tree with advisory findings (bare-except) but no blocking
    violation passes the strict corpus run — pinning the non-gating split."""
    repo = _seed_repo(
        tmp_path,
        {
            "workflow.yml": _CLEAN_WORKFLOW,
            "src/planted.py": _BARE_EXCEPT_PY,  # advisory finding
        },
    )
    payload = _run(repo)
    assert payload["advisory_findings_present"] is True
    assert payload["passed"] is True
    exit_code = gate.main(["gate", gate.ALL_PERWRITE_FLAG, str(repo), gate.STRICT_FLAG])
    assert exit_code == gate.EXIT_PASS
