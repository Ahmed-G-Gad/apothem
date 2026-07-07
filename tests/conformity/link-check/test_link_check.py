# SPDX-License-Identifier: MIT

"""Self-tests for the link-check validator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "link_check.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("link_check", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["link_check"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def test_internal_link_resolves(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("# target", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("See [target](target.md).", encoding="utf-8")
    result = _MOD.check(source.read_text(encoding="utf-8"), source)
    assert result.passed, result.findings
    assert result.internal_count == 1


def test_internal_link_dead_fails(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("See [missing](does-not-exist.md).", encoding="utf-8")
    result = _MOD.check(source.read_text(encoding="utf-8"), source)
    assert not result.passed
    assert any("does-not-exist.md" in f.destination for f in result.findings)


def test_external_link_skipped(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("See [home](https://example.com).", encoding="utf-8")
    result = _MOD.check(source.read_text(encoding="utf-8"), source)
    assert result.passed
    assert result.external_count == 1
    assert result.internal_count == 0


def test_anchor_only_link_passes(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("See [section](#anchor).", encoding="utf-8")
    result = _MOD.check(source.read_text(encoding="utf-8"), source)
    assert result.passed


def test_internal_link_with_fragment_resolves(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("# target\n## section", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("See [target](target.md#section).", encoding="utf-8")
    result = _MOD.check(source.read_text(encoding="utf-8"), source)
    assert result.passed


def test_mailto_link_skipped(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("Email [me](mailto:me@example.com).", encoding="utf-8")
    result = _MOD.check(source.read_text(encoding="utf-8"), source)
    assert result.passed
    assert result.external_count == 1


@pytest.mark.parametrize(
    "body",
    [
        "No links here.",
        "# heading only",
        "",
    ],
)
def test_bodies_without_links_pass(tmp_path: Path, body: str) -> None:
    source = tmp_path / "source.md"
    source.write_text(body, encoding="utf-8")
    result = _MOD.check(body, source)
    assert result.passed
    assert result.internal_count == 0
    assert result.external_count == 0


# --- Fumadocs /docs site-route resolution -----------------------------------
#
# Root-absolute ``/docs/<path>`` and ``/<locale>/docs/<path>`` links resolve
# against the on-disk page set under ``site/content/docs/``. The page root is
# discovered by walking the source file's ancestors, so the source path must
# sit inside this repo (whose ``site/content/docs`` is the resolution target).
# ``_PROBE_SOURCE`` is a synthetic in-repo path: it need not exist on disk —
# ``check()`` only uses it to locate the page root.

_FIXTURE_DIR: Final[Path] = Path(__file__).resolve().parent
_PROBE_SOURCE: Final[Path] = _FIXTURE_DIR / "__docs_route_probe__.md"


@pytest.mark.parametrize(
    "route",
    [
        "/docs/faq",  # leaf page -> site/content/docs/faq.mdx
        "/docs/glossary",  # leaf page -> site/content/docs/glossary.mdx
        "/docs/reference",  # section -> site/content/docs/reference/index.mdx
        "/docs",  # docs root -> site/content/docs/index.mdx
        "/docs/cli-reference/install",  # nested leaf page
        "/docs/glossary#a-term",  # the fragment is stripped before resolving
    ],
)
def test_live_docs_route_resolves(route: str) -> None:
    result = _MOD.check(f"See [x]({route}).", _PROBE_SOURCE)
    assert result.passed, result.findings
    assert result.internal_count == 1
    assert result.external_count == 0


@pytest.mark.parametrize(
    "route",
    [
        "/docs/this-route-does-not-exist",  # dead leaf
        "/docs/reference/no-such-page",  # dead page under a live section
    ],
)
def test_dead_docs_route_fails(route: str) -> None:
    result = _MOD.check(f"See [x]({route}).", _PROBE_SOURCE)
    assert not result.passed
    assert any(f.destination == route for f in result.findings)


def test_locale_docs_route_maps_under_locale_subtree() -> None:
    # /<locale>/docs/<path> resolves under site/content/docs/<locale>/...; a
    # dead one is flagged, and the attempted targets sit under the ar/ subtree.
    result = _MOD.check("See [x](/ar/docs/__no_such_localized_page__).", _PROBE_SOURCE)
    assert not result.passed
    assert any(
        "site/content/docs/ar/__no_such_localized_page__" in f.detail
        for f in result.findings
    )


@pytest.mark.parametrize(
    "route",
    [
        "/",  # site root, not a docs page
        "/img/logo.svg",  # asset path
        "/llms.txt",  # well-known file
        "/xx/docs/faq",  # unknown locale prefix -> not a docs route
    ],
)
def test_non_docs_root_absolute_out_of_scope(route: str) -> None:
    result = _MOD.check(f"See [x]({route}).", _PROBE_SOURCE)
    assert result.passed
    assert result.external_count == 1
    assert result.internal_count == 0


def test_docs_route_outside_site_repo_out_of_scope(tmp_path: Path) -> None:
    # No site/content/docs ancestor above a tmp source: /docs routes are not
    # checkable there, so they stay out of scope (no finding), as before.
    source = tmp_path / "note.md"
    source.write_text("See [x](/docs/this-route-does-not-exist).", encoding="utf-8")
    result = _MOD.check(source.read_text(encoding="utf-8"), source)
    assert result.passed
    assert result.external_count == 1
    assert result.internal_count == 0


def test_live_docs_routes_fixture_passes() -> None:
    fixture = _FIXTURE_DIR / "pass-live-docs-routes.md"
    result = _MOD.check(fixture.read_text(encoding="utf-8"), fixture)
    assert result.passed, result.findings
    assert result.internal_count >= 3


def test_dead_docs_route_fixture_fails() -> None:
    fixture = _FIXTURE_DIR / "fail-dead-docs-route.md"
    result = _MOD.check(fixture.read_text(encoding="utf-8"), fixture)
    assert not result.passed
    assert any("does-not-exist" in f.destination for f in result.findings)


# --- C5: LINK_RE hardening (angle-bracket dests, single-quoted/paren titles)


def test_angle_bracket_destination_resolves(tmp_path: Path) -> None:
    (tmp_path / "target.md").write_text("# t", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("See [x](<target.md>).", encoding="utf-8")
    result = _MOD.check(source.read_text(encoding="utf-8"), source)
    assert result.passed, result.findings
    assert result.internal_count == 1


def test_angle_bracket_external_with_paren_is_counted(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("See [x](<https://example.com/a(b)>).", encoding="utf-8")
    result = _MOD.check(source.read_text(encoding="utf-8"), source)
    assert result.passed
    assert result.external_count == 1


@pytest.mark.parametrize(
    "link",
    [
        '[x](target.md "a title")',
        "[x](target.md 'a title')",
        "[x](target.md (a title))",
    ],
)
def test_titles_do_not_break_resolution(tmp_path: Path, link: str) -> None:
    (tmp_path / "target.md").write_text("# t", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text(f"See {link}.", encoding="utf-8")
    result = _MOD.check(source.read_text(encoding="utf-8"), source)
    assert result.passed, result.findings
    assert result.internal_count == 1


def test_dead_link_with_single_quoted_title_is_flagged(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("See [x](nope.md 'title').", encoding="utf-8")
    result = _MOD.check(source.read_text(encoding="utf-8"), source)
    assert not result.passed
    assert any("nope.md" in f.destination for f in result.findings)


def test_payload_keys_are_snake_case(tmp_path: Path) -> None:
    import json

    source = tmp_path / "source.md"
    source.write_text("See [x](https://example.com).", encoding="utf-8")
    payload = json.loads(
        _MOD.check(source.read_text(encoding="utf-8"), source).to_json()
    )
    assert "internal_count" in payload
    assert "external_count" in payload
    assert "internal-count" not in payload
    assert "external-count" not in payload
