# SPDX-License-Identifier: MIT

"""Assemble the committed Claude Code plugin distribution tree.

The repository is not itself a shippable plugin package. Claude Cowork caps a
plugin package at 5,000 files; this repository carries 6,153 tracked files,
because ``site/`` (the documentation site) and ``tests/`` (the behaviour-diff
golden corpus, mirrored across ten harnesses) together account for 85% of it.
Neither is plugin content. Claude Code clones a marketplace locally and applies
no file cap, so a marketplace whose plugin ``source`` is the repository root
installs there and fails in Cowork.

There is no exclusion mechanism for plugin packages — no ``.pluginignore``, no
``exclude`` manifest field — so the only remedy is to give the plugin a root
that holds plugin content and nothing else. This script materializes that root
from :mod:`apothem.lib.plugin_tree`, whose assembled layout (catalog at the
root, verbatim engine copy under ``lib/apothem``) is exactly that package.

The output is committed so a git-source marketplace can resolve
``"source": "./plugins/claude-code"`` directly from a clone. ``--check`` re-runs
the assembly into a scratch directory and diffs it against the committed tree,
so the commit can never drift from the generator.

Usage::

    python scripts/dev/assemble_plugin_tree.py            # write the tree
    python scripts/dev/assemble_plugin_tree.py --check    # fail on drift
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Vendored dependencies first, then the engine — the same order bin/apothem.mjs
# puts on PYTHONPATH. plugin_tree imports jsonschema, and the CI job that runs
# this check does so before installing the release toolchain, so resolving the
# import through site-packages would make the gate depend on whatever the runner
# happens to have. The engine ships its dependencies precisely so it can run from
# a bare checkout; use them.
for _path in (_REPO_ROOT / "src" / "apothem" / "_vendor", _REPO_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from apothem.lib.plugin_tree import assemble_plugin_tree  # noqa: E402

#: Source package the plugin tree is assembled from.
SRC_ROOT = _REPO_ROOT / "src" / "apothem"

#: Committed plugin root. Named for the harness whose plugin surface it is —
#: the sibling ``plugins/apothem/`` is Codex's ``.codex-plugin`` surface, a
#: different manifest format for a different host.
PLUGIN_ROOT = _REPO_ROOT / "plugins" / "claude-code"


def _relative_paths(root: Path) -> set[str]:
    """Return every file under ``root`` as a POSIX path relative to it."""
    return {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }


def _diff(expected: Path, actual: Path) -> list[str]:
    """Return human-readable drift lines between two assembled trees.

    Args:
        expected: Freshly assembled reference tree.
        actual: The committed tree under test.

    Returns:
        One line per drifted path, empty when the trees match byte for byte.
    """
    expected_files = _relative_paths(expected)
    actual_files = _relative_paths(actual)

    lines = [
        f"missing from commit: {rel}" for rel in sorted(expected_files - actual_files)
    ]
    lines += [
        f"not in generator:   {rel}" for rel in sorted(actual_files - expected_files)
    ]
    lines += [
        f"content differs:    {rel}"
        for rel in sorted(expected_files & actual_files)
        if not filecmp.cmp(expected / rel, actual / rel, shallow=False)
    ]
    return lines


def _check() -> int:
    """Assemble into a scratch dir and report drift against the commit."""
    if not PLUGIN_ROOT.is_dir():
        print(
            f"error: plugin tree missing at {PLUGIN_ROOT}\n"
            "       run: python scripts/dev/assemble_plugin_tree.py",
            file=sys.stderr,
        )
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        reference = Path(tmp) / "claude-code"
        assemble_plugin_tree(SRC_ROOT, reference)
        drift = _diff(reference, PLUGIN_ROOT)

    if drift:
        print(
            f"error: {PLUGIN_ROOT.relative_to(_REPO_ROOT).as_posix()} has drifted "
            f"from the generator ({len(drift)} path(s)):",
            file=sys.stderr,
        )
        for line in drift:
            print(f"  {line}", file=sys.stderr)
        print(
            "\nregenerate and commit:\n  python scripts/dev/assemble_plugin_tree.py",
            file=sys.stderr,
        )
        return 1

    print(f"plugin tree in sync: {PLUGIN_ROOT.relative_to(_REPO_ROOT).as_posix()}")
    return 0


def _write() -> int:
    """Materialize the plugin tree at :data:`PLUGIN_ROOT`."""
    # Remove first so a catalog member deleted upstream cannot survive as a
    # stale file: assemble_plugin_tree replaces the directories it owns, but a
    # path it no longer emits would otherwise persist from an earlier run.
    if PLUGIN_ROOT.exists():
        shutil.rmtree(PLUGIN_ROOT)
    assemble_plugin_tree(SRC_ROOT, PLUGIN_ROOT)

    files = _relative_paths(PLUGIN_ROOT)
    total = sum((PLUGIN_ROOT / rel).stat().st_size for rel in files)
    print(
        f"assembled {PLUGIN_ROOT.relative_to(_REPO_ROOT).as_posix()}: "
        f"{len(files)} files, {total / 1024 / 1024:.1f} MB"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Argument vector, or ``None`` to read ``sys.argv``.

    Returns:
        ``0`` on success, ``1`` when ``--check`` finds drift.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed tree matches the generator; do not write.",
    )
    args = parser.parse_args(argv)
    return _check() if args.check else _write()


if __name__ == "__main__":
    raise SystemExit(main())
