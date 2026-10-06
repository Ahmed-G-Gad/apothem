# SPDX-License-Identifier: MIT

"""The engine-installed conformity gate hook starts in the installed layout.

``apothem install --harness claude-code`` copies the gate to
``~/.claude/.apothem/support/conformity/gate.py`` and registers it as a
PreToolUse Write/Edit hook. The installed copy has no ``apothem`` package on
its import path, so the gate used to die with ``ModuleNotFoundError`` on every
Write and the harness treated the hook error as non-blocking: no conformity
check ever ran. This test installs claude-code into an isolated ``HOME``, runs
the registered command exactly as the harness would (no ``PYTHONPATH``), and
expects exit 0 with a JSON report from matchers that loaded without error.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_SECONDS = 300

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="the registered command is resolved for a POSIX HOME layout here",
)


def _engine_env(home: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("CODEX_HOME", "XDG_CONFIG_HOME", "APOTHEM_CONFORMITY_SCOPE")
    }
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return env


def _engine(home: Path, *args: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "apothem", *args],
        env=_engine_env(home),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=TIMEOUT_SECONDS,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.fixture(scope="module")
def installed_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    home = tmp_path_factory.mktemp("isolated-home")
    _engine(home, "profile", "init")
    _engine(home, "install", "--harness", "claude-code")
    return home


def _gate_command(home: Path, matcher: str) -> list[str]:
    settings = json.loads((home / ".claude" / "settings.json").read_text("utf-8"))
    for group in settings["hooks"]["PreToolUse"]:
        if group["matcher"] != matcher:
            continue
        for hook in group["hooks"]:
            args = [str(arg) for arg in hook.get("args", [])]
            if any(arg.endswith("conformity/gate.py") for arg in args):
                return [str(hook["command"]), *args]
    raise AssertionError(f"no gate hook registered for {matcher}")


def _run_hook(
    home: Path, argv: list[str], payload: dict[str, object]
) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in (
            "PYTHONPATH",
            "CODEX_HOME",
            "XDG_CONFIG_HOME",
            "APOTHEM_CONFORMITY_SCOPE",
        )
    }
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    return subprocess.run(
        argv,
        input=json.dumps(payload),
        env=env,
        cwd=str(home),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=TIMEOUT_SECONDS,
    )


@pytest.mark.parametrize("matcher", ["Write", "Edit"])
def test_registered_gate_hook_starts_and_reports(
    installed_home: Path, matcher: str
) -> None:
    """The registered command exits 0 and prints a report from loaded matchers."""
    argv = _gate_command(installed_home, matcher)
    assert argv[1].endswith(".apothem/support/conformity/gate.py")
    target = installed_home / ".claude" / "rules" / "zz-probe.md"
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(target), "content": "# Probe\n\nA body.\n"},
    }

    completed = _run_hook(installed_home, argv, payload)

    assert completed.returncode == 0, completed.stderr
    assert "Traceback" not in completed.stderr
    report = json.loads(completed.stdout)
    assert report["orchestrator"] == "conformity-gate"
    matchers = {inv["grep"] for inv in report["invocations"]}
    assert "file_header_grep" in matchers
    errors = {
        inv["grep"]: inv["error"] for inv in report["invocations"] if inv["error"]
    }
    assert errors == {}


def test_installed_gate_runs_a_standalone_validator(installed_home: Path) -> None:
    """``--check`` on a standalone validator also starts in the installed layout."""
    gate = (
        installed_home / ".claude" / ".apothem" / "support" / "conformity" / "gate.py"
    )
    completed = _run_hook(
        installed_home,
        [
            sys.executable,
            str(gate),
            "--check",
            "no-toplevel-docs-grep",
            str(installed_home),
        ],
        {},
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["inspected"] == 1
