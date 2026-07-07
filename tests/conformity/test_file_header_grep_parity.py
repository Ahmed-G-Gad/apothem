# SPDX-License-Identifier: MIT

"""Parity test: file_header_grep's inlined helpers vs scripts/inject-header.py.

``file_header_grep.py`` deliberately inlines the header-detection helpers from
``scripts/inject-header.py`` under a byte-identical-semantics claim, because the
grep is hot-loaded via importlib and cannot import from ``scripts/`` at that
execution surface. This test pins that claim so the two implementations cannot
drift silently: for every shared variant family and a spread of representative
paths, the grep's ``_render_variant`` / ``_render_canonical_block`` /
``_replace_marker`` / ``_fnmatch_with_globstar`` / ``_variant_family_for``
produce the same result as the injector's counterparts.

The two SUFFIX_VARIANT / BASENAME_VARIANT tables are NOT required to be equal:
the injector legitimately covers a wider suffix set (e.g. ``.cff`` / ``.mdc``)
and extra basenames (``CODEOWNERS`` / ``apothem`` / ``PKGBUILD``). Parity is
asserted only over the intersection the grep actually maps, plus the algorithmic
helpers that must agree byte-for-byte.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from apothem.conformity import file_header_grep as fhg

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INJECTOR_PATH = _REPO_ROOT / "scripts" / "inject-header.py"


def _load_injector() -> ModuleType:
    """Load scripts/inject-header.py in-process (hyphenated filename)."""
    spec = importlib.util.spec_from_file_location(
        "apothem_inject_header", _INJECTOR_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["apothem_inject_header"] = module
    spec.loader.exec_module(module)
    return module


injector = _load_injector()

# The variant families the grep renders (VARIANT_EXEMPT is not renderable).
_RENDERABLE_VARIANTS = (
    fhg.VARIANT_HASH,
    fhg.VARIANT_DOUBLE_SLASH,
    fhg.VARIANT_HTML,
    fhg.VARIANT_C_BLOCK,
    fhg.VARIANT_SEMICOLON,
    fhg.VARIANT_DOUBLE_DASH,
)


def test_variant_constant_names_match() -> None:
    """The VARIANT_* string constants are identical across both modules."""
    for name in (
        "VARIANT_HASH",
        "VARIANT_DOUBLE_SLASH",
        "VARIANT_HTML",
        "VARIANT_C_BLOCK",
        "VARIANT_SEMICOLON",
        "VARIANT_DOUBLE_DASH",
        "VARIANT_EXEMPT",
    ):
        assert getattr(fhg, name) == getattr(injector, name), name


def test_author_and_spdx_marker_constants_match() -> None:
    """The detection-anchor substrings must match the injector byte-for-byte."""
    assert fhg.AUTHOR_MARK == injector.AUTHOR_MARK
    assert fhg.SPDX_PREFIX_TEXT == injector.SPDX_PREFIX_TEXT
    assert fhg.SCAN_LINE_BUDGET == injector.SCAN_LINE_BUDGET


@pytest.mark.parametrize("variant", _RENDERABLE_VARIANTS)
def test_render_variant_matches_injector(variant: str) -> None:
    """The single-line variant rendering agrees with the injector."""
    hash_form_line, spdx_text = fhg._load_banner()
    assert hash_form_line, "banner fixture must load for the parity check"
    banner = injector.CanonicalBanner(
        spdx_text=spdx_text, hash_form_line=hash_form_line
    )
    assert fhg._render_variant(hash_form_line, spdx_text, variant) == (
        injector.render_variant(banner, variant)
    )


@pytest.mark.parametrize("variant", _RENDERABLE_VARIANTS)
def test_render_canonical_block_matches_injector(variant: str) -> None:
    """The canonical block (variant line + trailing blank) agrees."""
    hash_form_line, spdx_text = fhg._load_banner()
    banner = injector.CanonicalBanner(
        spdx_text=spdx_text, hash_form_line=hash_form_line
    )
    assert fhg._render_canonical_block(hash_form_line, spdx_text, variant) == (
        injector.render_canonical_block(banner, variant)
    )


@pytest.mark.parametrize(
    ("source", "target"),
    [("#", "//"), ("#", ";"), ("#", "--")],
)
def test_replace_marker_matches_injector(source: str, target: str) -> None:
    """Marker substitution agrees on the fixture's hash-form line."""
    hash_form_line, _ = fhg._load_banner()
    assert fhg._replace_marker(hash_form_line, source, target) == (
        injector._replace_marker(hash_form_line, source, target)
    )


@pytest.mark.parametrize(
    ("path", "pattern"),
    [
        ("LICENSE", "LICENSE"),
        ("src/apothem/x.py", "src/apothem/**"),
        (".apothem/plans/draft.md", ".apothem/**"),
        ("tests/fixtures/a/b.py", "tests/fixtures/**"),
        ("a/b/c.txt", "a/*/c.txt"),
        ("a/b/c/d.txt", "a/**/d.txt"),
        ("node_modules/x/y.js", "**/node_modules/**"),
        ("plain.py", "*.md"),
        ("only.one.segment", "only.one.segment"),
    ],
)
def test_fnmatch_globstar_matches_injector(path: str, pattern: str) -> None:
    """The gitignore-style globstar matcher agrees for every probe."""
    assert fhg._fnmatch_with_globstar(path, pattern) == (
        injector._fnmatch_with_globstar(path, pattern)
    )


@pytest.mark.parametrize(
    "relative",
    [
        "src/apothem/x.py",
        "scripts/a.sh",
        "site/app.ts",
        "styles/main.css",
        "queries/q.sql",
        "config/app.ini",
        "docs/page.md",
        "Makefile",
        ".gitignore",
        "unknown.bin",
        "no_suffix_no_basename",
    ],
)
def test_variant_family_for_matches_injector_on_shared_keys(relative: str) -> None:
    """Variant resolution agrees on every key the grep's tables map.

    The injector's tables are a superset; parity is asserted only where the
    grep resolves a non-exempt family OR both resolve exempt, which is the
    behavioural contract that matters (a file the grep checks, the injector
    injects the same variant for).
    """
    grep_variant = fhg._variant_family_for(Path(relative))
    injector_variant = injector.variant_family_for(Path(relative))
    if grep_variant != fhg.VARIANT_EXEMPT:
        assert grep_variant == injector_variant, relative
