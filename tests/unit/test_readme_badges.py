# SPDX-License-Identifier: MIT

"""The README badge strip reports the project's real state.

Two badges were wrong for the same structural reasons. The release badge read
"unreleased" because the badges workflow ran ``git describe`` on a depth-1
checkout, where no tag is reachable. The license badge used the dynamic
``github/license`` form, which reads "repo not found" whenever GitHub does not
serve the repository's metadata, although the badge policy reserves a static
form for the license. These tests pin both fixes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _badges_steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(
        (_REPO_ROOT / ".github" / "workflows" / "badges.yml").read_text(
            encoding="utf-8"
        )
    )
    job = cast("dict[str, Any]", workflow["jobs"]["publish-badges"])
    return cast("list[dict[str, Any]]", job["steps"])


def test_release_badge_checkout_has_the_history_git_describe_needs() -> None:
    steps = _badges_steps()
    describes = any("git describe" in step.get("run", "") for step in steps)
    assert describes, "the release badge no longer uses git describe"
    checkout = next(
        step for step in steps if "actions/checkout" in step.get("uses", "")
    )
    assert checkout.get("with", {}).get("fetch-depth") == 0, (
        "git describe finds no tag on a shallow checkout; set fetch-depth: 0"
    )


def test_release_badge_describes_release_tags_only() -> None:
    run = next(
        step["run"] for step in _badges_steps() if "git describe" in step.get("run", "")
    )
    assert "--match" in run, "match vMAJOR.MINOR.PATCH so a stray tag is not shown"


def test_license_badge_uses_the_static_form() -> None:
    readme = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
    license_badges = re.findall(r'<img alt="License[^"]*" src="([^"]+)"', readme)
    assert license_badges, "README has no License badge"
    for src in license_badges:
        assert src.startswith("https://img.shields.io/badge/"), (
            f"{src}: the badge policy reserves the static form for the license"
        )
