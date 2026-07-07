# SPDX-License-Identifier: MIT

"""Self-tests for static-version-grep badge classification.

Covers the dynamic-ref false-positive guard (a build-status badge pinned to a
release branch via ``?branch=v1.2.3`` is not a static-version literal), the
``?tag=`` variant, and a registry version badge (no static version literal) — alongside the
still-flagged static ``/badge/`` generator form.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType
from typing import Final

_MOD: Final[ModuleType] = importlib.import_module(
    "apothem.conformity.static_version_grep"
)


def test_dynamic_branch_status_badge_is_not_flagged(tmp_path: Path) -> None:
    body = (
        "# Project\n\n"
        "![ci](https://img.shields.io/github/actions/workflow/status/"
        "ahmed-g-gad/apothem/ci.yml?branch=v1.2.3)\n"
    )
    (tmp_path / "README.md").write_text(body, encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed, [str(f) for f in result.findings]


def test_tag_param_version_is_not_flagged(tmp_path: Path) -> None:
    body = (
        "# Project\n\n"
        "![cov](https://img.shields.io/codecov/c/github/"
        "ahmed-g-gad/apothem?tag=v2.0.0)\n"
    )
    (tmp_path / "README.md").write_text(body, encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed, [str(f) for f in result.findings]


def test_registry_version_badge_is_not_flagged(tmp_path: Path) -> None:
    body = "# Project\n\n![npm](https://img.shields.io/npm/v/@ahmed-g-gad/apothem)\n"
    (tmp_path / "README.md").write_text(body, encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed, [str(f) for f in result.findings]


def test_static_badge_with_literal_version_is_flagged(tmp_path: Path) -> None:
    # Regression guard: the static `/badge/` generator embeds the displayed
    # version in the URL path; stripping ref params must not let it pass.
    body = "# Project\n\n![release](https://img.shields.io/badge/release-1.2.3-green)\n"
    (tmp_path / "README.md").write_text(body, encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert not result.passed
    assert any(f.site_class == "readme-badge" for f in result.findings)
