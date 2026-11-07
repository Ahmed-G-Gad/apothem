# SPDX-License-Identifier: MIT

"""Install, update and uninstall leave a user's files in the paths 1.5.0 swept.

Releases 1.0.1 to 1.5.0 removed each path below whole on every install and
update, whatever it held, though no release ever installed a file there
(``~/.claude/commands``, ``~/.codex/rules`` and others). Each test places a
user's file at every such path, runs the adapter's install, update and
uninstall, and checks every file is still there, byte for byte.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class

#: The stale-sweep entries main listed before this change, by public id: the
#: install root they are relative to, and the entries.
_FORMER: dict[str, tuple[str, tuple[str, ...]]] = {
    "claude-code": (
        "~/.claude",
        (
            "src",
            "conformity",
            "schemas",
            "hooks",
            "config",
            "scripts",
            "tools",
            "lib",
            "templates",
            "docs",
            "tests",
            "packaging",
            "mcp",
            "examples",
            "assets",
            "site",
            "public",
            "commands",
            "statuslines/__init__.py",
            "rules/AGENTS.md",
            "skills/AGENTS.md",
            "agents/AGENTS.md",
            "statuslines/AGENTS.md",
            "output-styles/AGENTS.md",
        ),
    ),
    "codex": (
        "~/.codex",
        (
            "../.config/apothem/hooks",
            "../.agents/skills/AGENTS.md",
            "rules",
            "commands",
        ),
    ),
    "gemini-cli": (
        "project",
        (
            "skills/AGENTS.md",
            ".gemini/apothem/templates",
            ".gemini/apothem/hooks",
            ".gemini/apothem/rules",
        ),
    ),
    "opencode": ("~/.config/opencode", ("apothem/templates", "apothem/hooks")),
    "qwen-code": (
        "~/.qwen",
        ("skills/AGENTS.md", "apothem/templates", "apothem/hooks"),
    ),
    "hermes": (
        "~/.hermes",
        (
            "cli-config.yaml",
            "profile.yaml",
            "apothem/templates",
            "apothem/hooks",
            "apothem/skills",
            "apothem/agents",
        ),
    ),
    "open-claw": (
        "~/.openclaw",
        (
            "../.open-claw/config.yaml",
            "apothem/templates",
            "apothem/hooks",
            "apothem/skills",
            "apothem/agents",
        ),
    ),
    "kimi-code": (
        "project",
        (
            ".kimi-code/apothem/skills/AGENTS.md",
            ".kimi-code/apothem/templates",
            ".kimi-code/apothem/hooks",
            ".kimi-code/apothem/rules",
            ".kimi-code/apothem/skills",
            ".kimi-code/apothem/agents",
        ),
    ),
}

_FILE_SUFFIXES = (".py", ".md", ".yaml")

#: Paths in a folder Apothem owns whose name its source tree also carries:
#: uninstall removes such a name from ~/.claude/statuslines/, as it removes
#: render.py there. It is not the sweep, and install and update keep the file.
_UNINSTALL_OWNS = frozenset({Path("statuslines/__init__.py")})


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    for name in ("CODEX_HOME", "XDG_CONFIG_HOME", "OPENCODE_CONFIG_DIR"):
        monkeypatch.delenv(name, raising=False)
    return folder


def _plant(root: Path, entries: tuple[str, ...]) -> dict[Path, bytes]:
    """Put a user's file at or inside each former entry; return what was written."""
    planted: dict[Path, bytes] = {}
    for entry in entries:
        target = root / entry
        if not target.name.endswith(_FILE_SUFFIXES):
            target = target / "mine.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        body = f"a user's own file at {entry}\n".encode()
        target.write_bytes(body)
        planted[target] = body
    return planted


def _runner(public_id: str, project: Path) -> tuple[Callable[[str], object], bool]:
    adapter = load_adapter_class(get_harness_entry(public_id))()
    scoped = _FORMER[public_id][0] == "project"

    def run(action: str) -> object:
        method = getattr(adapter, action)
        if action == "uninstall":
            return method(project=project) if scoped else method()
        return method({}, project=project) if scoped else method({})

    return run, scoped


@pytest.mark.parametrize("public_id", sorted(_FORMER))
def test_a_users_files_in_formerly_swept_paths_survive(
    public_id: str, home: Path, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    base, entries = _FORMER[public_id]
    root = project if base == "project" else home / base.removeprefix("~/")
    planted = _plant(root, entries)
    run, _scoped = _runner(public_id, project)

    for action in ("install", "update", "uninstall"):
        run(action)
        for path, body in planted.items():
            if action == "uninstall" and path.relative_to(root) in _UNINSTALL_OWNS:
                continue
            assert path.read_bytes() == body, f"{action} changed {path}"


def test_no_stale_sweep_entry_names_a_folder_a_user_or_tool_writes() -> None:
    # The sweep removes a listed path whole, so only Apothem's own namespace may
    # be listed: a path inside an apothem folder, or Kimi Code's .apothem tree.
    for name in (
        "claude_code",
        "codex",
        "gemini_cli",
        "opencode",
        "qwen_code",
        "hermes",
        "open_claw",
        "kimi_code",
    ):
        for entry in install_driver.load_rules(name).stale_sweep:
            parts = Path(entry).parts
            assert "apothem" in parts or ".apothem" in parts, (name, entry)
