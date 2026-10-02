# SPDX-License-Identifier: MIT

"""Move every version anchor in the repository to one new release version.

Why this script exists. The release version lives in more than a dozen
hand-maintained places: the Python packaging manifest, the npm, site and VS
Code package manifests, the Gemini, Qwen, Codex and Antigravity extension
manifests, the Claude Code marketplace, the citation file, the security
support table and the CHANGELOG. The parity tests catch a missed file, but
nothing performed the bump, so every release was a manual multi-file edit and
a runbook-faithful maintainer hit red CI.

What it does, in order:

1. Validates ``NEW`` as a ``MAJOR.MINOR.PATCH`` release version that is not
   lower than the current ``pyproject.toml`` version.
2. Rewrites each anchor in place. JSON files keep their exact formatting: only
   the matched ``"version"`` value changes, and the result is re-parsed to
   prove that nothing but the declared key paths moved.
3. Promotes ``## [Unreleased]`` content to a dated ``## [NEW]`` section and
   points the CHANGELOG link definitions at the new tag.
4. Adds a supported ``MAJOR.MINOR.x`` row to the SECURITY.md table when the
   bump opens a new minor.
5. Regenerates the derived trees (Claude Code plugin package, behavior-diff
   goldens, docs reference and changelog pages) unless ``--no-regen``.

Re-running with the current version is safe: it re-aligns any stragglers and
changes nothing else. Stdlib only, so it runs before any dependency install.

Usage::

    python scripts/release/bump_version.py 1.2.0
    python scripts/release/bump_version.py 1.2.0 --date 2026-11-01 --dry-run

Exit codes: ``0`` on success, ``1`` when an anchor cannot be updated, ``2``
on a usage error (malformed version or date, or a downgrade).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]

#: (repo-relative path, key path to the object holding ``version``). An empty
#: key path means the top-level object. This list must stay a superset of the
#: one in ``tests/unit/test_manifest_version_sync.py``; a test enforces it.
JSON_ANCHORS: list[tuple[str, tuple[str, ...]]] = [
    (".claude-plugin/marketplace.json", ()),
    (".claude-plugin/marketplace.json", ("metadata",)),
    ("gemini-extension.json", ()),
    ("qwen-extension.json", ()),
    ("plugins/apothem/.codex-plugin/plugin.json", ()),
    ("src/apothem/harnesses/antigravity/templates/plugin.json", ()),
    ("package.json", ()),
    ("vscode-extension/package.json", ()),
    ("site/package.json", ()),
    ("site/package-lock.json", ()),
    ("site/package-lock.json", ("packages", "")),
]

PYPROJECT = "pyproject.toml"
CITATION = "CITATION.cff"
CHANGELOG = "CHANGELOG.md"
SECURITY = "SECURITY.md"

#: Derived trees, regenerated after the anchors move. Each entry is the argv
#: tail run from the repository root; ``{python}`` is the running interpreter.
REGEN_COMMANDS: list[list[str]] = [
    ["{python}", "scripts/dev/assemble_plugin_tree.py"],
    ["{python}", "scripts/dev/regen-behavior-goldens.py"],
    ["node", "site/scripts/update-reference-inventory.mjs"],
]

_RELEASE_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_PYPROJECT_VERSION = re.compile(r'^(version\s*=\s*")([^"]+)(")', re.MULTILINE)
_JSON_VERSION = re.compile(r'("version"\s*:\s*")([^"]*)(")')


class BumpError(RuntimeError):
    """An anchor could not be rewritten as declared."""


def anchor_files() -> list[str]:
    """Return every repository-relative file the bumper may rewrite."""
    seen: dict[str, None] = {rel: None for rel, _ in JSON_ANCHORS}
    for rel in (PYPROJECT, CITATION, CHANGELOG, SECURITY):
        seen[rel] = None
    return list(seen)


def _parse(version: str) -> tuple[int, int, int]:
    match = _RELEASE_VERSION.match(version)
    if match is None:
        raise ValueError(version)
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def current_version(root: Path) -> str:
    """Return the ``[project].version`` declared in ``pyproject.toml``."""
    text = (root / PYPROJECT).read_text(encoding="utf-8")
    match = _PYPROJECT_VERSION.search(text)
    if match is None:
        raise BumpError(f'{PYPROJECT}: no top-level version = "..." line')
    return match.group(2)


def _get(data: object, keys: tuple[str, ...]) -> dict[str, Any]:
    """Return the JSON object reached by walking *keys* from *data*."""
    node = data
    for key in keys:
        node = cast("dict[str, Any]", node)[key]
    return cast("dict[str, Any]", node)


def _set_json_version(text: str, keys: tuple[str, ...], new: str, rel: str) -> str:
    """Return *text* with the ``version`` under *keys* set to *new*.

    The JSON is never re-serialized, so key order, indentation and escaping
    stay byte-identical. Each ``"version": "..."`` occurrence is tried in turn;
    the one whose replacement moves the value at *keys* is kept. Files such as
    a lockfile hold many unrelated ``version`` keys, so a plain
    replace-all would rewrite third-party entries.
    """
    data = json.loads(text)
    if _get(data, keys).get("version") == new:
        return text
    for match in _JSON_VERSION.finditer(text):
        candidate = text[: match.start(2)] + new + text[match.end(2) :]
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if _get(parsed, keys).get("version") == new:
            return candidate
    raise BumpError(
        f"{rel}: no version field found under {list(keys) or 'the top level'}"
    )


def _bump_json(root: Path, new: str) -> dict[str, tuple[str, str]]:
    """Rewrite every JSON anchor. Returns ``{rel: (before, after)}`` texts."""
    changes: dict[str, tuple[str, str]] = {}
    for rel, keys in JSON_ANCHORS:
        path = root / rel
        if not path.is_file():
            continue
        before = changes[rel][0] if rel in changes else path.read_text(encoding="utf-8")
        current = changes[rel][1] if rel in changes else before
        changes[rel] = (before, _set_json_version(current, keys, new, rel))

    # Prove each file changed only at its declared key paths.
    for rel, (before, after) in changes.items():
        original = json.loads(before)
        updated = json.loads(after)
        for anchor_rel, keys in JSON_ANCHORS:
            if anchor_rel == rel:
                _get(updated, keys)["version"] = _get(original, keys)["version"]
        if updated != original:
            raise BumpError(f"{rel}: rewrite touched more than the version fields")
    return changes


def _bump_pyproject(text: str, new: str) -> str:
    return _PYPROJECT_VERSION.sub(
        lambda m: f"{m.group(1)}{new}{m.group(3)}", text, count=1
    )


def _bump_citation(text: str, new: str, date: str) -> str:
    text, versions = re.subn(
        r'^(\s*version:\s*")[^"]*(")', rf"\g<1>{new}\g<2>", text, flags=re.MULTILINE
    )
    text, dates = re.subn(
        r'^(\s*date-released:\s*")[^"]*(")',
        rf"\g<1>{date}\g<2>",
        text,
        flags=re.MULTILINE,
    )
    if versions == 0 or dates == 0:
        raise BumpError(f"{CITATION}: expected version and date-released fields")
    return text


def _bump_changelog(text: str, new: str, old: str, date: str) -> tuple[str, list[str]]:
    """Promote Unreleased to ``## [new] - date`` and refresh the link block."""
    notes: list[str] = []
    heading = re.compile(rf"^## \[{re.escape(new)}\]", re.MULTILINE)
    unreleased = re.search(r"^## \[Unreleased\][^\n]*\n", text, re.MULTILINE)
    if unreleased is None:
        raise BumpError(f"{CHANGELOG}: no '## [Unreleased]' heading")
    if heading.search(text) is None:
        following = re.compile(r"^## \[", re.MULTILINE).search(text, unreleased.end())
        body_end = following.start() if following else len(text)
        if not text[unreleased.end() : body_end].strip():
            notes.append(
                f"{CHANGELOG}: [Unreleased] was empty; the [{new}] section has no entries"
            )
        text = (
            text[: unreleased.end()]
            + f"\n## [{new}] - {date}\n"
            + text[unreleased.end() :]
        )

    link = re.search(r"^\[Unreleased\]:\s*(\S+)\s*$", text, re.MULTILINE)
    if link is None:
        raise BumpError(f"{CHANGELOG}: no '[Unreleased]: <url>' link definition")
    base = re.sub(r"/(compare|releases)/.*$", "", link.group(1))
    replacement = f"[Unreleased]: {base}/compare/v{new}...HEAD"
    text = text[: link.start()] + replacement + text[link.end() :]
    if re.search(rf"^\[{re.escape(new)}\]:", text, re.MULTILINE) is None:
        end = link.start() + len(replacement)
        text = text[:end] + f"\n[{new}]: {base}/releases/tag/v{new}" + text[end:]
    if old != new and re.search(rf"^\[{re.escape(old)}\]:", text, re.MULTILINE) is None:
        notes.append(
            f"{CHANGELOG}: no link definition for the previous version [{old}]"
        )
    return text, notes


def _bump_security(text: str, new: str) -> tuple[str, list[str]]:
    """Add ``MAJOR.MINOR.x`` as a supported row when the minor is new."""
    major, minor, _ = _parse(new)
    series = f"{major}.{minor}.x"
    if re.search(rf"^\|\s*{re.escape(series)}\s*\|", text, re.MULTILINE):
        return text, []
    rows = list(re.finditer(r"^\|\s*\d+\.\d+\.x\s*\|[^\n]*\n", text, re.MULTILINE))
    if not rows:
        raise BumpError(f"{SECURITY}: no supported-versions table rows found")
    first = rows[0]
    cells = first.group(0).split("|")
    width_version, width_support = len(cells[1]), len(cells[2])
    row = f"|{(' ' + series).ljust(width_version)}|{' ✓'.ljust(width_support)}|\n"
    text = text[: first.start()] + row + text[first.start() :]
    return text, [
        f"{SECURITY}: added {series} as supported; review the earlier rows "
        "(which minors stay supported is an operator decision)"
    ]


def _text_step(
    root: Path, rel: str, transform: Callable[[str], str]
) -> tuple[str, tuple[str, str]] | None:
    path = root / rel
    if not path.is_file():
        return None
    before = path.read_text(encoding="utf-8")
    return rel, (before, transform(before))


def plan(
    root: Path, new: str, date: str
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """Compute every rewrite without touching the disk."""
    old = current_version(root)
    notes: list[str] = []
    changes = _bump_json(root, new)

    def changelog(text: str) -> str:
        updated, extra = _bump_changelog(text, new, old, date)
        notes.extend(extra)
        return updated

    def security(text: str) -> str:
        updated, extra = _bump_security(text, new)
        notes.extend(extra)
        return updated

    steps = (
        _text_step(root, PYPROJECT, lambda t: _bump_pyproject(t, new)),
        _text_step(root, CITATION, lambda t: _bump_citation(t, new, date)),
        _text_step(root, CHANGELOG, changelog),
        _text_step(root, SECURITY, security),
    )
    for step in steps:
        if step is not None:
            changes[step[0]] = step[1]
    return changes, notes


def _write(root: Path, changes: dict[str, tuple[str, str]]) -> list[str]:
    written: list[str] = []
    for rel, (before, after) in changes.items():
        if before == after:
            continue
        with (root / rel).open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(after)
        written.append(rel)
    return written


def _regenerate(root: Path) -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(root / "src"), env.get("PYTHONPATH", "")) if part
    )
    for template in REGEN_COMMANDS:
        argv = [sys.executable if arg == "{python}" else arg for arg in template]
        if shutil.which(argv[0]) is None and argv[0] != sys.executable:
            print(
                f"bump-version: {argv[0]} not found; run by hand: {' '.join(template)}"
            )
            continue
        print(f"bump-version: regenerating: {' '.join(template)}")
        # Fixed argv from REGEN_COMMANDS, no shell; root selects the checkout.
        completed = subprocess.run(argv, cwd=root, env=env, check=False)  # noqa: S603
        if completed.returncode != 0:
            print(
                f"bump-version: regeneration failed: {' '.join(template)}",
                file=sys.stderr,
            )
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(
        description="Move every version anchor to one new release version."
    )
    parser.add_argument(
        "version", help="New release version, MAJOR.MINOR.PATCH (no 'v')."
    )
    parser.add_argument(
        "--date",
        default=_dt.datetime.now(_dt.timezone.utc).date().isoformat(),
        help="Release date for CHANGELOG and CITATION.cff (default: today, UTC).",
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument(
        "--dry-run", action="store_true", help="List the changes; write nothing."
    )
    parser.add_argument(
        "--no-regen",
        action="store_true",
        help="Skip regenerating the plugin package, goldens and docs pages.",
    )
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()

    try:
        new = _parse(args.version)
    except ValueError:
        print(
            f"bump-version: {args.version!r} is not MAJOR.MINOR.PATCH", file=sys.stderr
        )
        return 2
    try:
        _dt.date.fromisoformat(args.date)
    except ValueError:
        print(f"bump-version: {args.date!r} is not a YYYY-MM-DD date", file=sys.stderr)
        return 2

    try:
        old = current_version(root)
        if new < _parse(old):
            print(
                f"bump-version: {args.version} is lower than the current {old}",
                file=sys.stderr,
            )
            return 2
        changes, notes = plan(root, args.version, args.date)
    except (BumpError, ValueError, KeyError, OSError) as exc:
        print(f"bump-version: {exc}", file=sys.stderr)
        return 1

    pending = sorted(rel for rel, (before, after) in changes.items() if before != after)
    verb = "would update" if args.dry_run else "updated"
    for rel in pending:
        print(f"bump-version: {verb} {rel}")
    for note in notes:
        print(f"bump-version: note: {note}")
    if args.dry_run:
        return 0

    _write(root, changes)
    print(f"bump-version: {old} -> {args.version} ({len(pending)} files)")
    if args.no_regen:
        return 0
    return _regenerate(root)


if __name__ == "__main__":
    raise SystemExit(main())
