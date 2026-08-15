# SPDX-License-Identifier: MIT

"""Fail the build when the site's version drifts from the engine's.

Why this check exists. ``site/package.json`` carries a ``version`` that the
landing footer renders to visitors, and it is maintained by hand alongside the
one in ``pyproject.toml``. Two hand-maintained copies of the same number drift
silently: nothing breaks, no test fails, and the site simply advertises a
release the project is no longer shipping. The failure is invisible precisely
because it is cosmetic.

This is the same shape as ``check_pip_pin_drift.py`` — one canonical value,
several files that must agree, and a cheap assertion that says so out loud.
``pyproject.toml`` is the source of truth; the site follows it.

Exit codes: ``0`` when the two agree, ``1`` on drift or an unreadable file.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
SITE_PACKAGE_JSON = REPO_ROOT / "site" / "package.json"

# Match the project's own version, not a dependency's. The [project] table's
# version is the first top-level `version = "..."` in the file.
_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def engine_version() -> str:
    """Return the version declared in the packaging manifest."""
    match = _VERSION_RE.search(PYPROJECT.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"check-site-version-parity: no version in {PYPROJECT}")
    return match.group(1)


def site_version() -> str:
    """Return the version the documentation site advertises."""
    payload = json.loads(SITE_PACKAGE_JSON.read_text(encoding="utf-8"))
    version = payload.get("version")
    if not isinstance(version, str):
        raise SystemExit(
            f"check-site-version-parity: no string version in {SITE_PACKAGE_JSON}"
        )
    return version


def main() -> int:
    """Compare the two declarations and report any drift.

    Post-conditions: prints the agreed version on success, or names both
    values and the file to edit on failure.
    """
    engine = engine_version()
    site = site_version()

    if engine != site:
        print(
            "check-site-version-parity: DRIFT\n"
            f"  pyproject.toml      {engine}\n"
            f"  site/package.json   {site}\n"
            "  pyproject.toml is canonical; update site/package.json to match.",
            file=sys.stderr,
        )
        return 1

    print(f"check-site-version-parity: OK ({engine})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
