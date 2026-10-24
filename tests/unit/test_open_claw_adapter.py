# SPDX-License-Identifier: MIT

"""Unit tests for the open-claw harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

import json
from pathlib import Path
from string import Template

import pytest
import yaml

import apothem.harnesses.open_claw as open_claw_pkg
from apothem.harnesses import HarnessAdapter
from apothem.harnesses._shared.install_driver import MaterializationError
from apothem.harnesses.open_claw import OpenClawAdapter
from apothem.harnesses.open_claw.materializer import SKILLS_DIRECTORY
from apothem.lib.propagation import load_manifest

_ADAPTER_DIR = Path(open_claw_pkg.__file__).resolve().parent


def _capabilities() -> dict[str, object]:
    return yaml.safe_load(
        (_ADAPTER_DIR / "capabilities.yml").read_text(encoding="utf-8")
    )


@pytest.fixture
def adapter() -> OpenClawAdapter:
    return OpenClawAdapter()


def test_protocol_conformance(adapter: OpenClawAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: OpenClawAdapter) -> None:
    assert adapter.name == "open-claw"


def test_output_path_is_path(adapter: OpenClawAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: OpenClawAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: OpenClawAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({})  # must not raise


def test_uninstall_noop_when_not_installed(
    adapter: OpenClawAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nonexistent_config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: missing))
    adapter.uninstall()  # must not raise when output_path does not exist


def test_uninstall_keeps_operator_keys_and_strips_apothem(
    adapter: OpenClawAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall of the materializer-rendered openclaw.json: the
    # operator authors their own keys into the config; uninstall keeps them and
    # leaves no whole-file .bak sibling. (OpenClaw renders an empty {} config, so
    # an operator-free install is an Apothem-only file the uninstall deletes.)
    import json

    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    target = tmp_path / "openclaw.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({})
    # The operator authors their own configuration into the file.
    target.write_text(json.dumps({"operatorKey": "value"}, indent=2), encoding="utf-8")

    adapter.uninstall()

    assert target.is_file()
    remaining = json.loads(target.read_text(encoding="utf-8"))
    assert remaining == {"operatorKey": "value"}
    assert not list(tmp_path.glob("openclaw.json.*.bak"))


def test_uninstall_deletes_apothem_only_config(
    adapter: OpenClawAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An Apothem-only config (empty render, no operator keys) is deleted.
    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    target = tmp_path / "openclaw.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({})
    assert target.is_file()

    adapter.uninstall()

    assert not target.exists()
    assert not list(tmp_path.glob("openclaw.json.*.bak"))


def test_capabilities_declare_subagent_dispatch_and_no_mcp_file() -> None:
    # Open-Claw documents subagents via agents.list[].subagents.allowAgents,
    # but MCP is a CLI-command surface with no adapter-owned config-file block.
    # Skills load through skills.load.extraDirs, which the adapter authors.
    capabilities = _capabilities()
    assert capabilities["sub_agent_dispatch"] is True
    assert capabilities["mcp_servers"] == []
    assert capabilities["custom_command_support"] == "skills-extraDirs"


# --- skills.load.extraDirs ---------------------------------------------------
#
# OpenClaw reads skills from several roots and, when one skill name appears in
# more than one, uses the highest source; skills.load.extraDirs is the lowest
# (https://docs.openclaw.ai/tools/skills, read 2026-10-24). The adapter lists
# its support skills directory there and owns only that entry.

_OPERATOR_EXTRA_DIRS = ["~/team-skills"]
_SKILL_FILE = "SKILL.md"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway home directory; the adapter's output path resolves inside it."""
    root = tmp_path / "home"
    root.mkdir()
    monkeypatch.setenv("HOME", str(root))
    monkeypatch.setenv("USERPROFILE", str(root))
    return root


def _config_path(home: Path) -> Path:
    return home / ".openclaw" / "openclaw.json"


def _config(home: Path) -> dict[str, object]:
    return json.loads(_config_path(home).read_text(encoding="utf-8"))


def _write_config(home: Path, doc: dict[str, object]) -> None:
    _config_path(home).parent.mkdir(exist_ok=True)
    _config_path(home).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _write_text(home: Path, text: str) -> None:
    _config_path(home).parent.mkdir(exist_ok=True)
    _config_path(home).write_text(text, encoding="utf-8")


def _extra_dirs(home: Path) -> list[str]:
    return _config(home)["skills"]["load"]["extraDirs"]  # type: ignore[index,return-value]


def _skill_roots(home: Path, workspace: Path) -> list[Path]:
    """Return OpenClaw's file-backed skill roots, highest precedence first.

    The order and the name-clash rule (the highest source wins) are the
    vendor's, from the page cited above. Workshop, bundled and plugin skills are
    left out: neither Apothem nor the operator fills them. The last roots are the
    ``extraDirs`` entries of the config the adapter wrote, so the test follows
    the key rather than the manifest.
    """
    return [
        workspace / "skills",
        workspace / ".agents" / "skills",
        home / ".agents" / "skills",
        home / ".openclaw" / "skills",
        *(Path(entry).expanduser() for entry in _extra_dirs(home)),
    ]


def _winner(name: str, roots: list[Path]) -> Path | None:
    return next(
        (
            root / name / _SKILL_FILE
            for root in roots
            if (root / name / _SKILL_FILE).is_file()
        ),
        None,
    )


def test_skills_directory_is_the_manifest_skills_target() -> None:
    entry = next(
        item
        for item in load_manifest()["open_claw"].install
        if item.source == "skills/"
    )
    target = Template(entry.target).substitute(HARNESS_ROOT="~/.openclaw")
    assert target.rstrip("/") == SKILLS_DIRECTORY


def test_install_lists_the_directory_the_skills_land_in(
    adapter: OpenClawAdapter, home: Path
) -> None:
    adapter.install({})

    assert _config(home) == {"skills": {"load": {"extraDirs": [SKILLS_DIRECTORY]}}}
    listed = Path(SKILLS_DIRECTORY).expanduser()
    assert listed == home / ".openclaw" / ".apothem" / "support" / "skills"
    assert any(listed.glob(f"*/{_SKILL_FILE}"))


def test_install_and_update_list_the_directory_once(
    adapter: OpenClawAdapter, home: Path
) -> None:
    adapter.install({})
    first = _config_path(home).read_bytes()

    adapter.install({})
    adapter.update({})

    assert _config_path(home).read_bytes() == first
    assert _extra_dirs(home) == [SKILLS_DIRECTORY]


def test_install_keeps_the_operators_extra_dirs_first(
    adapter: OpenClawAdapter, home: Path
) -> None:
    operator = {
        "gateway": {"port": 18789},
        "skills": {"load": {"watch": True, "extraDirs": list(_OPERATOR_EXTRA_DIRS)}},
    }
    _write_config(home, operator)

    adapter.install({})
    adapter.update({})

    merged = _config(home)
    assert merged["gateway"] == {"port": 18789}
    assert merged["skills"]["load"]["watch"] is True  # type: ignore[index]
    assert _extra_dirs(home) == [*_OPERATOR_EXTRA_DIRS, SKILLS_DIRECTORY]


@pytest.mark.parametrize(
    "operator",
    [
        {"gateway": {"port": 18789}},
        {"skills": {"load": {"watch": True}}},
        {"skills": {"entries": {"demo": {"enabled": False}}}},
        {"skills": {"load": {"extraDirs": ["~/team-skills"]}}},
    ],
    ids=["no-skills", "no-extra-dirs", "other-skills-keys", "own-extra-dirs"],
)
def test_uninstall_removes_only_the_apothem_entry(
    adapter: OpenClawAdapter, home: Path, operator: dict[str, object]
) -> None:
    _write_config(home, operator)
    adapter.install({})
    assert SKILLS_DIRECTORY in _extra_dirs(home)

    adapter.uninstall()

    assert _config(home) == operator


def test_uninstall_keeps_an_entry_the_operator_listed_themselves(
    adapter: OpenClawAdapter, home: Path
) -> None:
    # An entry that was already in the file is the operator's, even though it
    # equals what Apothem would write: install does not claim it.
    operator = {"skills": {"load": {"extraDirs": [SKILLS_DIRECTORY]}}}
    _write_config(home, operator)

    adapter.install({})
    adapter.uninstall()

    assert _config(home) == operator


def test_an_operator_skill_wins_a_name_clash_in_every_higher_root(
    adapter: OpenClawAdapter, home: Path, tmp_path: Path
) -> None:
    adapter.install({})
    roots = _skill_roots(home, tmp_path / "workspace")
    higher, installed = roots[:-1], roots[-1]
    names = sorted(
        path.name for path in installed.iterdir() if (path / _SKILL_FILE).is_file()
    )[: len(higher)]
    assert len(names) == len(higher)
    # With no clash OpenClaw reaches each Apothem copy through the key.
    for name in names:
        assert _winner(name, roots) == installed / name / _SKILL_FILE

    # The operator keeps a skill named like an Apothem one in each higher root
    # (a different name per root).
    mine = {}
    for root, name in zip(higher, names, strict=True):
        copy = root / name / _SKILL_FILE
        copy.parent.mkdir(parents=True)
        copy.write_text(f"operator copy of {name}\n", encoding="utf-8")
        mine[name] = copy

    # Theirs is the one loaded, and an update replaces neither copy.
    for _ in range(2):
        for name, copy in mine.items():
            assert _winner(name, roots) == copy
            assert (installed / name / _SKILL_FILE).is_file()
        adapter.update({})
    adapter.uninstall()
    for name, copy in mine.items():
        assert copy.read_text(encoding="utf-8") == f"operator copy of {name}\n"


def test_install_writes_into_no_higher_precedence_skill_root(
    adapter: OpenClawAdapter, home: Path, tmp_path: Path
) -> None:
    adapter.install({})

    higher = _skill_roots(home, tmp_path / "workspace")[:-1]
    assert [root for root in higher if root.exists()] == []


def test_verify_requires_the_skills_entry(adapter: OpenClawAdapter, home: Path) -> None:
    adapter.install({})
    assert adapter.verify()

    _write_config(home, {"gateway": {"port": 18789}})
    assert not adapter.verify()

    adapter.update({})
    assert adapter.verify()


def test_verify_reads_the_json5_dialect_openclaw_reads(
    adapter: OpenClawAdapter, home: Path
) -> None:
    adapter.install({})
    _write_text(
        home,
        f'// mine\n{{ skills: {{ load: {{ extraDirs: ["{SKILLS_DIRECTORY}",], }}, }}, }}\n',
    )

    assert adapter.verify()


def test_install_refuses_a_commented_config_it_would_have_to_rewrite(
    adapter: OpenClawAdapter, home: Path
) -> None:
    # Rewriting the file as strict JSON would drop the operator's comments, so
    # the write is refused and the file is left as it was.
    text = "// my gateway\n{ gateway: { port: 18789 } }\n"
    _write_text(home, text)

    with pytest.raises(MaterializationError, match="JSON5"):
        adapter.install({})

    assert _config_path(home).read_text(encoding="utf-8") == text


def test_install_leaves_a_commented_config_that_already_lists_the_directory(
    adapter: OpenClawAdapter, home: Path
) -> None:
    # The fix the refusal names: the operator adds the entry themselves, and a
    # later install has nothing to change.
    text = (
        f'// mine\n{{ skills: {{ load: {{ extraDirs: ["{SKILLS_DIRECTORY}"] }} }} }}\n'
    )
    _write_text(home, text)

    adapter.install({})

    assert _config_path(home).read_text(encoding="utf-8") == text
    assert adapter.verify()


@pytest.mark.parametrize(
    ("operator", "after_uninstall"),
    [
        ({"gateway": {"port": 18789}, "skills": None}, {"gateway": {"port": 18789}}),
        (
            {"gateway": {"port": 18789}, "skills": {"load": None}},
            {"gateway": {"port": 18789}, "skills": {}},
        ),
        (
            {"skills": {"load": {"watch": True, "extraDirs": None}}},
            {"skills": {"load": {"watch": True}}},
        ),
    ],
    ids=["null-skills", "null-load", "null-extra-dirs-beside-watch"],
)
def test_a_null_skills_key_is_filled_and_its_entry_removed_again(
    adapter: OpenClawAdapter,
    home: Path,
    operator: dict[str, object],
    after_uninstall: dict[str, object],
) -> None:
    # `skills: null` holds nothing of the operator's, so install fills it,
    # records the entry as Apothem's, and uninstall takes it out again.
    _write_config(home, operator)

    adapter.install({})
    adapter.update({})
    assert _extra_dirs(home) == [SKILLS_DIRECTORY]

    adapter.uninstall()

    assert _config(home) == after_uninstall


@pytest.mark.parametrize(
    ("operator", "where"),
    [
        ({"skills": "off"}, "skills"),
        ({"skills": {"load": ["team"]}}, "skills.load"),
        ({"skills": {"load": {"extraDirs": "~/team-skills"}}}, "skills.load.extraDirs"),
        (
            {"skills": {"load": {"extraDirs": {"team": "~/team"}}}},
            "skills.load.extraDirs",
        ),
    ],
    ids=["scalar-skills", "list-load", "scalar-extra-dirs", "mapping-extra-dirs"],
)
def test_install_refuses_a_skills_value_of_the_wrong_shape(
    adapter: OpenClawAdapter, home: Path, operator: dict[str, object], where: str
) -> None:
    # Replacing the operator's value would lose it, and Apothem would record
    # nothing for the entry it wrote there, so uninstall could not take it out.
    _write_config(home, operator)
    before = _config_path(home).read_bytes()

    with pytest.raises(MaterializationError, match=f"at {where}, where Apothem"):
        adapter.install({})

    assert _config_path(home).read_bytes() == before
