# SPDX-License-Identifier: MIT

"""HARD INVARIANT: ``.apothem/plans`` is the SOLE canonical project-local tree.

The F3 cutover makes ``<project-root>/.apothem/plans`` the SOLE canonical
PROJECT-LOCAL plans location. A legacy ``<project-root>/.plans`` tree is no
longer canonical — operators upgrade it via ``apothem migrate-workspace`` — so a
project-local ``.plans`` directory is now a flagged stray. The global-plans deny
is unchanged: a plans directory at any location that is NOT the project root
stays flagged. This module pins the corners of that invariant against
``no_global_plans_grep``:

  (i)   ``<project-root>/.apothem/plans/foo.md`` is ACCEPTED (sole canonical
        project-local).
  (ii)  ``<project-root>/.plans/foo.md`` (legacy, no longer canonical) is
        FLAGGED as a stray on disk — the operator upgrades it via
        ``apothem migrate-workspace``.
  (iii) a GLOBAL ``.plans`` — a ``.plans`` directory at a location that is NOT
        the project root (analogous to a harness-config-root ``~/.claude/.plans``
        when the project root is not that root) — is STILL FLAGGED.
  (iv)  a GLOBAL ``.apothem/plans`` — an ``.apothem/plans`` directory at a
        location that is NOT the project root (analogous to ``~/.apothem/plans``
        when the project root is not the user home) — is STILL FLAGGED.

The matcher operates on a single project root, so a "global" plans location is
modeled as a plans directory that is NOT the canonical ``<root>/.apothem/plans``
— exactly the stray-suite class the matcher exists to flag. Case (i) exercises
the accept path; (ii)/(iii)/(iv) exercise the preserved-deny path. Together they
prove the cutover left ``.apothem/plans`` the sole accepted project-local tree
without weakening the global deny.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "no_global_plans_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("no_global_plans_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["no_global_plans_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)


def _commit_all(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", message, "--no-verify"], cwd=repo, check=True
    )


# --- (i) project-local .apothem/plans ACCEPTED (sole canonical) --------------


def test_case_i_project_local_apothem_plans_accepted(tmp_path: Path) -> None:
    """``<root>/.apothem/plans/foo.md`` (gitignored canonical) is ACCEPTED."""
    _git_init(tmp_path)
    (tmp_path / ".gitignore").write_text(".apothem/\n", encoding="utf-8")
    plans = tmp_path / ".apothem" / "plans"
    plans.mkdir(parents=True)
    (plans / "foo.md").write_text("# plan\n", encoding="utf-8")
    # Operator data siblings under .apothem/ must not be mistaken for plans.
    (tmp_path / ".apothem" / "memory").mkdir()
    (tmp_path / ".apothem" / "memory" / "records.json").write_text(
        "[]\n", encoding="utf-8"
    )
    _commit_all(tmp_path, "init with canonical .apothem/plans/")
    result = _MOD.check(tmp_path)
    assert result.passed is True, [f.detail for f in result.findings]
    assert result.findings == []


# --- (ii) legacy project-local .plans FLAGGED (no longer canonical) ----------


def test_case_ii_legacy_project_local_dot_plans_flagged(tmp_path: Path) -> None:
    """A legacy ``<root>/.plans`` is no longer canonical and is FLAGGED.

    Operators upgrade it via ``apothem migrate-workspace``; until then the
    untracked stray sweep flags the legacy tree.
    """
    _git_init(tmp_path)
    (tmp_path / ".gitignore").write_text(".plans/\n.apothem/\n", encoding="utf-8")
    plans = tmp_path / ".plans"
    plans.mkdir()
    (plans / "foo.md").write_text("# legacy plan\n", encoding="utf-8")
    _commit_all(tmp_path, "init with legacy .plans/")
    result = _MOD.check(tmp_path)
    assert result.passed is False, [f.detail for f in result.findings]
    flagged = {f.path for f in result.findings}
    # The legacy project-local .plans is now a flagged stray (tracked-leak via
    # git index, since the gitignore in this fixture still lists it but git
    # add -A tracked it before — either path flags it).
    assert any(".plans" in path for path in flagged)


# --- (iii) global .plans STILL FLAGGED ---------------------------------------


def test_case_iii_global_dot_plans_still_flagged(tmp_path: Path) -> None:
    """A ``.plans`` at a non-project-root location is STILL FLAGGED.

    A harness-config-root ``.plans`` (e.g. ``~/.claude/.plans``) when the
    project root is not that root is a stray plans directory — not the canonical
    ``<root>/.apothem/plans`` — and the deny must not weaken for it.
    """
    _git_init(tmp_path)
    # Canonical project-local plans is fine; the stray sits elsewhere.
    (tmp_path / ".apothem" / "plans").mkdir(parents=True)
    global_plans = tmp_path / "fake-harness-config-root" / ".plans"
    global_plans.mkdir(parents=True)
    (global_plans / "leaked.md").write_text("# global plan\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    flagged = {f.path for f in result.findings}
    assert "fake-harness-config-root/.plans/" in flagged


# --- (iv) global .apothem/plans STILL FLAGGED --------------------------------


def test_case_iv_global_apothem_plans_still_flagged(tmp_path: Path) -> None:
    """An ``.apothem/plans`` at a non-project-root location is STILL FLAGGED.

    A ``~/.apothem/plans`` when the project root is not the user home is a stray
    plans directory — not the canonical ``<root>/.apothem/plans`` — and the deny
    must not weaken for it.
    """
    _git_init(tmp_path)
    (tmp_path / ".apothem" / "plans").mkdir(parents=True)
    global_apothem_plans = tmp_path / "fake-home" / ".apothem" / "plans"
    global_apothem_plans.mkdir(parents=True)
    (global_apothem_plans / "leaked.md").write_text("# global\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    flagged = {f.path for f in result.findings}
    assert "fake-home/.apothem/plans/" in flagged


def test_global_deny_intact_with_canonical_present(tmp_path: Path) -> None:
    """Canonical accepted, legacy + globals flagged."""
    _git_init(tmp_path)
    (tmp_path / ".gitignore").write_text(".apothem/\n", encoding="utf-8")
    # (i) canonical project-local tree — must NOT be flagged.
    (tmp_path / ".apothem" / "plans").mkdir(parents=True)
    (tmp_path / ".apothem" / "plans" / "b.md").write_text("b\n", encoding="utf-8")
    # global-location strays — must STILL be flagged.
    (tmp_path / "elsewhere" / ".plans").mkdir(parents=True)
    (tmp_path / "elsewhere2" / ".apothem" / "plans").mkdir(parents=True)
    result = _MOD.check(tmp_path)
    assert result.passed is False
    flagged = {f.path for f in result.findings}
    assert "elsewhere/.plans/" in flagged
    assert "elsewhere2/.apothem/plans/" in flagged
    # The canonical tree is NOT among the findings.
    assert ".apothem/plans/" not in flagged


# --- stray-sweep helper isolation (no git) -----------------------------------


def test_sweep_helper_accepts_canonical_flags_legacy_and_strays(
    tmp_path: Path,
) -> None:
    """The sweep helper accepts only the canonical tree; flags legacy + strays."""
    (tmp_path / ".apothem" / "plans").mkdir(parents=True)
    (tmp_path / ".apothem" / "memory").mkdir()  # operator data, not a plan
    (tmp_path / ".plans").mkdir()  # legacy project-local — now a stray
    (tmp_path / "sub" / ".plans").mkdir(parents=True)
    (tmp_path / "sub2" / ".apothem" / "plans").mkdir(parents=True)
    findings = _MOD._sweep_stray_plans_dirs(tmp_path, frozenset())
    flagged = {f.path for f in findings}
    assert flagged == {".plans/", "sub/.plans/", "sub2/.apothem/plans/"}
