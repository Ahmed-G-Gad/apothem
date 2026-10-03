# SPDX-License-Identifier: MIT

"""Where an install places the corpus directories Apothem bodies cite.

Apothem rules, skills, commands and helper definitions cite support files by
repository-style paths: ``rules/<name>.md``, ``templates/...``,
``schemas/...``, ``hooks/...`` and ``conformity/...``. Each harness install
copies those directories to its own locations (``~/.claude/rules/`` and
``~/.claude/.apothem/support/templates/`` for one, ``~/.config/apothem/rules/``
for another). This module derives each location from the propagation
manifest's install entries, so the text that tells the model where the files
are (the per-skill reference note) names exactly the directories the install
writes, and nothing it does not.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.lib.propagation import HarnessRules, resolve_target

#: Corpus directories whose files Apothem bodies cite by relative path, in the
#: order the announcement lists them.
CITED_CORPUS_DIRS: Final[tuple[str, ...]] = (
    "rules",
    "templates",
    "schemas",
    "hooks",
    "conformity",
)

#: Install modes that write every source file under its own relative path, so
#: a citation ``<dir>/<path>`` names a file under the installed directory.
#: Converting modes that rename files (TOML commands, skill-wrapped commands)
#: are not citation targets.
_PATH_KEEPING_MODES: Final[frozenset[str]] = frozenset(
    {"merge_tree_entries", "replace_tree", "claude_rules", "antigravity_rules"}
)

#: Heading of the per-skill note generated command skills carry.
REFERENCE_NOTE_HEADING: Final[str] = "## Installed Reference Paths"


@dataclass(frozen=True)
class CorpusLayout:
    """Where one install placed each cited corpus directory.

    ``dirs`` pairs each installed corpus directory name with its location.
    ``base`` is the project root of a project-scope install: its locations are
    shown relative to it, because the files that name them live in the project
    (and may be committed), where an absolute path would be specific to one
    machine. A user-scope install shows absolute paths (``base`` is ``None``).
    """

    dirs: tuple[tuple[str, Path], ...]
    base: Path | None = None

    def __bool__(self) -> bool:
        """Return True when the install places at least one cited directory."""
        return bool(self.dirs)

    def display(self, path: Path) -> str:
        """Return *path* as the text a note shows."""
        if self.base is not None:
            return path.relative_to(self.base).as_posix()
        return path.as_posix()

    def path_lines(self) -> list[str]:
        """Return one Markdown bullet per installed directory."""
        return [
            f"- `{name}/<path>` is `{self.display(path)}/<path>`"
            for name, path in self.dirs
        ]


def _load_rules(harness_name: str) -> HarnessRules:
    """Return *harness_name*'s manifest rules through the driver.

    Imported at call time: the driver imports this module while it initializes,
    and resolving the rules through it keeps a test's patched ``load_rules`` in
    effect.
    """
    from apothem.harnesses._shared import install_driver

    return install_driver.load_rules(harness_name)


def _normalized(path: Path) -> Path:
    """Return *path* with ``..`` segments folded, without touching the disk."""
    return Path(os.path.normpath(path))


def corpus_layout(
    rules: HarnessRules,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
) -> CorpusLayout:
    """Return where *rules* install each cited corpus directory.

    The location comes from the first install entry whose source is the corpus
    directory and whose mode keeps each file's relative path. A directory the
    harness does not install is absent from the layout.
    """
    found: dict[str, Path] = {}
    for entry in rules.install:
        name = entry.source.rstrip("/")
        if (
            name not in CITED_CORPUS_DIRS
            or name in found
            or entry.mode not in _PATH_KEEPING_MODES
        ):
            continue
        target = resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        )
        found[name] = _normalized(target)
    dirs = tuple((name, found[name]) for name in CITED_CORPUS_DIRS if name in found)
    base = _normalized(project_root) if harness_root is None and project_root else None
    return CorpusLayout(dirs=dirs, base=base)


def harness_layout(harness_name: str, root: Path) -> CorpusLayout:
    """Return *harness_name*'s corpus layout for an install into *root*.

    *root* is the harness root of a user-scope harness or the project root of
    a project-scope one (a harness whose manifest targets use
    ``${PROJECT_ROOT}``). A harness absent from the manifest has no layout.
    """
    try:
        rules = _load_rules(harness_name)
    except RuntimeError:
        return CorpusLayout(dirs=())
    if any("${PROJECT_ROOT}" in entry.target for entry in rules.install):
        return corpus_layout(rules, project_root=root)
    return corpus_layout(rules, harness_root=root)


def reference_note(layout: CorpusLayout) -> str:
    """Return the note a generated command skill carries.

    It names the installed directory of every cited corpus directory; an empty
    layout yields a note that says no support files are installed.
    """
    if not layout:
        return (
            f"\n{REFERENCE_NOTE_HEADING}\n\n"
            "This install places no Apothem support files beside this skill; a "
            "repository-style reference such as `rules/...` resolves only to a "
            "project-local file with the same relative path.\n"
        )
    relative = (
        " Paths are relative to the project root." if layout.base is not None else ""
    )
    bullets = "\n".join(layout.path_lines())
    return (
        f"\n{REFERENCE_NOTE_HEADING}\n\n"
        "When this skill is installed by Apothem, resolve a repository-style "
        "reference against the installed directory for its first segment, "
        "unless a project-local file with the same relative path exists."
        f"{relative}\n\n{bullets}\n"
    )
