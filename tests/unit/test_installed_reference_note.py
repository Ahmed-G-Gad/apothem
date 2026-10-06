# SPDX-License-Identifier: MIT

"""The Installed Reference Paths note names only directories the install wrote.

Every command an install wraps as a skill carries a note telling the model
where repository-style references such as ``rules/...`` and ``templates/...``
resolve. The note is derived from the propagation manifest, so after a fixture
install every directory it names must exist.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_layout import REFERENCE_NOTE_HEADING
from apothem.lib.propagation import load_manifest, resolve_target

#: A backticked span of the note.
_SPAN = re.compile(r"`([^`]+)`")

#: The citation forms the note explains, which are not locations themselves.
_CITATION = re.compile(r"^(?:rules|templates|schemas|hooks|conformity)/")


def _named_paths(section: str, root: Path) -> list[Path]:
    """Return every location a note section names, resolved against *root*.

    A span such as ``/home/u/.claude/rules/<path>`` names its directory; a
    citation form such as ``rules/<path>`` or ``templates/...`` names none.
    """
    paths: list[Path] = []
    for span in _SPAN.findall(section):
        if _CITATION.match(span) or "..." in span:
            continue
        shown = Path(span.removesuffix("/<path>"))
        paths.append(shown if shown.is_absolute() else root / shown)
    return paths


_COMMAND_SKILL_HARNESSES = sorted(
    name
    for name, rules in load_manifest().items()
    if any(entry.mode == "command_skills" for entry in rules.install)
)


def _install(harness: str, tmp_path: Path) -> tuple[Path, Path | None, Path | None]:
    """Install *harness* into *tmp_path*; return (root, harness_root, project_root)."""
    rules = install_driver.load_rules(harness)
    if any("${PROJECT_ROOT}" in entry.target for entry in rules.install):
        project = tmp_path / "project"
        project.mkdir()
        install_driver.run_install(harness, project_root=project)
        return project, None, project
    harness_root = tmp_path / "home" / f".{harness}"
    install_driver.run_install(harness, harness_root=harness_root)
    return harness_root, harness_root, None


def test_every_command_skill_harness_is_covered() -> None:
    assert {"claude_code", "codex", "hermes", "kimi_code", "open_claw"} <= set(
        _COMMAND_SKILL_HARNESSES
    )


@pytest.mark.parametrize("harness", _COMMAND_SKILL_HARNESSES)
def test_every_path_a_note_names_exists_after_install(
    harness: str, tmp_path: Path
) -> None:
    root, harness_root, project_root = _install(harness, tmp_path)
    rules = install_driver.load_rules(harness)
    skill_roots = {
        resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        )
        for entry in rules.install
        if entry.mode == "command_skills"
    }
    notes = [
        skill_md.read_text(encoding="utf-8")
        for skill_root in skill_roots
        for skill_md in sorted(skill_root.glob("*/SKILL.md"))
        if REFERENCE_NOTE_HEADING in skill_md.read_text(encoding="utf-8")
    ]
    assert notes, f"{harness}: no generated command skill carries the note"

    named: set[Path] = set()
    for note in notes:
        section = note.split(REFERENCE_NOTE_HEADING, 1)[1]
        paths = _named_paths(section, root)
        assert paths, f"{harness}: the note names no directory"
        named.update(paths)
    missing = sorted(str(path) for path in named if not path.is_dir())
    assert missing == []


#: A bullet of the note: ``- `rules/<path>` is `<dir>/<path>```.
_BULLET = re.compile(r"^- `([a-z]+)/<path>` is `(.+)/<path>`$", re.MULTILINE)


def _sample_citation(prefix: str) -> str:
    """Return a real corpus file under *prefix* as a repository-style citation."""
    source = install_driver.APOTHEM_SRC / prefix
    sample = next(
        path
        for path in sorted(source.rglob("*"))
        if path.is_file()
        and path.name not in {"README.md", "AGENTS.md"}
        and "__pycache__" not in path.parts
    )
    return sample.relative_to(install_driver.APOTHEM_SRC).as_posix()


@pytest.mark.parametrize("harness", _COMMAND_SKILL_HARNESSES)
def test_note_bullets_resolve_real_corpus_files(harness: str, tmp_path: Path) -> None:
    root, harness_root, project_root = _install(harness, tmp_path)
    rules = install_driver.load_rules(harness)
    skill_root = next(
        resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        )
        for entry in rules.install
        if entry.mode == "command_skills"
    )
    note = next(
        text
        for skill_md in sorted(skill_root.glob("*/SKILL.md"))
        if REFERENCE_NOTE_HEADING in (text := skill_md.read_text(encoding="utf-8"))
    )
    bullets = _BULLET.findall(note.split(REFERENCE_NOTE_HEADING, 1)[1])
    assert {prefix for prefix, _ in bullets} >= {"rules", "templates", "hooks"}
    for prefix, shown in bullets:
        base = Path(shown) if Path(shown).is_absolute() else root / shown
        citation = _sample_citation(prefix)
        resolved = base / citation.split("/", 1)[1]
        assert resolved.is_file(), (harness, citation, resolved)
