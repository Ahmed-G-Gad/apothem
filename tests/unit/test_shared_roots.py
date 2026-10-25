# SPDX-License-Identifier: MIT

"""Shared roots: one declared owner, and harness-neutral text in shared files.

Several harnesses load the same instruction file. A project ``AGENTS.md`` is
read by Codex, Cursor, GitHub Copilot, Kiro, Devin Desktop, OpenCode, Hermes,
Antigravity, CodeBuddy and Zed as well as Kimi Code; a project ``GEMINI.md`` is
read by Antigravity, the Copilot CLI and Zed as well as Gemini CLI; and
``~/.gemini/GEMINI.md`` is the global context file of both Gemini CLI and
Antigravity. An Apothem block written there must not tell every one of those
tools that it is one particular harness.

The registry records each such path once, with the adapter it belongs to (its
owner), the other adapters that write the same bytes to it (its co-installers),
and the harnesses whose vendor docs only load it (its readers). A user-level
folder several installs write is counted through the install ledger.
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
                path = _normalized(concrete)
                writers.setdefault(path, []).append(entry.public_id)
                # A glob target such as ``~/.codex/agents/*.toml`` writes into
                # its parent folder, which is the path another tool loads.
                parent, _, name = path.rpartition("/")
                if "*" in name:
                    writers.setdefault(parent, []).append(entry.public_id)
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
    # The owner and the co-installers are exactly the adapters that write it.
    assert sorted(_written_paths().get(path, [])) == sorted(
        [root.owner, *root.co_installers]
    ), (path, root.owner)
    assert root.owner not in root.co_installers
    assert set(root.co_installers) <= set(SUPPORTED_HARNESS_IDS)
    assert list(root.co_installers) == sorted(root.co_installers)
    assert root.kind in {"load", "support"}
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", root.retrieved)
    if root.kind == "support":
        # A folder only Apothem's own files cite: nothing else loads it.
        assert root.co_installers, path
        assert not root.readers, path
        assert not root.evidence, path
        return
    assert root.readers, path
    assert root.owner not in root.readers
    assert set(root.readers) <= set(SUPPORTED_HARNESS_IDS)
    assert set(root.readers).isdisjoint(root.co_installers)
    assert list(root.readers) == sorted(root.readers)
    assert set(root.reader_conditions) <= set(root.readers)
    assert all(condition.strip() for condition in root.reader_conditions.values())
    assert root.evidence
    assert all(url.startswith("https://") for url in root.evidence)


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
    # Cursor, GitHub Copilot, Windsurf and Zed write the same copy Codex does;
    # the ledger decides which install removes it. The rest only load it.
    assert root.co_installers == ("cursor", "github-copilot", "windsurf", "zed")
    assert {
        "gemini-cli",
        "kimi-code",
        "open-claw",
        "opencode",
        "qwen-code",
    } == set(root.readers)


def test_agents_skills_root_writers_are_the_manifest_entries_for_it() -> None:
    # The registry and the manifest agree on who writes the shared folder: every
    # harness whose manifest has a user-level entry for it is the owner or a
    # co-installer, and no other harness is.
    from apothem.lib.propagation import load_manifest

    writers = {
        public_id
        for entry in HARNESS_REGISTRY
        for public_id in [entry.public_id]
        if any(
            install.user_level
            and install.target.rstrip("/") == "${USER_HOME}/.agents/skills"
            for install in load_manifest()[entry.package_key].install
        )
    }
    root = _DECLARED["~/.agents/skills"]
    assert writers == {root.owner, *root.co_installers}


def test_support_roots_are_written_by_codex_and_the_seven_rules_adapters() -> None:
    expected = {
        "codex",
        "codebuddy",
        "cursor",
        "github-copilot",
        "kiro",
        "trae",
        "windsurf",
        "zed",
    }
    for name in ("rules", "templates"):
        root = _DECLARED[f"~/.config/apothem/{name}"]
        assert root.kind == "support"
        assert {root.owner, *root.co_installers} == expected


@pytest.mark.parametrize(
    ("public_id", "folder"),
    [
        ("codebuddy", "~/.codebuddy/skills"),
        ("kiro", "~/.kiro/skills"),
        ("trae", "~/.trae/skills"),
    ],
)
def test_own_skill_folders_are_registered_and_not_shared(
    public_id: str, folder: str
) -> None:
    # CodeBuddy, Kiro and Trae document their own user folder and not
    # ~/.agents/skills, so each writes its own folder and no other adapter does.
    assert _written_paths()[folder] == [public_id]
    assert folder not in _DECLARED


def test_agents_skills_root_lists_no_tool_the_vendor_docs_leave_open() -> None:
    # Antigravity, Kiro, CodeBuddy and Trae do not document a default load of
    # ~/.agents/skills, and Hermes names it only as a skills.external_dirs
    # example. Add one only with a vendor page that shows the load.
    root = _DECLARED["~/.agents/skills"]
    open_gaps = {"antigravity", "codebuddy", "hermes", "kiro", "trae"}
    assert open_gaps.isdisjoint(root.readers)


def test_open_claw_reads_agents_skills_only_under_its_default_state_dir() -> None:
    root = _DECLARED["~/.agents/skills"]
    assert "default state directory" in root.reader_conditions["open-claw"]


@pytest.mark.parametrize(
    ("path", "owner"),
    [("~/.claude/agents", "claude-code"), ("~/.codex/agents", "codex")],
)
def test_cursor_reads_the_agents_folders_of_claude_code_and_codex(
    path: str, owner: str
) -> None:
    root = _DECLARED[path]
    assert root.owner == owner
    assert root.readers == ("cursor",)
    # Where the owner writes the folder is not a condition on Cursor's reading it.
    assert not root.reader_conditions


def test_github_copilot_is_not_a_reader_of_the_claude_agents_folder() -> None:
    # The VS Code docs list ~/.claude/agents for the Anthropic Claude harness,
    # not for the Local harness that GitHub Copilot uses.
    assert "github-copilot" not in _DECLARED["~/.claude/agents"].readers
