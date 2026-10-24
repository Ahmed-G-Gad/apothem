# SPDX-License-Identifier: MIT

"""Generate the session-start skill index message.

The SessionStart hook injects a compact index of the shipped skills so a model
can find a skill even after Claude Code drops descriptions from its skill
listing. The index is generated from the catalog frontmatter and committed at
``src/apothem/hooks/messages/skill-index.md``; ``--check`` fails when the
committed file no longer matches the catalog, the same drift pattern as
``assemble_plugin_tree.py``.

Usage::

    python scripts/dev/generate_skill_index.py            # write the file
    python scripts/dev/generate_skill_index.py --check    # fail on drift

Run it after changing a skill or command name, its ``disable-model-invocation``
flag, or the cue map in ``src/apothem/lib/skill_index.py``, then regenerate the
plugin tree with ``scripts/dev/assemble_plugin_tree.py``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Vendored dependencies first, then the engine, as in assemble_plugin_tree.py.
for _path in (_REPO_ROOT / "src" / "apothem" / "_vendor", _REPO_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from apothem.lib.skill_index import (  # noqa: E402
    INDEX_MESSAGE_REL,
    SkillIndexError,
    build_index_message,
)

#: Source package the index is generated from.
SRC_ROOT = _REPO_ROOT / "src" / "apothem"

#: Committed message file.
INDEX_PATH = SRC_ROOT / INDEX_MESSAGE_REL


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Argument vector, or ``None`` to read ``sys.argv``.

    Returns:
        ``0`` on success, ``1`` on drift (``--check``) or a generation error.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed file matches the catalog; do not write.",
    )
    args = parser.parse_args(argv)
    try:
        expected = build_index_message(SRC_ROOT)
    except SkillIndexError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    shown = INDEX_PATH.relative_to(_REPO_ROOT).as_posix()
    if args.check:
        actual = (
            INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.is_file() else None
        )
        if actual != expected:
            print(
                f"error: {shown} has drifted from the catalog\n"
                "regenerate and commit:\n"
                "  python scripts/dev/generate_skill_index.py",
                file=sys.stderr,
            )
            return 1
        print(f"skill index in sync: {shown}")
        return 0
    INDEX_PATH.write_text(expected, encoding="utf-8", newline="\n")
    print(f"wrote {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
