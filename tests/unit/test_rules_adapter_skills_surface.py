# SPDX-License-Identifier: MIT

"""The seven rules-file adapters declare the skills and corpus they install.

GitHub Copilot, Cursor, Windsurf, Zed, CodeBuddy, Kiro and Trae write a rules
file into the project and, ahead of it, three user-level things: the skills and
the commands wrapped as skills, in a folder in the user home, and the rules and
templates corpus those skills cite, in ``~/.config/apothem/``. Cursor, GitHub
Copilot, Windsurf and Zed read the shared ``~/.agents/skills/``; CodeBuddy, Kiro
and Trae use the user folder their own vendor documents. This module pins what
every declaration surface says about that, without installing anything: the
manifest entries, the registry cells and paths, the capability dossier, the
anchor template, the convention pin and the compatibility matrix.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared import install_driver_converters as conv
from apothem.harnesses._shared.install_driver_agent_emitters import AGENT_EMITTERS
from apothem.harnesses._shared.install_driver_shared import SHARED_EMISSION
from apothem.lib.harness_registry import HARNESS_REGISTRY, get_harness_entry
from apothem.lib.propagation import load_manifest

_REPO = Path(__file__).resolve().parents[2]
_PKG = _REPO / "src" / "apothem"
_MATRIX = _PKG / "schemas" / "compatibility-matrix.yaml"

#: public id -> (package key, home-relative skills folder)
_SEVEN = {
    "cursor": ("cursor", ".agents/skills"),
    "github-copilot": ("github_copilot", ".agents/skills"),
    "windsurf": ("windsurf", ".agents/skills"),
    "zed": ("zed", ".agents/skills"),
    "codebuddy": ("codebuddy", ".codebuddy/skills"),
    "kiro": ("kiro", ".kiro/skills"),
    "trae": ("trae", ".trae/skills"),
}
_IDS = sorted(_SEVEN)

#: The adapters that also write the agents cohort as native subagents.
_WITH_AGENTS = frozenset(
    {"codebuddy", "cursor", "github-copilot", "kiro", "trae", "windsurf"}
)

#: The adapters that also register hooks natively, and the manifest modes of the
#: project entries that carry them (the dispatcher's support tree and the
#: key-merged registration), which follow the instruction anchor.
_HOOK_MODES = {
    "codebuddy": ["merge_tree_entries", "write_text"],
    "github-copilot": ["merge_tree_entries", "native_hooks"],
    "kiro": ["merge_tree_entries", "native_hooks"],
}

#: The harnesses that write ``~/.agents/skills/`` with the registered owner.
_SHARED_AGENTS_SKILLS = ("cursor", "github-copilot", "windsurf", "zed")


def _rules(public_id: str):
    return load_manifest()[_SEVEN[public_id][0]]


@pytest.mark.parametrize("public_id", _IDS)
def test_manifest_has_the_four_user_level_entries_before_the_project_anchor(
    public_id: str,
) -> None:
    folder = _SEVEN[public_id][1]
    install = _rules(public_id).install
    user = [entry for entry in install if entry.user_level]
    assert [(e.source, e.mode, e.target) for e in user] == [
        ("rules/", "merge_tree_entries", "${USER_HOME}/.config/apothem/rules/"),
        ("skills/", "native_skills", f"${{USER_HOME}}/{folder}/"),
        ("commands/", "command_skills", f"${{USER_HOME}}/{folder}/"),
        ("templates/", "merge_tree_entries", "${USER_HOME}/.config/apothem/templates/"),
    ]
    assert all(e.ownership_class == "apothem-owned" for e in user)
    # D19: the user-level steps run first, so a failure writing the user home
    # aborts the install before anything in the project changes.
    assert install[: len(user)] == user
    anchors = [e for e in install[len(user) :] if e.mode not in AGENT_EMITTERS]
    expected = ["sentinel_merge", *_HOOK_MODES.get(public_id, [])]
    assert [e.mode for e in anchors] == expected
    assert all("${PROJECT_ROOT}" in e.target for e in anchors)


@pytest.mark.parametrize("public_id", _IDS)
def test_manifest_blocks_name_no_harness_root(public_id: str) -> None:
    # A project-scope block has no harness root; a literal placeholder would be
    # resolved against the working directory.
    assert all("${HARNESS_ROOT}" not in e.target for e in _rules(public_id).install)


@pytest.mark.parametrize("public_id", _IDS)
def test_registry_lists_the_user_level_folders_and_cells(public_id: str) -> None:
    entry = get_harness_entry(public_id)
    folder = _SEVEN[public_id][1]
    assert f"~/{folder}/" in entry.target_paths
    assert "~/.config/apothem/{rules,templates}/" in entry.target_paths
    status = entry.capability_status
    assert status["skills"] == "native"
    assert status["commands"] == "converted"
    assert status["templates"] == "support-tree"
    assert status["rules"] == "native"
    for cell in ("skills", "commands", "templates"):
        assert cell not in entry.unsupported_rationale
    # The cohorts the adapter still does not write keep an honest rationale.
    if public_id in _HOOK_MODES:
        assert status["hooks"] == "native"
        assert "hooks" not in entry.unsupported_rationale
    else:
        assert status["hooks"] == "unsupported"
        assert entry.unsupported_rationale["hooks"].strip()
    if public_id in _WITH_AGENTS:
        assert status["agents"] == "converted"
        assert status["sub_agent_dispatch"] == "native"
        assert "agents" not in entry.unsupported_rationale
    else:
        assert status["agents"] == "unsupported"
        assert entry.unsupported_rationale["agents"].strip()


def test_the_seven_are_the_only_project_scope_rules_adapters_with_user_folders() -> (
    None
):
    with_user_level = {
        entry.public_id
        for entry in HARNESS_REGISTRY
        if any(e.user_level for e in load_manifest()[entry.package_key].install)
    }
    assert with_user_level == {"codex", *_SEVEN}


@pytest.mark.parametrize("public_id", _IDS)
def test_capability_dossier_declares_skills_and_converted_commands(
    public_id: str,
) -> None:
    entry = get_harness_entry(public_id)
    caps = yaml.safe_load((_REPO / entry.capabilities_path).read_text("utf-8"))
    assert caps["custom_command_support"] == "skills"
    assert caps["sub_agent_dispatch"] is (public_id in _WITH_AGENTS)
    assert "skills" in caps["layered_context_surface"]
    assert "~/.config/apothem" in caps["layered_context_surface"]
    losses = caps["conversion_losses"]["commands"]
    # Version, updated and portability fold under the standard metadata map.
    for key in ("version", "updated", "portability"):
        assert losses[key] == f"native:metadata.{key}"


@pytest.mark.parametrize("public_id", _IDS)
def test_anchor_template_names_the_skills_folder_and_no_longer_says_rules_only(
    public_id: str,
) -> None:
    entry = get_harness_entry(public_id)
    folder = _SEVEN[public_id][1]
    text = " ".join((_PKG / entry.template_sources[0]).read_text("utf-8").split())
    assert f"`~/{folder}/`" in text
    assert "`~/.config/apothem/`" in text
    assert "installed beside it" not in text
    assert "are not installed here" not in text
    assert "skill folder is in place" in text  # the verify sentence


@pytest.mark.parametrize("public_id", _IDS)
def test_convention_pin_records_the_skills_surface_and_the_open_probe(
    public_id: str,
) -> None:
    entry = get_harness_entry(public_id)
    folder = _SEVEN[public_id][1]
    pin = (_REPO / entry.standard_pin_path).read_text("utf-8")
    flat = " ".join(pin.split())
    snapshot = re.search(r"^- Snapshot date: (\d{4}-\d{2}-\d{2})$", pin, re.MULTILINE)
    assert snapshot is not None
    assert snapshot.group(1) >= "2026-10-24"  # ISO dates compare as text
    assert f"~/{folder}/" in flat
    assert "rules-only posture" not in flat
    assert "deliberate rules-only" not in flat
    # The reader's treatment of the extra frontmatter keys is not documented.
    assert "TODO(clarify)" in pin
    assert "SHARED_TOPLEVEL_KEYS" in flat or "metadata" in flat


def test_trae_records_the_user_folder_questions_for_agents_and_skills() -> None:
    """Trae documents ``~/.trae-cn/agents/`` where its other user paths are ``~/.trae/``.

    The China edition's skills page (docs.trae.cn) gives ``~/.trae-cn/skills``
    where the English page gives ``~/.trae/skills``. Its changelog (TRAE CN
    v3.3.63, personal edition only) says the global skills directories of the two
    editions are compatible, so the install writes ``~/.trae/skills/`` only; the
    pin and the manifest cite that entry and keep the other editions open. The
    user folder for subagents is open too, and the install writes neither
    ``.trae-cn`` folder.
    """
    pin = " ".join(
        (_REPO / get_harness_entry("trae").standard_pin_path).read_text("utf-8").split()
    )
    assert "~/.trae-cn/agents/" in pin
    assert "~/.trae-cn/skills" in pin
    assert "v3.3.63" in pin
    assert "TODO(clarify)" in pin
    manifest = (_PKG / "lib" / "propagation-manifest.yaml").read_text("utf-8")
    block = manifest[manifest.index("\n  trae:\n") : manifest.index("\n  zed:\n")]
    assert "TODO(clarify)" in block
    assert "~/.trae-cn/agents/" in block
    assert "~/.trae-cn/skills" in block
    assert "v3.3.63" in block
    assert not any(".trae-cn" in e.target for e in load_manifest()["trae"].install)
    # The cross-tool folder stays out of Trae's block.
    assert ".agents/skills" not in "".join(
        e.target for e in load_manifest()["trae"].install
    )


@pytest.mark.parametrize("public_id", _IDS)
def test_compatibility_matrix_lists_the_skills_delivery(public_id: str) -> None:
    matrix = yaml.safe_load(_MATRIX.read_text("utf-8"))
    row = next(r for r in matrix["harnesses"] if r["name"] == public_id)
    assert row["supports_skills"] is True
    classes = matrix["asset_classes"]
    for cohort in ("skills", "commands", "templates"):
        assert public_id in classes[cohort]["compatible_harnesses"], cohort
    folder = _SEVEN[public_id][1]
    assert f"~/{folder}/" in classes["skills"]["materialisation_strategy"][public_id]
    assert f"~/{folder}/" in classes["commands"]["materialisation_strategy"][public_id]
    assert (
        "~/.config/apothem/templates/"
        in (classes["templates"]["materialisation_strategy"][public_id])
    )


def test_agents_skills_writers_are_the_registered_co_installers() -> None:
    from apothem.lib.harness_registry import SHARED_ROOTS

    root = next(r for r in SHARED_ROOTS if r.path == "~/.agents/skills/")
    assert root.owner == "codex"
    assert root.co_installers == _SHARED_AGENTS_SKILLS
    # CodeBuddy, Kiro and Trae document their own folders and not this one.
    assert {"codebuddy", "kiro", "trae"}.isdisjoint(
        {*root.readers, *root.co_installers}
    )


def test_the_shared_emission_fits_a_catalog_of_fifty_thousand_bytes() -> None:
    # A reader that lists every skill's name and description in one catalog may
    # cap it (a 50 KB cap was reported for Zed from a single reading that has not
    # been confirmed). The shared emission stays far below that, so the open
    # question does not block the release; a growing corpus trips this first.
    src = install_driver.APOTHEM_SRC
    sizes: list[int] = []
    for skill in sorted((src / "skills").glob("*/SKILL.md")):
        text = conv._native_skill_emission(SHARED_EMISSION, skill.read_text("utf-8"))[0]
        sizes.append(_catalog_bytes(skill.parent.name, text))
    skill_names = {skill.parent.name for skill in (src / "skills").glob("*/SKILL.md")}
    for command in sorted((src / "commands").glob("*.md")):
        if command.stem in skill_names or command.name in {"README.md", "AGENTS.md"}:
            continue
        files = conv._command_skill_files(
            command, harness_name=SHARED_EMISSION, install_root=Path("/unused")
        )
        sizes.append(_catalog_bytes(command.stem, files["SKILL.md"].decode("utf-8")))
    assert len(sizes) >= 60
    assert sum(sizes) < 50_000, sum(sizes)


def _catalog_bytes(name: str, skill_text: str) -> int:
    head = skill_text[4 : skill_text.index("\n---\n", 4)]
    description = str(yaml.safe_load(head)["description"])
    return len(name.encode("utf-8")) + len(description.encode("utf-8"))


def test_manifest_comments_no_longer_call_the_seven_rules_only() -> None:
    manifest = (_PKG / "lib" / "propagation-manifest.yaml").read_text("utf-8")
    for public_id in _IDS:
        key = _SEVEN[public_id][0]
        start = manifest.index(f"\n  {key}:\n")
        end = manifest.find("\n\n  ", start + 5)
        block = manifest[start : end if end != -1 else None]
        assert re.search(r"\.config/apothem/", block), public_id
