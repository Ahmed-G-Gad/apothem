# SPDX-License-Identifier: MIT

"""Tests for ``scripts/dev/channel_smoke.py``, the anonymous install-channel smoke.

The driver is only useful while its commands match what the README tells a new
user to run, so the first group of tests holds the two in step. The rest pin
the properties that make a passing run meaningful: credentials never reach a
step, Git cannot prompt, a missing prerequisite fails rather than silently
skips, and a failing step stops its channel.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import channel_smoke as smoke  # noqa: E402

_README = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
_WORKFLOW = (_REPO_ROOT / ".github" / "workflows" / "channel-smoke.yml").read_text(
    encoding="utf-8"
)


@pytest.mark.parametrize("channel", smoke.CHANNELS, ids=lambda c: c.id)
def test_documented_commands_appear_in_the_readme(channel: smoke.Channel) -> None:
    """Every command a channel claims is documented is in the README verbatim."""
    for command in channel.documented:
        assert command in _README, f"{channel.id}: README no longer shows {command!r}"


def test_every_numbered_readme_channel_is_smoked() -> None:
    """Each numbered install channel in the README has at least one smoke channel."""
    numbers = set(re.findall(r"^### (\d+) — ", _README, flags=re.MULTILINE))
    assert numbers, "the README must number its install channels"
    covered = {channel.title.split(" ", 1)[0] for channel in smoke.CHANNELS}
    assert numbers <= covered, f"unsmoked channels: {sorted(numbers - covered)}"


def test_channel_ids_are_unique() -> None:
    ids = smoke.channel_ids()
    assert len(ids) == len(set(ids))


def test_anonymous_env_strips_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "NPM_TOKEN",
        "NODE_AUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
    ):
        monkeypatch.setenv(name, "secret-value")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = smoke.anonymous_env(tmp_path)
    assert "secret-value" not in env.values()
    assert env["PATH"] == "/usr/bin"
    assert env["HOME"] == str(tmp_path)
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert Path(env["GIT_CONFIG_GLOBAL"]).read_text(encoding="utf-8") == ""
    assert Path(env["CODEX_HOME"]).is_dir()
    assert Path(env["CLAUDE_CONFIG_DIR"]).is_dir()


def test_list_prints_ids_and_filters_by_runner(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert smoke.main(["--list"]) == smoke.EXIT_OK
    assert json.loads(capsys.readouterr().out) == smoke.channel_ids()
    assert smoke.main(["--list", "--runner", "windows-latest"]) == smoke.EXIT_OK
    windows = json.loads(capsys.readouterr().out)
    assert windows == ["installer-windows"]


def test_unknown_channel_is_a_usage_error() -> None:
    assert smoke.main(["--channel", "no-such-channel"]) == smoke.EXIT_USAGE


def _fake(*steps: smoke.Step, requires: tuple[str, ...] = ()) -> smoke.Channel:
    return smoke.Channel(
        id="fake", title="0 — fake", documented=(), requires=requires, steps=steps
    )


def test_missing_prerequisite_fails_unless_allowed() -> None:
    channel = _fake(requires=("apothem-no-such-tool",))
    assert smoke.run_channel(channel)["status"] == "failed"
    assert smoke.run_channel(channel, allow_missing_tools=True)["status"] == "skipped"


def test_passing_steps_pass() -> None:
    ok = smoke.Step((sys.executable, "-c", "print('ok')"))
    record = smoke.run_channel(_fake(ok, ok))
    assert record["status"] == "passed"
    assert [step["exit"] for step in record["steps"]] == [0, 0]  # type: ignore[union-attr]


def test_a_failing_step_stops_the_channel() -> None:
    fail = smoke.Step((sys.executable, "-c", "raise SystemExit(4)"))
    ok = smoke.Step((sys.executable, "-c", "print('ok')"))
    record = smoke.run_channel(_fake(fail, ok))
    assert record["status"] == "failed"
    assert [step["exit"] for step in record["steps"]] == [4]  # type: ignore[union-attr]


def test_steps_do_not_see_host_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "secret-value")
    probe = smoke.Step(
        (
            sys.executable,
            "-c",
            "import os, sys; sys.exit(1 if 'GITHUB_TOKEN' in os.environ else 0)",
        )
    )
    assert smoke.run_channel(_fake(probe))["status"] == "passed"


def test_workflow_runs_every_channel_without_secrets() -> None:
    """The workflow builds its matrix from the driver and grants no secret."""
    assert "permissions: {}" in _WORKFLOW
    assert "secrets." not in _WORKFLOW
    assert "channel_smoke.py --list --runner ubuntu-latest" in _WORKFLOW
    assert "channel_smoke.py --list --runner windows-latest" in _WORKFLOW
    assert "persist-credentials: false" in _WORKFLOW
    runners = {channel.runner for channel in smoke.CHANNELS}
    assert runners == {"ubuntu-latest", "windows-latest"}
