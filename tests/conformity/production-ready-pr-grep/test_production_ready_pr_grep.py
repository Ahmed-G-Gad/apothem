# SPDX-License-Identifier: MIT

"""Behavioral pass+fail coverage for the production-ready-pr matcher.

The matcher's per-file ``check`` is a soft pass by design; the substantive
four-class shape check fires in ``_check_staged`` over the staged-diff path
list. These tests drive ``_classify`` directly (path -> class labels) and
drive ``_check_staged`` with a monkeypatched ``_staged_paths`` so the
pass case (code + tests + docs + changelog all present) and the fail case
(code-only change-set) are both deterministic and network-free.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "production_ready_pr_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "production_ready_pr_grep", _GREP_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["production_ready_pr_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def test_classify_recognizes_each_class() -> None:
    assert "code" in _MOD._classify("src/apothem/cli/main.py")
    assert "tests" in _MOD._classify("tests/unit/test_main.py")
    assert "docs" in _MOD._classify("README.md")
    assert "changelog" in _MOD._classify("CHANGELOG.md")


def test_site_content_docs_is_docs_class() -> None:
    # This repo's documentation lives under site/content/docs/; those paths must
    # count as the docs-class the four-class shape requires.
    assert "docs" in _MOD._classify("site/content/docs/reference/cli.mdx")
    # Harness product templates count as documentation surfaces too.
    assert "docs" in _MOD._classify(
        "src/apothem/harnesses/cursor/templates/apothem-rules.mdc"
    )
    # A nested README/CONTRIBUTING is a docs surface at any depth.
    assert "docs" in _MOD._classify("src/apothem/lib/README.md")


def test_root_docs_tree_is_not_docs_class() -> None:
    # no_toplevel_docs_grep hard-forbids a root docs/ tree, so the old ^docs?/
    # expectation is retired: a root docs/ path must NOT be credited as
    # docs-class (the two validators no longer contradict each other).
    assert "docs" not in _MOD._classify("docs/cli.md")


def test_code_plus_site_docs_change_set_passes(monkeypatch) -> None:
    # A code change accompanied by a site/content/docs page (plus tests and
    # CHANGELOG) satisfies the four-class shape — previously impossible because
    # the ^docs?/ pattern could never match this repo's docs tree.
    monkeypatch.setattr(
        _MOD,
        "_staged_paths",
        lambda: [
            "src/apothem/cli/main.py",
            "tests/unit/test_main.py",
            "site/content/docs/reference/cli.mdx",
            "CHANGELOG.md",
        ],
    )
    result = _MOD._check_staged()
    assert result.passed, result.to_json()
    assert result.findings == []


def test_per_file_check_is_soft_pass() -> None:
    result = _MOD.check("anything at all", Path("src/apothem/cli/main.py"))
    assert result.passed
    assert result.findings == []


def test_complete_change_set_passes(monkeypatch) -> None:
    monkeypatch.setattr(
        _MOD,
        "_staged_paths",
        lambda: [
            "src/apothem/cli/main.py",
            "tests/unit/test_main.py",
            "site/content/docs/reference/cli.mdx",
            "CHANGELOG.md",
        ],
    )
    result = _MOD._check_staged()
    assert result.passed, result.to_json()
    assert result.findings == []


def test_code_only_change_set_fails(monkeypatch) -> None:
    monkeypatch.setattr(_MOD, "_staged_paths", lambda: ["src/apothem/cli/main.py"])
    result = _MOD._check_staged()
    assert not result.passed
    issues = {f.issue for f in result.findings}
    assert "missing tests-class file" in issues
    assert "missing docs-class file" in issues
    assert "missing CHANGELOG entry" in issues


def test_non_code_only_change_set_passes(monkeypatch) -> None:
    # A docs-only change-set has no code-class file, so the four-class
    # requirement does not trigger.
    monkeypatch.setattr(_MOD, "_staged_paths", lambda: ["docs/notes.md"])
    result = _MOD._check_staged()
    assert result.passed
    assert result.findings == []
