#!/usr/bin/env python
# SPDX-License-Identifier: MIT

"""Regenerate Apothem raster assets from SVG masters.

Tooling:

    resvg  (single Rust binary, no install) — SVG -> PNG
    Pillow (pip-installable)                — PNG composition / ICO

The output set is byte-equivalent for SVG rendering (resvg follows the
same SVG 1.1 + 2 spec ImageMagick honours via librsvg/MagickWand) and
identical for the multi-resolution favicon.ico container.

Usage:
    python scripts/dev/rebuild-assets-resvg.py [--resvg /path/to/resvg.exe]
    python scripts/dev/rebuild-assets-resvg.py --check-only
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS = REPO_ROOT / "assets"
SRC = ASSETS / "src"
SITE_PUBLIC = REPO_ROOT / "site" / "public"
SITE_SRC_ASSETS = REPO_ROOT / "site" / "src" / "assets"


def find_resvg(operator_override: str | None) -> Path:
    """Resolve the ``resvg`` binary, preferring the operator's explicit choice.

    Pre-conditions: ``operator_override`` is the ``--resvg`` value, or ``None``
    to auto-detect.

    Post-conditions: an explicit override that does not resolve to a file
    raises ``SystemExit`` rather than silently falling back — an operator who
    named a binary meant that one. Auto-detection searches ``PATH`` first, then
    the conventional per-user install locations, covering both the POSIX and
    the Windows executable names.
    """
    if operator_override:
        path = Path(operator_override)
        if not path.is_file():
            raise SystemExit(f"--resvg target not found: {path}")
        return path
    on_path = shutil.which("resvg") or shutil.which("resvg.exe")
    if on_path:
        return Path(on_path)
    candidates = [
        Path.home() / ".local" / "bin" / "resvg.exe",
        Path.home() / ".local" / "bin" / "resvg",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    raise SystemExit(
        "resvg not found. Download from "
        "https://github.com/linebender/resvg/releases (resvg-win64.zip on Windows; "
        "resvg-linux-x86_64.tar.gz on Linux; resvg-macos.zip on macOS), extract, and "
        "place on PATH or pass --resvg <path>."
    )


def render_png(resvg: Path, svg: Path, png: Path, size: int) -> None:
    """Render `svg` to `png` at `size`x`size` pixels via resvg."""
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(  # noqa: S603 -- resvg path resolved from PATH or ~/.local/bin only; argv elements are internally-derived constants (no untrusted input flows through); developer-only script not shipped at runtime
        [str(resvg), "--width", str(size), "--height", str(size), str(svg), str(png)],
        check=True,
        capture_output=True,
    )


def render_banner(resvg: Path, svg: Path, png: Path, width: int, height: int) -> None:
    """Render `svg` to `png` at exact `width`x`height` (rectangular)."""
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(  # noqa: S603 -- resvg path resolved from PATH or ~/.local/bin only; argv elements are internally-derived constants (no untrusted input flows through); developer-only script not shipped at runtime
        [
            str(resvg),
            "--width",
            str(width),
            "--height",
            str(height),
            str(svg),
            str(png),
        ],
        check=True,
        capture_output=True,
    )


def build_favicon_ico(resvg: Path, out: Path) -> None:
    """Build multi-resolution favicon.ico from the favicon SVG master.

    Container holds 16x16, 32x32, 48x48 layers. Pillow's `save(format='ICO')`
    is the canonical Python path for multi-res ICO generation.
    """
    with tempfile.TemporaryDirectory(prefix="apothem-favicon-") as tmp:
        tmp_path = Path(tmp)
        layers = []
        for size in (16, 32, 48):
            layer = tmp_path / f"favicon-{size}.png"
            render_png(resvg, ASSETS / "favicon.svg", layer, size)
            with Image.open(layer) as image:
                layers.append(image.copy())
        layers[1].save(
            out,
            format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48)],
            append_images=[layers[0], layers[2]],
        )


def sync_runtime_svgs() -> None:
    """Copy editable SVG masters into their runtime asset locations."""
    for name in ("logo.svg", "logo-dark.svg", "logo-animated.svg"):
        shutil.copy2(SRC / name, ASSETS / name)


def mirror_site_public() -> None:
    """Mirror the web-served asset subset into the Next.js public directory."""
    SITE_PUBLIC.mkdir(parents=True, exist_ok=True)
    for name in (
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
    ):
        shutil.copy2(ASSETS / name, SITE_PUBLIC / name)


def mirror_site_source_assets() -> None:
    """Mirror the optimized logo sources used by the Fumadocs site hero images."""
    SITE_SRC_ASSETS.mkdir(parents=True, exist_ok=True)
    for name in ("logo.svg", "logo-dark.svg"):
        shutil.copy2(ASSETS / name, SITE_SRC_ASSETS / name)


def main() -> int:
    """Re-render the raster asset set from the SVG masters; return the exit.

    Post-conditions: ``--check-only`` verifies the toolchain is resolvable and
    returns without writing any file, so CI can assert the renderer is
    available without regenerating committed assets. Otherwise every raster is
    re-rendered from its SVG master, keeping the binary assets derivable rather
    than hand-maintained. Returns ``0`` on success.
    """
    parser = argparse.ArgumentParser(
        description="Regenerate Apothem raster set from SVG masters via resvg."
    )
    parser.add_argument(
        "--resvg", help="Path to resvg binary; auto-detected when absent."
    )
    parser.add_argument(
        "--check-only", action="store_true", help="Verify toolchain only."
    )
    args = parser.parse_args()

    resvg = find_resvg(args.resvg)
    print(f"[OK] resvg: {resvg}")

    if args.check_only:
        return 0

    # 1) Runtime SVG set
    sync_runtime_svgs()
    print("[OK] runtime SVG set")

    # 2) Favicon set
    render_png(resvg, ASSETS / "favicon.svg", ASSETS / "favicon-16x16.png", 16)
    render_png(resvg, ASSETS / "favicon.svg", ASSETS / "favicon-32x32.png", 32)
    print("[OK] favicon-16x16.png + favicon-32x32.png")

    # 3) Apple touch icons. Rendered from the dark-tile master so the mark
    # stays legible on the opaque background iOS composites home-screen and
    # pinned-tab icons over (the transparent logo master would vanish on a
    # dark wallpaper).
    for size in (120, 144, 152, 180):
        render_png(
            resvg,
            SRC / "apple-touch.svg",
            ASSETS / f"apple-touch-icon-{size}.png",
            size,
        )
    print("[OK] apple-touch-icon set (120/144/152/180)")

    # 4) Logo raster set (light). 192 + 512 are the PWA-manifest maskable
    # installability icons referenced from site/public/manifest.json.
    for size in (16, 32, 64, 128, 192, 256, 512, 1024):
        render_png(resvg, SRC / "logo.svg", ASSETS / f"logo-{size}.png", size)
    print("[OK] logo raster set (light; 16..1024)")

    # 5) Logo raster set (dark)
    for size in (16, 32, 64, 128, 256, 512, 1024):
        render_png(resvg, SRC / "logo-dark.svg", ASSETS / f"logo-dark-{size}.png", size)
    print("[OK] logo raster set (dark; 16..1024)")

    # 5b) Maskable PWA icons. Rendered from the dark full-bleed tile master with
    # the glyph held inside the maskable safe zone, so adaptive launchers can
    # crop the tile to any shape without clipping the mark. The transparent
    # logo masters serve the `purpose: "any"` slots; these serve `"maskable"`.
    for size in (192, 512):
        render_png(
            resvg, SRC / "icon-maskable.svg", ASSETS / f"logo-maskable-{size}.png", size
        )
    print("[OK] maskable PWA icon set (192/512)")

    # 6) Single primary raster
    render_png(resvg, SRC / "logo.svg", ASSETS / "logo.png", 256)
    print("[OK] logo.png (256)")

    # 7) Favicon ICO (multi-resolution container)
    build_favicon_ico(resvg, ASSETS / "favicon.ico")
    print("[OK] favicon.ico (16+32+48)")

    # 8) Social cards
    if (SRC / "og-banner.svg").is_file():
        render_banner(
            resvg, SRC / "og-banner.svg", ASSETS / "og-banner-1200x630.png", 1200, 630
        )
        print("[OK] og-banner-1200x630.png")
    if (SRC / "twitter-card.svg").is_file():
        render_banner(
            resvg, SRC / "twitter-card.svg", ASSETS / "twitter-card.png", 1200, 628
        )
        print("[OK] twitter-card.png (1200x628)")

    # 9) Site asset mirrors
    mirror_site_public()
    mirror_site_source_assets()
    print("[OK] site asset mirrors")

    print("\nRebuild complete. Run 'git diff --stat assets/' to review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
