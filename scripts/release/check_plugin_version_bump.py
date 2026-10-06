# SPDX-License-Identifier: MIT

"""Fail when the Claude Code plugin changed since the last release tag but its
manifest version did not.

Why this check exists. When a plugin manifest pins ``version``, Claude Code
keeps every user on the cached copy until that string changes; ``claude
plugin update`` reports "already at the latest version". After v1.1.0 the
marketplace source moved from the repository root to ``plugins/claude-code``
and the hooks paths changed, all under the same 1.1.0, so users who
installed before the move never received later fixes, and "1.1.0" named two
different packages.

The check resolves each plugin through ``.claude-plugin/marketplace.json`` at
HEAD (working tree) and at the base release tag, then fails when the plugin's
source directory moved or its contents differ while the manifest version is
unchanged. The base is the newest ``vMAJOR.MINOR.PATCH`` tag reachable from
HEAD that does not point at HEAD itself, so on a tag push the new tag is
compared with the previous release. With no such tag the check skips and says
so.

Usage::

    python scripts/release/check_plugin_version_bump.py
    python scripts/release/check_plugin_version_bump.py --base-ref v1.1.0
    python scripts/release/check_plugin_version_bump.py --advisory   # warn, exit 0

Exit codes: ``0`` pass or skip, ``1`` a plugin changed without a version
change, ``2`` git or manifest error.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKETPLACE = ".claude-plugin/marketplace.json"
_RELEASE_TAG = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class CheckError(RuntimeError):
    """git or a manifest could not be read."""


@dataclass(frozen=True)
class Plugin:
    """One marketplace entry resolved at one ref."""

    name: str
    source: str
    version: str | None


def _git(
    root: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git")
    if git is None:
        raise CheckError("git is not on PATH")
    completed = subprocess.run(  # noqa: S603 - fixed git argv, no shell
        [git, *args], cwd=root, capture_output=True, text=True, check=False
    )
    if check and completed.returncode != 0:
        raise CheckError(f"git {' '.join(args)}: {completed.stderr.strip()}")
    return completed


def _normalize(source: str) -> str:
    """Return a marketplace ``source`` as a repo-relative pathspec."""
    path = source.strip()
    while path.startswith("./"):
        path = path[2:]
    path = path.rstrip("/")
    return path or "."


def base_tag(root: Path) -> str | None:
    """Return the newest release tag reachable from HEAD, excluding HEAD's own."""
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    tags = _git(root, "tag", "--merged", "HEAD", "--list", "v*").stdout.split()
    best: tuple[tuple[int, int, int], str] | None = None
    for tag in tags:
        match = _RELEASE_TAG.match(tag)
        if match is None:
            continue
        commit = _git(root, "rev-parse", f"{tag}^{{commit}}").stdout.strip()
        if commit == head:
            continue
        key = (int(match[1]), int(match[2]), int(match[3]))
        if best is None or key > best[0]:
            best = (key, tag)
    return best[1] if best else None


def _read(root: Path, ref: str | None, rel: str) -> str | None:
    """Return *rel* at *ref* (``None`` = working tree), or ``None`` if absent."""
    if ref is None:
        path = root / rel
        return path.read_text(encoding="utf-8") if path.is_file() else None
    shown = _git(root, "show", f"{ref}:{rel}", check=False)
    return shown.stdout if shown.returncode == 0 else None


def plugins_at(root: Path, ref: str | None) -> dict[str, Plugin]:
    """Resolve every marketplace plugin at *ref* (``None`` = working tree)."""
    raw = _read(root, ref, MARKETPLACE)
    if raw is None:
        return {}
    try:
        entries = json.loads(raw).get("plugins", [])
    except json.JSONDecodeError as exc:
        raise CheckError(f"{MARKETPLACE} at {ref or 'HEAD'}: {exc}") from exc
    resolved: dict[str, Plugin] = {}
    for entry in entries:
        source = entry.get("source")
        if not isinstance(source, str):
            continue  # a remote source (github, url) is not in this repository
        path = _normalize(source)
        manifest_rel = (
            ".claude-plugin/plugin.json"
            if path == "."
            else f"{path}/.claude-plugin/plugin.json"
        )
        manifest = _read(root, ref, manifest_rel)
        version = None
        if manifest is not None:
            value = json.loads(manifest).get("version")
            version = value if isinstance(value, str) else None
        resolved[entry["name"]] = Plugin(entry["name"], path, version)
    return resolved


def _content_differs(root: Path, base: str, path: str) -> bool:
    """True when *path* in the working tree differs from *path* at *base*."""
    diff = _git(root, "diff", "--quiet", base, "--", path, check=False)
    if diff.returncode not in (0, 1):
        raise CheckError(f"git diff {base} -- {path}: {diff.stderr.strip()}")
    return diff.returncode == 1


def find_problems(root: Path, base: str) -> list[str]:
    """Return one message per plugin that changed without a version change."""
    before = plugins_at(root, base)
    problems: list[str] = []
    for name, now in plugins_at(root, None).items():
        then = before.get(name)
        if then is None:
            print(
                f"check-plugin-version-bump: {name}: new since {base}; nothing to compare"
            )
            continue
        if now.version is None:
            # No pinned version: Claude Code versions the plugin by commit SHA.
            continue
        moved = now.source != then.source
        if not moved and not _content_differs(root, base, now.source):
            continue
        if now.version != then.version:
            continue
        what = (
            f"source moved from {then.source} to {now.source}"
            if moved
            else f"{now.source} differs from {base}"
        )
        problems.append(
            f"{name}: {what}, but its manifest version is still {now.version}. "
            "Installed copies will not update until the version changes; run "
            "scripts/release/bump_version.py with the next version."
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-ref",
        help="Compare with this ref instead of the newest earlier release tag.",
    )
    parser.add_argument(
        "--advisory",
        action="store_true",
        help=(
            "Report findings as GitHub warning annotations and exit 0. Pull "
            "requests between releases use this; the release build does not."
        ),
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root: Path = args.root

    try:
        base = args.base_ref or base_tag(root)
        if base is None:
            print(
                "check-plugin-version-bump: skipped — no vMAJOR.MINOR.PATCH tag "
                "is reachable from HEAD (a shallow clone fetches none; use "
                "fetch-depth: 0)"
            )
            return 0
        problems = find_problems(root, base)
    except (CheckError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"check-plugin-version-bump: error: {exc}", file=sys.stderr)
        return 2

    if problems:
        print(f"check-plugin-version-bump: {len(problems)} finding(s) against {base}")
        for problem in problems:
            print(f"  {problem}")
        if args.advisory:
            for problem in problems:
                print(
                    f"::warning title=Plugin version not bumped since {base}::"
                    f"{problem} Run scripts/release/bump_version.py before tagging."
                )
            return 0
        return 1
    print(f"check-plugin-version-bump: OK against {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
