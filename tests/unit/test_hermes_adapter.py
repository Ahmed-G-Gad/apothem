# SPDX-License-Identifier: MIT

"""Unit tests for the hermes harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

import pytest
import yaml

import apothem.harnesses.hermes as hermes_pkg
from apothem.harnesses import HarnessAdapter
from apothem.harnesses._shared.install_driver import MaterializationError
from apothem.harnesses.hermes import HermesAdapter
from apothem.harnesses.hermes.materializer import SKILLS_DIRECTORY
from apothem.lib.propagation import load_manifest

_ADAPTER_DIR = Path(hermes_pkg.__file__).resolve().parent


def _capabilities() -> dict[str, object]:
    return yaml.safe_load(
        (_ADAPTER_DIR / "capabilities.yml").read_text(encoding="utf-8")
    )


@pytest.fixture
def adapter() -> HermesAdapter:
    return HermesAdapter()


def test_protocol_conformance(adapter: HermesAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: HermesAdapter) -> None:
    assert adapter.name == "hermes"


def test_output_path_is_path(adapter: HermesAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: HermesAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: HermesAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({})  # must not raise


def test_uninstall_noop_when_not_installed(
    adapter: HermesAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nonexistent_config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: missing))
    adapter.uninstall()  # must not raise when output_path does not exist


def test_uninstall_keeps_operator_keys_and_strips_apothem(
    adapter: HermesAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall of the materializer-rendered config.yaml: install
    # with an MCP server (so Apothem writes mcp_servers), add operator
    # channels/auth keys, uninstall, and assert the operator keys survive while
    # Apothem's server entries are removed — with NO whole-file .bak sibling.
    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    target = tmp_path / "config.yaml"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({"mcp_servers": {"demo": {"command": "demo-bin"}}})
    doc = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    assert "demo" in doc["mcp_servers"]  # Apothem-authored MCP server
    doc["channels"] = {"slack": "xoxb-token"}
    doc["auth"] = {"token": "operator-secret"}
    target.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    adapter.uninstall()

    assert target.is_file()  # operator content remains
    remaining = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert remaining["channels"] == {"slack": "xoxb-token"}
    assert remaining["auth"] == {"token": "operator-secret"}
    assert "mcp_servers" not in remaining
    assert "skills" not in remaining  # the skills directory entry Apothem added
    assert not list(tmp_path.glob("config.yaml.*.bak"))


def test_capabilities_declare_mcp_subagent_and_memory() -> None:
    # Hermes documents the top-level mcp_servers block, delegation/delegate_task
    # subagent dispatch, and durable memory at ~/.hermes/memories/.
    capabilities = _capabilities()
    assert capabilities["mcp_servers"]
    assert capabilities["sub_agent_dispatch"] is True
    assert "memories" in str(capabilities["agent_memory_surface"])


def test_update_moves_servers_out_of_the_auxiliary_model_slot(
    adapter: HermesAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Earlier releases wrote the profile's servers under auxiliary.mcp, which
    # Hermes reads as the auxiliary model slot for MCP tool dispatch. An update
    # over such a config moves them to the top-level mcp_servers block and
    # leaves the operator's own auxiliary routing alone.
    from apothem.lib import install_ledger
    from apothem.lib.install_ledger import LedgerRecord, LedgerTarget

    target = tmp_path / ".hermes" / "config.yaml"
    target.parent.mkdir()
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    profile = {
        "mcp_servers": {"fs": {"transport": "stdio", "command": "npx", "args": ["srv"]}}
    }
    legacy = {
        "auxiliary": {
            "compression": {"provider": "openrouter"},
            "mcp": {"fs": {"command": "npx", "args": ["srv"]}},
        }
    }
    target.write_text(yaml.safe_dump(legacy, sort_keys=False), encoding="utf-8")
    # The install record an earlier release left (no ownership recorded).
    install_ledger.append_record(
        LedgerRecord.create(
            harness="hermes",
            root=target.parent,
            kind="install",
            targets=(LedgerTarget(str(target), "write_text", "operator-owned"),),
        )
    )

    adapter.update(profile)

    doc = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert doc["mcp_servers"] == {"fs": {"command": "npx", "args": ["srv"]}}
    assert doc["auxiliary"] == {"compression": {"provider": "openrouter"}}

    adapter.uninstall()
    remaining = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert remaining == {"auxiliary": {"compression": {"provider": "openrouter"}}}


_LEGACY_SERVERS = {"fs": {"command": "npx", "args": ["srv"]}}
_OPERATOR_ROUTING = {"compression": {"provider": "openrouter"}}


@pytest.fixture
def legacy_install(
    adapter: HermesAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """The install record an earlier release left, with no update since.

    That release wrote the profile's servers under ``auxiliary.mcp`` and
    recorded no ownership. The shared profile at its default path still lists
    the same server. Returns the ``config.yaml`` path; each test writes it.
    """
    from apothem.lib import install_ledger
    from apothem.lib.install_ledger import LedgerRecord, LedgerTarget

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        yaml.safe_dump(
            {
                "identity": {"name": "Example User"},
                "mcp_servers": {
                    "fs": {"transport": "stdio", "command": "npx", "args": ["srv"]}
                },
            }
        ),
        encoding="utf-8",
    )
    target = home / ".hermes" / "config.yaml"
    target.parent.mkdir(parents=True)
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    install_ledger.append_record(
        LedgerRecord.create(
            harness="hermes",
            root=target.parent,
            kind="install",
            targets=(LedgerTarget(str(target), "write_text", "operator-owned"),),
        )
    )
    return target


def _write(target: Path, doc: dict[str, object]) -> None:
    target.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def test_uninstall_removes_the_legacy_auxiliary_mcp_block(
    adapter: HermesAdapter, legacy_install: Path
) -> None:
    # Uninstalling without updating first removes the servers the earlier
    # release wrote, and keeps the operator's own auxiliary routing.
    _write(legacy_install, {"auxiliary": {**_OPERATOR_ROUTING, "mcp": _LEGACY_SERVERS}})

    adapter.uninstall()

    remaining = yaml.safe_load(legacy_install.read_text(encoding="utf-8"))
    assert remaining == {"auxiliary": _OPERATOR_ROUTING}


def test_uninstall_drops_an_auxiliary_mapping_left_empty(
    adapter: HermesAdapter, legacy_install: Path
) -> None:
    _write(
        legacy_install,
        {"model": "operator-model", "auxiliary": {"mcp": _LEGACY_SERVERS}},
    )

    adapter.uninstall()

    remaining = yaml.safe_load(legacy_install.read_text(encoding="utf-8"))
    assert remaining == {"model": "operator-model"}


def test_uninstall_keeps_an_operator_edited_auxiliary_mcp(
    adapter: HermesAdapter, legacy_install: Path
) -> None:
    # The value no longer equals what the earlier release wrote, so it is the
    # operator's now: uninstall leaves it, exactly as an update would.
    edited = {"fs": {"command": "npx", "args": ["srv", "--read-only"]}}
    doc = {"auxiliary": {**_OPERATOR_ROUTING, "mcp": edited}}
    _write(legacy_install, doc)

    adapter.uninstall()

    assert yaml.safe_load(legacy_install.read_text(encoding="utf-8")) == doc


def test_uninstall_without_a_shared_profile_leaves_the_legacy_block(
    adapter: HermesAdapter, legacy_install: Path, tmp_path: Path
) -> None:
    # With no profile to render the earlier value from, nothing can be shown to
    # be Apothem's, so nothing is removed.
    (tmp_path / "home" / ".config" / "apothem" / "profile.yaml").unlink()
    doc = {"auxiliary": {**_OPERATOR_ROUTING, "mcp": _LEGACY_SERVERS}}
    _write(legacy_install, doc)

    adapter.uninstall()

    assert yaml.safe_load(legacy_install.read_text(encoding="utf-8")) == doc


# --- skills.external_dirs ----------------------------------------------------
#
# Hermes lists skills.external_dirs last in its precedence order (project
# skills, then ~/.hermes/skills/, then skills.create_dir, then the external
# directories; https://hermes-agent.nousresearch.com/docs/user-guide/features/skills,
# read 2026-10-24). The adapter lists its support skills directory there and
# owns only that entry.

_OPERATOR_EXTERNAL_DIRS = ["~/team-skills"]
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
    return home / ".hermes" / "config.yaml"


def _config(home: Path) -> dict[str, object]:
    return yaml.safe_load(_config_path(home).read_text(encoding="utf-8"))


def _write_text(home: Path, text: str) -> None:
    _config_path(home).parent.mkdir(exist_ok=True)
    _config_path(home).write_text(text, encoding="utf-8")


def _write_config(home: Path, doc: dict[str, object]) -> None:
    _write_text(home, yaml.safe_dump(doc, sort_keys=False))


def _external_dirs(home: Path) -> list[str]:
    return _config(home)["skills"]["external_dirs"]  # type: ignore[index,return-value]


def _skill_roots(home: Path, project: Path) -> list[Path]:
    """Return Hermes's file-backed skill roots, highest precedence first.

    The order is the vendor's, from the page cited above: project skills, then
    ``~/.hermes/skills/``, then the ``skills.external_dirs`` entries.
    ``skills.create_dir`` is left out: Apothem sets nothing there and the vendor
    page names no default. The last roots are the ``external_dirs`` entries of
    the config the adapter wrote, so the test follows the key rather than the
    manifest.
    """
    return [
        project / ".hermes" / "skills",
        project / ".agents" / "skills",
        home / ".hermes" / "skills",
        *(Path(entry).expanduser() for entry in _external_dirs(home)),
    ]


def _winner(name: str, roots: list[Path]) -> Path | None:
    """Return the copy of skill *name* in the first root that holds one.

    That is the adapter's reading of the documented order (earlier wins); the
    vendor page does not state the clash rule (see the pin's TODO(clarify)).
    """
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
        item for item in load_manifest()["hermes"].install if item.source == "skills/"
    )
    target = Template(entry.target).substitute(HARNESS_ROOT="~/.hermes")
    assert target.rstrip("/") == SKILLS_DIRECTORY


def test_install_lists_the_directory_the_skills_land_in(
    adapter: HermesAdapter, home: Path
) -> None:
    adapter.install({})

    assert _config(home) == {"skills": {"external_dirs": [SKILLS_DIRECTORY]}}
    listed = Path(SKILLS_DIRECTORY).expanduser()
    assert listed == home / ".hermes" / ".apothem" / "support" / "skills"
    assert any(listed.glob(f"*/{_SKILL_FILE}"))


def test_install_and_update_list_the_directory_once(
    adapter: HermesAdapter, home: Path
) -> None:
    adapter.install({})
    first = _config_path(home).read_bytes()

    adapter.install({})
    adapter.update({})

    assert _config_path(home).read_bytes() == first
    assert _external_dirs(home) == [SKILLS_DIRECTORY]


def test_install_keeps_the_operators_external_dirs_first(
    adapter: HermesAdapter, home: Path
) -> None:
    operator = {
        "model": "operator-model",
        "skills": {
            "config": {"demo": {"enabled": False}},
            "external_dirs": list(_OPERATOR_EXTERNAL_DIRS),
        },
    }
    _write_config(home, operator)

    adapter.install({"mcp_servers": {"fs": {"command": "npx", "args": ["srv"]}}})
    adapter.update({"mcp_servers": {"fs": {"command": "npx", "args": ["srv"]}}})

    merged = _config(home)
    assert merged["model"] == "operator-model"
    assert merged["skills"]["config"] == {"demo": {"enabled": False}}  # type: ignore[index]
    assert _external_dirs(home) == [*_OPERATOR_EXTERNAL_DIRS, SKILLS_DIRECTORY]
    assert "fs" in merged["mcp_servers"]  # type: ignore[operator]


@pytest.mark.parametrize(
    "operator",
    [
        {"model": "operator-model"},
        {"skills": {"config": {"demo": {"enabled": False}}}},
        {"skills": {"external_dirs": ["~/team-skills"]}},
        {
            "skills": {
                "config": {"demo": {"enabled": False}},
                "external_dirs": ["~/team-skills", "/home/shared/team-skills"],
            }
        },
    ],
    ids=["no-skills", "skills-config-only", "own-external-dirs", "both"],
)
def test_uninstall_removes_only_the_apothem_entry(
    adapter: HermesAdapter, home: Path, operator: dict[str, object]
) -> None:
    _write_config(home, operator)
    adapter.install({})
    assert SKILLS_DIRECTORY in _external_dirs(home)

    adapter.uninstall()

    assert _config(home) == operator


def test_uninstall_keeps_an_entry_the_operator_listed_themselves(
    adapter: HermesAdapter, home: Path
) -> None:
    # Earlier docs told the operator to add this directory by hand. An entry
    # that was already in the file is theirs, even though it equals what Apothem
    # would write: install does not claim it, so uninstall leaves it.
    operator = {"skills": {"external_dirs": [SKILLS_DIRECTORY]}}
    _write_config(home, operator)

    adapter.install({})
    adapter.uninstall()

    assert _config(home) == operator


def test_an_operator_skill_takes_precedence_in_every_earlier_root(
    adapter: HermesAdapter, home: Path, tmp_path: Path
) -> None:
    adapter.install({})
    roots = _skill_roots(home, tmp_path / "project")
    earlier, installed = roots[:-1], roots[-1]
    names = sorted(
        path.name for path in installed.iterdir() if (path / _SKILL_FILE).is_file()
    )[: len(earlier)]
    assert len(names) == len(earlier)
    # With no clash Hermes reaches each Apothem copy through the key.
    for name in names:
        assert _winner(name, roots) == installed / name / _SKILL_FILE

    # The operator keeps a skill named like an Apothem one in each earlier root
    # (a different name per root).
    mine = {}
    for root, name in zip(earlier, names, strict=True):
        copy = root / name / _SKILL_FILE
        copy.parent.mkdir(parents=True)
        copy.write_text(f"operator copy of {name}\n", encoding="utf-8")
        mine[name] = copy

    # Theirs is the one the documented order reaches first, and an update
    # replaces neither copy.
    for _ in range(2):
        for name, copy in mine.items():
            assert _winner(name, roots) == copy
            assert (installed / name / _SKILL_FILE).is_file()
        adapter.update({})
    adapter.uninstall()
    for name, copy in mine.items():
        assert copy.read_text(encoding="utf-8") == f"operator copy of {name}\n"


def test_install_writes_into_no_earlier_skill_root(
    adapter: HermesAdapter, home: Path, tmp_path: Path
) -> None:
    adapter.install({})

    earlier = _skill_roots(home, tmp_path / "project")[:-1]
    assert [root for root in earlier if root.exists()] == []


def test_verify_requires_the_skills_entry(adapter: HermesAdapter, home: Path) -> None:
    adapter.install({})
    assert adapter.verify()

    _write_config(home, {"model": "operator-model"})
    assert not adapter.verify()

    adapter.update({})
    assert adapter.verify()


def test_install_refuses_a_commented_config_it_would_have_to_rewrite(
    adapter: HermesAdapter, home: Path
) -> None:
    # PyYAML would drop the operator's comments on rewrite, so the write is
    # refused and the file is left as it was.
    text = "# my model\nmodel: operator-model\n"
    _write_text(home, text)

    with pytest.raises(MaterializationError, match="comments"):
        adapter.install({})

    assert _config_path(home).read_text(encoding="utf-8") == text


def test_install_leaves_a_commented_config_that_already_lists_the_directory(
    adapter: HermesAdapter, home: Path
) -> None:
    # The fix the refusal names: the operator adds the entry themselves, and a
    # later install has nothing to change.
    text = f"# mine\nskills:\n  external_dirs:\n    - {SKILLS_DIRECTORY}\n"
    _write_text(home, text)

    adapter.install({})

    assert _config_path(home).read_text(encoding="utf-8") == text
    assert adapter.verify()


@pytest.mark.parametrize(
    ("operator", "after_uninstall"),
    [
        ({"model": "operator-model", "skills": None}, {"model": "operator-model"}),
        (
            {"model": "operator-model", "skills": {"external_dirs": None}},
            {"model": "operator-model", "skills": {}},
        ),
        (
            {"skills": {"config": {"demo": {"enabled": False}}, "external_dirs": None}},
            {"skills": {"config": {"demo": {"enabled": False}}}},
        ),
    ],
    ids=["null-skills", "null-external-dirs", "null-external-dirs-beside-config"],
)
def test_a_null_skills_key_is_filled_and_its_entry_removed_again(
    adapter: HermesAdapter,
    home: Path,
    operator: dict[str, object],
    after_uninstall: dict[str, object],
) -> None:
    # `skills:` with nothing under it holds nothing of the operator's, so install
    # fills it, records the entry as Apothem's, and uninstall takes it out again.
    _write_config(home, operator)

    adapter.install({})
    adapter.update({})
    assert _external_dirs(home) == [SKILLS_DIRECTORY]

    adapter.uninstall()

    assert _config(home) == after_uninstall


@pytest.mark.parametrize(
    ("operator", "where"),
    [
        ({"skills": "off"}, "skills"),
        ({"skills": ["team"]}, "skills"),
        ({"skills": {"external_dirs": "~/team-skills"}}, "skills.external_dirs"),
        ({"skills": {"external_dirs": {"team": "~/team"}}}, "skills.external_dirs"),
    ],
    ids=[
        "scalar-skills",
        "list-skills",
        "scalar-external-dirs",
        "mapping-external-dirs",
    ],
)
def test_install_refuses_a_skills_value_of_the_wrong_shape(
    adapter: HermesAdapter, home: Path, operator: dict[str, object], where: str
) -> None:
    # Replacing the operator's value would lose it, and Apothem would record
    # nothing for the entry it wrote there, so uninstall could not take it out.
    _write_config(home, operator)
    before = _config_path(home).read_bytes()

    with pytest.raises(MaterializationError, match=f"at {where}, where Apothem"):
        adapter.install({})

    assert _config_path(home).read_bytes() == before
