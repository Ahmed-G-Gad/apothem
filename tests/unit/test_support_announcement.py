# SPDX-License-Identifier: MIT

"""Each install announces where the support files its bodies cite were placed.

Apothem rules, skills, commands and helper definitions cite support files by
repository-style paths (``rules/<name>.md``, ``templates/...``,
``schemas/...``, ``hooks/...``). An install copies those directories to
harness-specific places, so the instruction file each install writes carries
one "Apothem support files" section mapping every installed directory to its
location. These tests install every adapter into an isolated home, read the
section back, and resolve the citations found in the installed bodies against
it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import apothem
from apothem.harnesses._shared.install_driver_layout import (
    ANNOUNCEMENT_HEADING,
    harness_layout,
)
from apothem.lib.harness_registry import (
    HARNESS_REGISTRY,
    HarnessRegistryEntry,
    load_adapter_class,
)

_SRC = Path(apothem.__file__).resolve().parent

#: The citation prefixes the resolution target covers.
_MEASURED = ("rules", "templates", "schemas", "hooks")

#: Required share of citations that resolve against the announced directories.
_TARGET_RATE = 0.99

#: A repository-style citation of a file: ``rules/naming.md``. The lookbehind
#: skips paths that are part of a longer path (``src/apothem/rules/x.md``,
#: ``~/.claude/rules/x.md``) or of a template token.
_CITATION = re.compile(
    r"(?<![\w./~${}-])((?:rules|templates|schemas|hooks|conformity)/"
    r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.[A-Za-z0-9]+)"
)

#: A bullet of the announcement: ``- `rules/<path>` is `<dir>/<path>```.
_BULLET = re.compile(r"^- `([a-z]+)/<path>` is `(.+)/<path>`$", re.MULTILINE)

#: Model-facing files an install writes (rules, skills, commands, agents).
_BODY_SUFFIXES = frozenset({".md", ".mdc", ".toml"})


def _has_layout(entry: HarnessRegistryEntry) -> bool:
    return bool(harness_layout(entry.package_key, Path("/root")))


_WITH_LAYOUT = [entry for entry in HARNESS_REGISTRY if _has_layout(entry)]
_WITHOUT_LAYOUT = [entry for entry in HARNESS_REGISTRY if not _has_layout(entry)]


def _install(
    entry: HarnessRegistryEntry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """Install *entry* into an isolated home; return (home, project)."""
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    adapter = load_adapter_class(entry)()
    if getattr(adapter, "requires_project", False):
        adapter.install({}, project=project)  # type: ignore[attr-defined]
    else:
        adapter.install({})  # type: ignore[attr-defined]
    return home, project


def _bodies(tmp_path: Path) -> list[Path]:
    """Return the model-facing files the install wrote under *tmp_path*."""
    return [
        path
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
        and path.suffix in _BODY_SUFFIXES
        and "state" not in path.relative_to(tmp_path).parts
    ]


def _announcement(bodies: list[Path]) -> tuple[Path, str]:
    """Return the single anchor that carries the announcement, and the section."""
    anchors = [
        path for path in bodies if ANNOUNCEMENT_HEADING in path.read_text("utf-8")
    ]
    assert len(anchors) == 1, [str(path) for path in anchors]
    text = anchors[0].read_text(encoding="utf-8")
    assert text.count(ANNOUNCEMENT_HEADING) == 1
    return anchors[0], text.split(ANNOUNCEMENT_HEADING, 1)[1]


def _announced_dirs(section: str, project: Path) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for prefix, shown in _BULLET.findall(section):
        path = Path(shown)
        mapping[prefix] = path if path.is_absolute() else project / path
    return mapping


def _citations(bodies: list[Path], anchor: Path) -> list[str]:
    found: list[str] = []
    for body in bodies:
        if body == anchor:
            continue
        for match in _CITATION.finditer(body.read_text(encoding="utf-8")):
            found.append(match.group(1).rstrip("."))
    return found


@pytest.mark.parametrize("entry", _WITH_LAYOUT, ids=lambda entry: entry.public_id)
def test_install_announces_only_installed_directories(
    entry: HarnessRegistryEntry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home, project = _install(entry, tmp_path, monkeypatch)
    _anchor, section = _announcement(_bodies(tmp_path))

    mapping = _announced_dirs(section, project)
    assert {"rules", "templates", "hooks"} <= set(mapping)
    missing = {
        prefix: str(path) for prefix, path in mapping.items() if not path.is_dir()
    }
    assert missing == {}
    # The prose is harness-neutral: some anchors are loaded by several tools.
    prose = re.sub(r"`[^`]*`", "", section)
    for other in HARNESS_REGISTRY:
        assert other.display_name not in prose, other.display_name


@pytest.mark.parametrize("entry", _WITH_LAYOUT, ids=lambda entry: entry.public_id)
def test_citations_resolve_against_the_announced_directories(
    entry: HarnessRegistryEntry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home, project = _install(entry, tmp_path, monkeypatch)
    bodies = _bodies(tmp_path)
    anchor, section = _announcement(bodies)
    mapping = _announced_dirs(section, project)

    measured = [
        citation
        for citation in _citations(bodies, anchor)
        if citation.split("/", 1)[0] in _MEASURED
        # An illustrative example (``rules/A.md``) names no corpus file.
        and (_SRC / citation).is_file()
    ]
    unresolved = [
        citation
        for citation in measured
        if not (
            (base := mapping.get(citation.split("/", 1)[0])) is not None
            and (base / citation.split("/", 1)[1]).is_file()
        )
    ]
    assert measured, entry.public_id
    rate = 1 - len(unresolved) / len(measured)
    assert rate >= _TARGET_RATE, (
        f"{entry.public_id}: {len(measured) - len(unresolved)}/{len(measured)} "
        f"citations resolve; unresolved: {sorted(set(unresolved))}"
    )


@pytest.mark.parametrize("entry", _WITHOUT_LAYOUT, ids=lambda entry: entry.public_id)
def test_install_without_support_files_claims_none(
    entry: HarnessRegistryEntry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(entry, tmp_path, monkeypatch)
    # The instruction files; GLM's provider TOML is operator configuration.
    for body in (path for path in _bodies(tmp_path) if path.suffix != ".toml"):
        text = body.read_text(encoding="utf-8")
        assert ANNOUNCEMENT_HEADING not in text, body
        assert "source repository" not in text, body
        assert "src/apothem/" not in text, body
