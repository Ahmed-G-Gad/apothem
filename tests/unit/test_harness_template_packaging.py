# SPDX-License-Identifier: MIT

"""Regression guard: harness templates must ship in the built wheel.

Each harness adapter that propagates a single rendered file (cursor,
gemini-cli, github-copilot, windsurf, codex, antigravity, claude-code)
reads its source from ``harnesses/<name>/templates/``. If that directory
is absent from ``[tool.setuptools.package-data]`` the template is excluded
from the wheel, and ``apothem install --harness <name>`` silently no-ops
(the install driver skips a missing source) — a defect invisible to an
editable install, where the source tree is always present.

These tests fail the moment a harness gains a templates/ directory without
a corresponding package-data entry, and the moment a write_text manifest
entry points at a source that does not exist on disk.
"""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared import install_driver

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HARNESSES_DIR = _REPO_ROOT / "src" / "apothem" / "harnesses"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _harness_packages_with_templates() -> list[str]:
    """Return harness package names that ship a templates/ directory."""
    return sorted(
        d.parent.name
        for d in _HARNESSES_DIR.glob("*/templates")
        if d.is_dir() and any(d.iterdir())
    )


def test_every_harness_template_dir_has_package_data_entry() -> None:
    """Each harness templates/ dir must be declared in package-data.

    The check is a literal-key presence test against pyproject so it runs
    without a TOML parser dependency on Python 3.10. The package-data key
    is the canonical ``apothem.harnesses.<name>`` string.
    """
    pyproject = _PYPROJECT.read_text(encoding="utf-8")
    missing = [
        name
        for name in _harness_packages_with_templates()
        if f'"apothem.harnesses.{name}"' not in pyproject
    ]
    assert not missing, (
        "harness packages ship a templates/ dir but have no "
        f"[tool.setuptools.package-data] entry (excluded from the wheel): {missing}"
    )


def test_every_write_text_manifest_source_exists() -> None:
    """Every write_text propagation source resolves to a real file."""
    manifest = install_driver.load_manifest()
    missing: list[str] = []
    for harness, rules in manifest.items():
        for entry in rules.install:
            if entry.mode == "write_text":
                source = install_driver.resolve_source(entry.source)
                if not source.is_file():
                    missing.append(f"{harness}: {entry.source}")
    assert not missing, f"write_text manifest sources do not exist on disk: {missing}"
