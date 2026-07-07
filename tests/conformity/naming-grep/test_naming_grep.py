# SPDX-License-Identifier: MIT

"""Self-tests for the naming-grep validator.

Each test exercises one branch of the canonical naming convention
declared in spec section 4.1. The fixtures are paths, not filesystem
artifacts; the validator operates on path strings so the tests do not
need a tmp_path scaffold."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "naming_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("naming_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["naming_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def test_canonical_uppercase_passes() -> None:
    for name in ("CLAUDE.md", "README.md", "LICENSE", "CHANGELOG.md", "MASTER-PLAN.md"):
        result = _MOD.check(name)
        assert result.passed, f"expected {name} to pass; got {result.findings}"


def test_kebab_case_file_passes() -> None:
    result = _MOD.check("src/apothem/rules/host-discovery.md")
    assert result.passed


def test_phase_prefix_dir_passes() -> None:
    result = _MOD.check("phases/06-repo-hygiene-and-validators/06D-validators")
    assert result.passed


def test_adr_pattern_passes() -> None:
    result = _MOD.check("docs/adr/0001-plans-discipline.md")
    assert result.passed


def test_uppercase_filename_fails() -> None:
    result = _MOD.check("src/apothem/rules/HostDiscovery.md")
    assert not result.passed
    assert any("HostDiscovery.md" in f.component for f in result.findings)


def test_python_module_snake_case_passes() -> None:
    # Per-family rule: a .py stem validates as snake_case (the Python-module
    # convention), so an underscore in a .py stem is NOT a violation.
    result = _MOD.check("src/apothem/conformity/naming_grep.py")
    assert result.passed, result.findings


def test_dunder_and_private_python_modules_pass() -> None:
    for name in (
        "src/apothem/__init__.py",
        "src/apothem/__main__.py",
        "src/apothem/lib/_atomic_io.py",
        "src/apothem/lib/_grep_base.pyi",
    ):
        result = _MOD.check(name)
        assert result.passed, f"{name} should pass: {result.findings}"


def test_python_package_directory_snake_case_passes() -> None:
    # A dotless directory component may be a Python package (snake_case).
    result = _MOD.check("src/apothem/harnesses/github_copilot/install.py")
    assert result.passed, result.findings


def test_uppercase_python_stem_fails() -> None:
    # Snake_case only — an UpperCamel .py stem is still a violation.
    result = _MOD.check("src/apothem/conformity/BadName.py")
    assert not result.passed
    assert any("BadName.py" in f.component for f in result.findings)


def test_underscore_in_non_python_file_fails() -> None:
    # The snake_case allowance is scoped to the Python-module family; a .md
    # file with an underscore stem is still kebab-only and fails.
    result = _MOD.check("docs/bad_name.md")
    assert not result.passed


def test_space_in_filename_fails() -> None:
    result = _MOD.check("docs/bad name.md")
    assert not result.passed


def test_hidden_directory_skipped() -> None:
    result = _MOD.check(".github/workflows/ci.yml")
    assert result.passed


def test_migration_script_prefix_passes() -> None:
    result = _MOD.check("migrations/0042_user_schema.sql")
    assert result.passed


def test_makefile_canonical_passes() -> None:
    result = _MOD.check("Makefile")
    assert result.passed


def test_standard_convention_pin_singleton_passes() -> None:
    # The SHOUTING-KEBAB adapter-package pin singleton is a canonical name.
    result = _MOD.check("src/apothem/harnesses/cursor/STANDARD-CONVENTION-PIN.md")
    assert result.passed, result.findings


def test_harness_output_singletons_pass() -> None:
    for name in ("AGENTS.md", "GEMINI.md", "QWEN.md"):
        result = _MOD.check(name)
        assert result.passed, f"{name}: {result.findings}"


def _make_tree(root: Path, rels: list[str]) -> None:
    for rel in rels:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n", encoding="utf-8")


def test_corpus_mode_walks_the_tree_not_just_the_basename(tmp_path: Path) -> None:
    # The regression this closes: corpus mode used to reduce the root to its
    # basename and validate only that one string. It must now walk the authored
    # tree and flag a nested violation.
    _make_tree(
        tmp_path,
        [
            "src/apothem/lib/atomic_io.py",  # snake .py — valid
            "src/apothem/rules/host-discovery.md",  # kebab .md — valid
            "src/apothem/rules/BadName.md",  # UpperCamel .md — violation
        ],
    )
    result = _MOD.check_corpus(tmp_path)
    assert not result.passed
    assert result.components_inspected > 0
    assert any("BadName.md" in f.component for f in result.findings)


def test_corpus_mode_accepts_python_and_kebab_families(tmp_path: Path) -> None:
    _make_tree(
        tmp_path,
        [
            "src/apothem/harnesses/github_copilot/__init__.py",
            "src/apothem/harnesses/github_copilot/install.py",
            "src/apothem/harnesses/cursor/STANDARD-CONVENTION-PIN.md",
            "src/apothem/rules/host-discovery.md",
        ],
    )
    result = _MOD.check_corpus(tmp_path)
    assert result.passed, [f.detail for f in result.findings]


def test_corpus_mode_flags_snake_case_markdown_templates(tmp_path: Path) -> None:
    # Markdown skill templates follow the kebab-case family like every other
    # authored .md artifact: the kebab-case names pass and a snake_case
    # holdout is a finding, not a tolerated note.
    _make_tree(
        tmp_path,
        [
            "src/apothem/skills/plan-suite/master-template.md",
            "src/apothem/skills/research-suite/research-template.md",
        ],
    )
    result = _MOD.check_corpus(tmp_path)
    assert result.passed, [f.detail for f in result.findings]
    assert result.notes == []

    _make_tree(tmp_path, ["src/apothem/skills/plan-suite/master_template.md"])
    result = _MOD.check_corpus(tmp_path)
    assert not result.passed
    assert any("master_template.md" in f.detail for f in result.findings)


def test_corpus_mode_skips_vendor_and_hidden_trees(tmp_path: Path) -> None:
    _make_tree(
        tmp_path,
        [
            "src/apothem/_vendor/attr/_make.py",  # vendored — out of scope
            "src/apothem/cli/.mypy_cache/CACHEDIR.TAG",  # generated — out of scope
        ],
    )
    result = _MOD.check_corpus(tmp_path)
    assert result.passed
    assert result.findings == []
