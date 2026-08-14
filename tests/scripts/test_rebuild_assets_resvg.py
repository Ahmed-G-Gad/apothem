# SPDX-License-Identifier: MIT

"""Unit tests for the raster-asset rebuild tool's resolution and mirror logic.

``scripts/dev/rebuild-assets-resvg.py`` regenerates the PNG/ICO asset set from
SVG masters via the ``resvg`` binary. The render functions are thin
subprocess/Pillow wrappers (integration-flavored), but two pieces carry real
branch logic worth covering directly: ``find_resvg`` (operator-override ->
PATH -> ``~/.local/bin`` -> hard error) and the asset mirror/sync copies (which
files land where). The module filename is hyphenated, so it is loaded via
importlib; Pillow is required at import, so the suite skips when it is absent.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MOD_PATH = _REPO_ROOT / "scripts" / "dev" / "rebuild-assets-resvg.py"

_spec = importlib.util.spec_from_file_location("rebuild_assets_resvg", _MOD_PATH)
assert _spec is not None
assert _spec.loader is not None
rar = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(rar)
    _IMPORT_OK = True
except ModuleNotFoundError:  # Pillow not installed in this environment.
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(not _IMPORT_OK, reason="Pillow (PIL) not available")


class TestFindResvg:
    """Locating the renderer binary.

    Covers the operator override being honoured when present and exiting when it
    is missing — a named binary is never silently replaced — against the
    auto-detection order: the search path first, then the local install
    locations.
    """

    def test_operator_override_present_is_returned(self, tmp_path: Path) -> None:
        binary = tmp_path / "resvg"
        binary.write_text("#!/bin/sh\n", encoding="utf-8")
        assert rar.find_resvg(str(binary)) == binary

    def test_operator_override_missing_exits(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="not found"):
            rar.find_resvg(str(tmp_path / "absent"))

    def test_resolves_from_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            rar.shutil,
            "which",
            lambda name: "/usr/bin/resvg" if name == "resvg" else None,
        )
        assert rar.find_resvg(None) == Path("/usr/bin/resvg")

    def test_falls_back_to_local_bin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(rar.shutil, "which", lambda _name: None)
        monkeypatch.setattr(rar.Path, "home", lambda: tmp_path)
        local_bin = tmp_path / ".local" / "bin"
        local_bin.mkdir(parents=True)
        (local_bin / "resvg").write_text("bin", encoding="utf-8")

        assert rar.find_resvg(None) == local_bin / "resvg"

    def test_not_found_anywhere_exits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(rar.shutil, "which", lambda _name: None)
        monkeypatch.setattr(rar.Path, "home", lambda: tmp_path)  # empty home
        with pytest.raises(SystemExit, match="resvg not found"):
            rar.find_resvg(None)


class TestSyncRuntimeSvgs:
    """Copying the SVG masters into the runtime asset tree."""

    def test_copies_each_master_into_assets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src = tmp_path / "src"
        assets = tmp_path / "assets"
        src.mkdir()
        assets.mkdir()
        for name in ("logo.svg", "logo-dark.svg", "logo-animated.svg"):
            (src / name).write_text(f"<svg>{name}</svg>", encoding="utf-8")
        monkeypatch.setattr(rar, "SRC", src)
        monkeypatch.setattr(rar, "ASSETS", assets)

        rar.sync_runtime_svgs()

        for name in ("logo.svg", "logo-dark.svg", "logo-animated.svg"):
            assert (assets / name).read_text(encoding="utf-8") == f"<svg>{name}</svg>"


class TestMirrorSiteSourceAssets:
    """Mirroring the logo pair into the site source tree.

    Covers that the destination directory is created rather than assumed.
    """

    def test_mirrors_logo_pair_creating_destination(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assets = tmp_path / "assets"
        dest = tmp_path / "site" / "src" / "assets"  # does not exist yet
        assets.mkdir()
        for name in ("logo.svg", "logo-dark.svg"):
            (assets / name).write_text(name, encoding="utf-8")
        monkeypatch.setattr(rar, "ASSETS", assets)
        monkeypatch.setattr(rar, "SITE_SRC_ASSETS", dest)

        rar.mirror_site_source_assets()

        # The destination is created on demand and both masters land.
        assert (dest / "logo.svg").is_file()
        assert (dest / "logo-dark.svg").is_file()


class TestMirrorSitePublic:
    """Mirroring the published web asset subset.

    Covers that the full subset is mirrored, so no published asset is left
    stale.
    """

    def test_mirrors_the_full_web_asset_subset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assets = tmp_path / "assets"
        public = tmp_path / "site" / "public"
        assets.mkdir()
        monkeypatch.setattr(rar, "ASSETS", assets)
        monkeypatch.setattr(rar, "SITE_PUBLIC", public)

        # Every name the mirror copies must exist in the source set.
        names = [
            "logo.svg",
            "logo-dark.svg",
            "logo-animated.svg",
            "logo-wordmark.svg",
            "logo-wordmark-dark.svg",
            "logo.png",
            "logo-192.png",
            "logo-256.png",
            "logo-512.png",
            "logo-maskable-192.png",
            "logo-maskable-512.png",
            "favicon.svg",
            "favicon.ico",
            "favicon-16x16.png",
            "favicon-32x32.png",
            "apple-touch-icon-180.png",
            "og-banner-1200x630.png",
            "twitter-card.png",
            "social-preview.svg",
        ]
        for name in names:
            (assets / name).write_bytes(b"x")

        rar.mirror_site_public()

        # All declared web assets are mirrored into the created public dir.
        assert public.is_dir()
        for name in names:
            assert (public / name).is_file()
