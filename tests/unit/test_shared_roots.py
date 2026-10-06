# SPDX-License-Identifier: MIT

"""Shared roots: one declared owner, and harness-neutral text in shared files.

Several harnesses load the same instruction file. A project ``AGENTS.md`` is
read by Codex, Cursor, GitHub Copilot, Kiro, Devin Desktop, OpenCode, Hermes,
Antigravity, CodeBuddy and Zed as well as Kimi Code; a project ``GEMINI.md`` is
read by Antigravity, the Copilot CLI and Zed as well as Gemini CLI; and
``~/.gemini/GEMINI.md`` is the global context file of both Gemini CLI and
Antigravity. An Apothem block written there must not tell every one of those
tools that it is one particular harness.

The registry records each such path once, with the single adapter that writes
it (its owner) and the harnesses whose vendor docs load it (its readers).
"""

from __future__ import annotations

import itertools
import re
from collections import Counter
from pathlib import Path

import pytest

import apothem
from apothem.lib.harness_registry import (
    CROSS_TOOL_INSTRUCTION_FILES,
    HARNESS_REGISTRY,
    PRIVATE_INSTRUCTION_TARGETS,
    SHARED_ROOTS,
    SUPPORTED_HARNESS_IDS,
    SharedRoot,
)

_PACKAGE_ROOT = Path(apothem.__file__).resolve().parent

# Templates the adapters write into an instruction file another harness reads.
_SHARED_ANCHOR_TEMPLATES = (
    "harnesses/kimi_code/templates/AGENTS.md",
    "harnesses/gemini_cli/templates/GEMINI.md",
    "harnesses/antigravity/templates/GEMINI.md",
    "harnesses/github_copilot/templates/copilot-instructions.md",
)

_DISPLAY_NAMES = sorted(
    {entry.display_name for entry in HARNESS_REGISTRY}
    | {"Gemini", "Kimi", "Copilot", "Devin"},
    key=len,
    reverse=True,
)


@pytest.mark.parametrize("template", _SHARED_ANCHOR_TEMPLATES)
def test_shared_anchor_title_names_no_harness(template: str) -> None:
    text = (_PACKAGE_ROOT / template).read_text(encoding="utf-8")
    headings = [line for line in text.splitlines() if line.startswith("#")]
    assert headings, template
    for heading in headings:
        for name in _DISPLAY_NAMES:
            assert name.lower() not in heading.lower(), (template, heading)


@pytest.mark.parametrize("template", _SHARED_ANCHOR_TEMPLATES)
def test_shared_anchor_claims_no_single_reader(template: str) -> None:
    # The block may say which install wrote it, but never that the file is one
    # harness's own surface: other harnesses read the same file.
    text = " ".join((_PACKAGE_ROOT / template).read_text(encoding="utf-8").split())
    assert not re.search(r"(?i)this file is the [^.]*surface for", text), template
    assert not re.search(r"(?i)is read by `?[a-z-]+`? at every session", text), template


def _expand(path: str) -> list[str]:
    """Expand the registry's ``{a,b}`` brace notation into concrete paths."""
    parts = re.split(r"(\{[^}]*\})", path)
    choices = [
        part[1:-1].split(",") if part.startswith("{") else [part] for part in parts
    ]
    return ["".join(combo) for combo in itertools.product(*choices)]


def _normalized(path: str) -> str:
    return path.rstrip("/")


def _written_paths() -> dict[str, list[str]]:
    """Map each concrete registry target path to the harnesses that write it."""
    writers: dict[str, list[str]] = {}
    for entry in HARNESS_REGISTRY:
        for target in entry.target_paths:
            for concrete in _expand(target):
                writers.setdefault(_normalized(concrete), []).append(entry.public_id)
    return writers


_DECLARED = {_normalized(root.path): root for root in SHARED_ROOTS}


def test_every_shared_root_is_declared_once() -> None:
    counts = Counter(_normalized(root.path) for root in SHARED_ROOTS)
    assert [path for path, n in counts.items() if n > 1] == []


@pytest.mark.parametrize("root", SHARED_ROOTS, ids=lambda root: root.path)
def test_shared_root_owner_writes_it_and_readers_are_registered(
    root: SharedRoot,
) -> None:
    path = _normalized(root.path)
    assert root.owner in SUPPORTED_HARNESS_IDS
    assert _written_paths().get(path) == [root.owner], (path, root.owner)
    assert root.readers, path
    assert root.owner not in root.readers
    assert set(root.readers) <= set(SUPPORTED_HARNESS_IDS)
    assert list(root.readers) == sorted(root.readers)
    assert root.evidence
    assert all(url.startswith("https://") for url in root.evidence)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", root.retrieved)


def test_paths_written_by_more_than_one_harness_declare_an_owner() -> None:
    shared = {
        path: writers for path, writers in _written_paths().items() if len(writers) > 1
    }
    undeclared = sorted(set(shared) - set(_DECLARED))
    assert undeclared == [], shared


def test_cross_tool_instruction_targets_declare_an_owner() -> None:
    # A target named like an instruction file several vendors read (AGENTS.md,
    # GEMINI.md, CLAUDE.md, copilot-instructions.md) is read by another
    # harness unless it sits in a directory only its own harness reads.
    undeclared = []
    for path, writers in _written_paths().items():
        if path.rsplit("/", 1)[-1] not in CROSS_TOOL_INSTRUCTION_FILES:
            continue
        if path in PRIVATE_INSTRUCTION_TARGETS:
            continue
        root = _DECLARED.get(path)
        if root is None or root.owner not in writers:
            undeclared.append((path, writers))
    assert undeclared == []


def test_private_instruction_targets_are_real_registry_targets() -> None:
    written = _written_paths()
    for path, reason in PRIVATE_INSTRUCTION_TARGETS.items():
        assert path in written, path
        assert reason.strip()


def test_codex_owns_the_shared_agents_skills_root() -> None:
    root = _DECLARED["~/.agents/skills"]
    assert root.owner == "codex"
    assert {"cursor", "gemini-cli", "github-copilot", "opencode", "zed"} <= set(
        root.readers
    )
