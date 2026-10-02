# SPDX-License-Identifier: MIT

"""Install advisories for shared roots.

Installing the owner of a shared root (Codex for ``~/.agents/skills/``) puts
Apothem content in front of every reader, so the install names the readers.
Installing a reader while the shared root already holds another adapter's
Apothem content says where that content comes from.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.lib.harness_registry import SHARED_ROOTS, get_harness_entry
from apothem.lib.install_advisories import (
    mcp_profile_advisories,
    shared_root_advisories,
)

_AGENTS_SKILLS = next(root for root in SHARED_ROOTS if root.owner == "codex")


def _skill(home: Path, name: str) -> None:
    folder = home / ".agents" / "skills" / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: x\n---\n", encoding="utf-8"
    )


def test_owner_install_names_every_reader(tmp_path: Path) -> None:
    advisories = shared_root_advisories("codex", home=tmp_path, project=None)
    owner = [a for a in advisories if a["role"] == "owner"]
    assert len(owner) == 1
    entry = owner[0]
    assert entry["outcome"] == "advisory"
    assert entry["operation"] == "shared_root"
    assert entry["harness"] == "codex"
    assert entry["path"] == str(tmp_path / ".agents" / "skills")
    message = str(entry["message"])
    assert "~/.agents/skills/" in message
    for reader in _AGENTS_SKILLS.readers:
        assert get_harness_entry(reader).display_name in message, reader


def test_reader_install_names_the_owner_when_apothem_content_is_present(
    tmp_path: Path,
) -> None:
    _skill(tmp_path, "workflow")  # an Apothem skill name
    advisories = shared_root_advisories("cursor", home=tmp_path, project=None)
    reader = [a for a in advisories if a["role"] == "reader"]
    assert len(reader) == 1
    message = str(reader[0]["message"])
    assert "~/.agents/skills/" in message
    assert "Codex" in message


def test_reader_install_is_silent_without_apothem_content(tmp_path: Path) -> None:
    _skill(tmp_path, "someone-elses-skill")
    advisories = shared_root_advisories("cursor", home=tmp_path, project=None)
    assert [a for a in advisories if a["role"] == "reader"] == []


def test_project_anchor_reader_needs_the_managed_block(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    agents = project / "AGENTS.md"
    agents.write_text("# Team instructions\n", encoding="utf-8")
    assert shared_root_advisories("zed", home=tmp_path, project=project) == []

    agents.write_text(
        "<!-- BEGIN APOTHEM MANAGED BLOCK -->\nx\n<!-- END APOTHEM MANAGED BLOCK -->\n",
        encoding="utf-8",
    )
    advisories = shared_root_advisories("zed", home=tmp_path, project=project)
    assert len(advisories) == 1
    assert "Kimi Code" in str(advisories[0]["message"])


def test_project_roots_are_skipped_without_a_project(tmp_path: Path) -> None:
    advisories = shared_root_advisories("kimi-code", home=tmp_path, project=None)
    assert advisories == []


def test_unrelated_harness_gets_no_advisory(tmp_path: Path) -> None:
    _skill(tmp_path, "workflow")
    assert shared_root_advisories("glm", home=tmp_path, project=tmp_path) == []


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    profile = tmp_path / "profile.yaml"
    profile.write_text("identity:\n  name: Test User\n", encoding="utf-8")
    return home, profile


def test_cli_codex_install_lists_the_readers(cli_env: tuple[Path, Path]) -> None:
    _home, profile = cli_env
    runner = CliRunner()
    args = ["install", "--harness", "codex", "--profile", str(profile), "--no-color"]

    plain = runner.invoke(main, args)
    assert plain.exit_code == 0, plain.output
    flat = " ".join(plain.output.split())
    assert "Note: codex - ~/.agents/skills/ is shared" in flat
    assert "Cursor" in flat

    payload = json.loads(runner.invoke(main, [*args, "--format", "json"]).output)
    shared = [w for w in payload["warnings"] if w.get("operation") == "shared_root"]
    assert len(shared) == 1
    assert shared[0]["outcome"] == "advisory"


# --- MCP profile advisories ---------------------------------------------------

_FAKE_GITHUB_TOKEN = "ghp_" + "0123456789abcdefghijABCDEFGHIJ0123"
_FAKE_API_KEY = "sk-" + "abcdefghijklmnopqrstuvwxyz012345"


def _profile(servers: dict[str, object], **extra: object) -> dict[str, object]:
    return {"identity": {"name": "Test User"}, "mcp_servers": servers, **extra}


def _fields(advisories: list[dict[str, object]], operation: str) -> list[object]:
    return [a["field"] for a in advisories if a["operation"] == operation]


def test_sse_transport_gets_a_deprecation_advisory(tmp_path: Path) -> None:
    profile = _profile(
        {"legacy": {"transport": "sse", "url": "https://mcp.example.com/sse"}}
    )
    advisories = mcp_profile_advisories(profile, tmp_path / "profile.yaml")
    assert _fields(advisories, "mcp_deprecated_transport") == [
        "mcp_servers.legacy.transport"
    ]
    entry = advisories[0]
    assert entry["outcome"] == "advisory"
    assert entry["harness"] is None
    assert "streamable-http" in str(entry["message"])


@pytest.mark.parametrize(
    ("url", "warned"),
    [
        ("http://mcp.example.com/mcp", True),
        ("http://10.0.0.5:8080/mcp", True),
        ("https://mcp.example.com/mcp", False),
        ("http://localhost:3000/mcp", False),
        ("http://127.0.0.1:3000/mcp", False),
        ("http://[::1]:3000/mcp", False),
    ],
)
def test_plain_http_to_a_remote_host_gets_an_advisory(
    tmp_path: Path, url: str, warned: bool
) -> None:
    profile = _profile({"api": {"transport": "streamable-http", "url": url}})
    advisories = mcp_profile_advisories(profile, tmp_path / "profile.yaml")
    expected = ["mcp_servers.api.url"] if warned else []
    assert _fields(advisories, "mcp_plain_http") == expected


@pytest.mark.parametrize(
    ("location", "key", "value"),
    [
        ("headers", "Authorization", f"Bearer {_FAKE_GITHUB_TOKEN}"),
        ("headers", "Authorization", "Bearer " + "a1b2c3d4e5f6g7h8i9j0k1l2m3"),
        ("env", "OPENAI_API_KEY", _FAKE_API_KEY),
        ("env", "SLACK_TOKEN", "xoxb-" + "1234567890-abcdefghij"),
        ("env", "GITHUB_TOKEN", _FAKE_GITHUB_TOKEN),
    ],
)
def test_literal_credentials_get_an_advisory_without_echoing_them(
    tmp_path: Path, location: str, key: str, value: str
) -> None:
    server: dict[str, object] = {"transport": "streamable-http"}
    server["url"] = "https://mcp.example.com/mcp"
    server[location] = {key: value}
    advisories = mcp_profile_advisories(_profile({"gh": server}), tmp_path / "p.yaml")
    assert _fields(advisories, "mcp_literal_credential") == [
        f"mcp_servers.gh.{location}.{key}"
    ]
    message = str(advisories[0]["message"])
    assert "${" in message
    assert value.split()[-1] not in json.dumps(advisories)


@pytest.mark.parametrize(
    "value",
    ["Bearer ${GITHUB_TOKEN}", "${OPENAI_API_KEY}", "Bearer short", "application/json"],
)
def test_references_and_ordinary_values_get_no_credential_advisory(
    tmp_path: Path, value: str
) -> None:
    server = {
        "transport": "streamable-http",
        "url": "https://mcp.example.com/mcp",
        "headers": {"Authorization": value},
    }
    advisories = mcp_profile_advisories(_profile({"gh": server}), tmp_path / "p.yaml")
    assert _fields(advisories, "mcp_literal_credential") == []


def test_harness_override_servers_are_checked(tmp_path: Path) -> None:
    profile = _profile(
        {},
        harnesses={
            "qwen-code": {
                "mcp_servers": {
                    "legacy": {"transport": "sse", "url": "http://mcp.example.com"}
                }
            }
        },
    )
    advisories = mcp_profile_advisories(profile, tmp_path / "profile.yaml")
    fields = [a["field"] for a in advisories]
    assert "harnesses.qwen-code.mcp_servers.legacy.transport" in fields
    assert "harnesses.qwen-code.mcp_servers.legacy.url" in fields


def test_cli_install_prints_the_mcp_advisories(cli_env: tuple[Path, Path]) -> None:
    _home, profile = cli_env
    profile.write_text(
        "identity:\n  name: Test User\n"
        "mcp_servers:\n"
        "  gh:\n"
        "    transport: sse\n"
        "    url: https://mcp.example.com/sse\n"
        "    headers:\n"
        f"      Authorization: Bearer {_FAKE_GITHUB_TOKEN}\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        main,
        ["install", "--harness", "qwen-code", "--profile", str(profile), "--no-color"],
    )
    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "mcp_servers.gh.headers.Authorization" in flat
    assert "streamable-http" in flat
    assert _FAKE_GITHUB_TOKEN not in result.output
