# SPDX-License-Identifier: MIT

"""Run every documented install channel the way an anonymous new user would.

Why this check exists. The README and the install pages promise eight install
channels. Nothing checked that a person without access to this repository can
follow them: a private repository, an unpublished listing, or a missing signing
key each turns a documented command into a failure that only a new user sees.
This driver runs each channel's documented commands in an isolated home
directory, with credentials removed from the environment and Git prompts
disabled, and reports which channels work.

What a channel runs. Each channel lists the commands exactly as the README
prints them (``documented``), so ``tests/scripts/test_channel_smoke.py`` can
assert the two stay in step. The driver runs the CLI equivalent where the
README shows an in-app slash command (the Claude Code plugin channel) and adds
the flag a non-interactive run needs where the tool would otherwise prompt
(``--consent``, ``-y``). Those adaptations are listed per channel in ``steps``.

What it does not do. It never uses a token, never writes outside its own
temporary directory, and never sends telemetry. The harness CLIs and runtimes a
channel names as prerequisites must already be on ``PATH``; a missing one is
reported as a failure, not skipped, unless ``--allow-missing-tools`` is passed
for a local run.

Usage::

    python scripts/dev/channel_smoke.py --list            # channel ids as JSON
    python scripts/dev/channel_smoke.py --channel npm     # run one channel
    python scripts/dev/channel_smoke.py --all             # run every channel

Exit status: 0 when every selected channel passes, 1 when any fails, 3 on a
usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = "ahmed-g-gad/apothem"
REPO_URL = f"https://github.com/{REPO}"
SITE = "https://apothem.ahmedgad.com"
STEP_TIMEOUT_SECONDS = 900
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 3

#: Environment variable names that can carry a credential. The driver removes
#: every match so a run proves the channel works anonymously.
_CREDENTIAL_NAME = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|APIKEY|AUTH|CREDENTIAL|_KEY$)",
    re.IGNORECASE,
)
_CREDENTIAL_EXACT = frozenset(
    {"GH_HOST", "GITHUB_ACTOR", "NPM_CONFIG_USERCONFIG", "NODE_AUTH_TOKEN"}
)


@dataclass(frozen=True)
class Step:
    """One command a channel runs.

    ``argv`` is executed directly unless ``interpreter`` names a shell, in
    which case ``argv[0]`` is the documented command line passed to it. ``cwd`` is relative to
    the channel's working directory.
    """

    argv: tuple[str, ...]
    interpreter: str | None = None
    cwd: str = "."


@dataclass(frozen=True)
class Channel:
    """A documented install channel and the commands that prove it works."""

    id: str
    title: str
    documented: tuple[str, ...]
    requires: tuple[str, ...]
    steps: tuple[Step, ...]
    runner: str = "ubuntu-latest"
    notes: tuple[str, ...] = field(default_factory=tuple)


def _npx(*args: str) -> Step:
    return Step(("npx", "@ahmed-g-gad/apothem", *args))


CHANNELS: tuple[Channel, ...] = (
    Channel(
        id="claude-code-plugin",
        title="1 — Claude Code plugin",
        documented=(
            f"/plugin marketplace add {REPO}",
            "/plugin install apothem@apothem",
        ),
        requires=("claude",),
        steps=(
            Step(("claude", "plugin", "marketplace", "add", REPO)),
            Step(
                (
                    "claude",
                    "plugin",
                    "install",
                    "apothem@apothem",
                    "--scope",
                    "user",
                    "-y",
                )
            ),
        ),
        notes=("Runs the CLI form of the in-app /plugin commands.",),
    ),
    Channel(
        id="npm",
        title="2 — npm shim (npx)",
        documented=(
            "npx @ahmed-g-gad/apothem quickstart --yes",
            "npx @ahmed-g-gad/apothem verify --harness claude-code",
            "npx @ahmed-g-gad/apothem --version",
        ),
        requires=("npx", "python3"),
        steps=(
            _npx("--version"),
            _npx("quickstart", "--yes"),
            _npx("verify", "--harness", "claude-code"),
        ),
    ),
    Channel(
        id="npm-github",
        title="2 — npm shim from GitHub",
        documented=(f"npx github:{REPO} install --harness claude-code",),
        requires=("npx", "python3", "git"),
        steps=(Step(("npx", f"github:{REPO}", "--version")),),
    ),
    Channel(
        id="installer-posix",
        title="3 — one-shot installer (POSIX)",
        documented=(f"curl -fsSL {SITE}/install.sh | sh",),
        requires=("curl", "sh", "git", "python3"),
        steps=(Step((f"curl -fsSL {SITE}/install.sh | sh",), interpreter="sh"),),
    ),
    Channel(
        id="installer-windows",
        title="3 — one-shot installer (Windows)",
        documented=(f"irm {SITE}/install.ps1 | iex",),
        requires=("pwsh", "git"),
        steps=(Step((f"irm {SITE}/install.ps1 | iex",), interpreter="pwsh"),),
        runner="windows-latest",
    ),
    Channel(
        id="vscode-extension",
        title="4 — VS Code family extension",
        documented=("code --install-extension apothem.vsix",),
        requires=("curl", "code"),
        steps=(
            Step(
                (
                    "curl",
                    "-fsSL",
                    "-o",
                    "apothem.vsix",
                    f"{REPO_URL}/releases/latest/download/apothem.vsix",
                )
            ),
            Step(("code", "--install-extension", "apothem.vsix")),
        ),
        notes=("Downloads the .vsix the README says each release attaches.",),
    ),
    Channel(
        id="gemini-cli-extension",
        title="5 — Gemini CLI extension",
        documented=(
            f"gemini extensions install {REPO_URL}",
            "npx @ahmed-g-gad/apothem install --harness gemini-cli --project .",
            "npx @ahmed-g-gad/apothem verify --harness gemini-cli --project .",
        ),
        requires=("gemini", "npx", "python3"),
        steps=(
            Step(("gemini", "extensions", "install", REPO_URL, "--consent")),
            _npx("install", "--harness", "gemini-cli", "--project", "."),
            _npx("verify", "--harness", "gemini-cli", "--project", "."),
        ),
        notes=("Adds --consent, which skips the interactive confirmation.",),
    ),
    Channel(
        id="qwen-code-extension",
        title="6 — Qwen Code extension",
        documented=(
            f"qwen extensions install {REPO}",
            "npx @ahmed-g-gad/apothem install --harness qwen-code",
            "npx @ahmed-g-gad/apothem verify --harness qwen-code",
        ),
        requires=("qwen", "npx", "python3"),
        steps=(
            Step(("qwen", "extensions", "install", f"{REPO}:apothem", "--consent")),
            _npx("install", "--harness", "qwen-code"),
            _npx("verify", "--harness", "qwen-code"),
        ),
        notes=(
            "Adds --consent, which skips the interactive confirmation.",
            "Names the plugin (`:apothem`): the repository is also a Claude Code"
            " marketplace, so Qwen Code otherwise asks which plugin to install.",
        ),
    ),
    Channel(
        id="codex-plugin",
        title="7 — Codex plugin",
        documented=(
            f"codex plugin marketplace add {REPO}",
            "codex plugin add apothem@apothem",
            "npx @ahmed-g-gad/apothem install --harness codex",
            "npx @ahmed-g-gad/apothem verify --harness codex",
        ),
        requires=("codex", "npx", "python3"),
        steps=(
            Step(("codex", "plugin", "marketplace", "add", REPO)),
            Step(("codex", "plugin", "add", "apothem@apothem")),
            _npx("install", "--harness", "codex"),
            _npx("verify", "--harness", "codex"),
        ),
    ),
    Channel(
        id="direct-engine",
        title="8 — direct engine (python -m apothem)",
        documented=(
            f"git clone {REPO_URL}",
            "PYTHONPATH=src python -m apothem install --harness claude-code",
            "PYTHONPATH=src python -m apothem verify --harness claude-code",
        ),
        requires=("git", "python"),
        steps=(
            Step(("git", "clone", "--depth", "1", REPO_URL, "apothem")),
            Step(
                ("PYTHONPATH=src python -m apothem install --harness claude-code",),
                interpreter="sh",
                cwd="apothem",
            ),
            Step(
                ("PYTHONPATH=src python -m apothem verify --harness claude-code",),
                interpreter="sh",
                cwd="apothem",
            ),
        ),
        notes=("Needs the documented click and rich prerequisites.",),
    ),
)


def channel_ids() -> list[str]:
    """Return every channel id in documentation order."""
    return [channel.id for channel in CHANNELS]


def anonymous_env(home: Path) -> dict[str, str]:
    """Return an environment with credentials removed and ``HOME`` isolated.

    Git is pointed at an empty global config so no credential helper, URL
    rewrite, or stored token from the host applies, and its terminal prompt is
    disabled so a private source fails at once instead of waiting for input.
    """
    env = {
        name: value
        for name, value in os.environ.items()
        if not _CREDENTIAL_NAME.search(name) and name not in _CREDENTIAL_EXACT
    }
    git_config = home / ".gitconfig-empty"
    git_config.parent.mkdir(parents=True, exist_ok=True)
    git_config.write_text("", encoding="utf-8")
    # Codex refuses a CODEX_HOME that does not exist yet.
    for tool_home in (".claude", ".codex"):
        (home / tool_home).mkdir(exist_ok=True)
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            "CODEX_HOME": str(home / ".codex"),
            "GIT_CONFIG_GLOBAL": str(git_config),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
            "npm_config_yes": "true",
            "npm_config_userconfig": str(home / ".npmrc"),
            "NO_COLOR": "1",
        }
    )
    return env


def missing_tools(channel: Channel) -> list[str]:
    """Return the prerequisite commands a channel names that are not on PATH."""
    return [tool for tool in channel.requires if shutil.which(tool) is None]


def _command(step: Step) -> list[str]:
    if step.interpreter == "sh":
        return ["sh", "-c", step.argv[0]]
    if step.interpreter == "pwsh":
        return ["pwsh", "-NoProfile", "-NonInteractive", "-Command", step.argv[0]]
    return list(step.argv)


def _display(step: Step) -> str:
    return step.argv[0] if step.interpreter else " ".join(step.argv)


def run_channel(
    channel: Channel, *, allow_missing_tools: bool = False
) -> dict[str, object]:
    """Run one channel in a fresh temporary home and return its result record."""
    record: dict[str, object] = {"channel": channel.id, "title": channel.title}
    absent = missing_tools(channel)
    if absent:
        record["status"] = "skipped" if allow_missing_tools else "failed"
        record["reason"] = "prerequisite not on PATH: " + ", ".join(absent)
        record["steps"] = []
        return record
    steps: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix=f"channel-{channel.id}-") as tmp:
        root = Path(tmp)
        home = root / "home"
        work = root / "work"
        home.mkdir()
        work.mkdir()
        env = anonymous_env(home)
        for step in channel.steps:
            cwd = work / step.cwd
            try:
                done = subprocess.run(  # noqa: S603 - argv is a fixed table above
                    _command(step),
                    cwd=cwd,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=STEP_TIMEOUT_SECONDS,
                    check=False,
                )
                code, tail = done.returncode, (done.stdout + done.stderr)[-2000:]
            except (OSError, subprocess.TimeoutExpired) as exc:
                code, tail = -1, f"{type(exc).__name__}: {exc}"
            steps.append({"command": _display(step), "exit": code, "output_tail": tail})
            if code != 0:
                break
    record["steps"] = steps
    completed = len(steps) == len(channel.steps) and all(s["exit"] == 0 for s in steps)
    record["status"] = "passed" if completed else "failed"
    return record


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the selected channels, and print a JSON report."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="print channel ids as JSON")
    group.add_argument(
        "--channel", action="append", help="run this channel (repeatable)"
    )
    group.add_argument("--all", action="store_true", help="run every channel")
    parser.add_argument(
        "--runner",
        help="with --list, print only the channels that run on this runner label",
    )
    parser.add_argument(
        "--allow-missing-tools",
        action="store_true",
        help="report a channel whose prerequisites are missing as skipped",
    )
    args = parser.parse_args(argv)

    if args.list:
        chosen = [c for c in CHANNELS if args.runner in (None, c.runner)]
        print(json.dumps([c.id for c in chosen]))
        return EXIT_OK

    selected = list(CHANNELS) if args.all else []
    for wanted in args.channel or []:
        match = [c for c in CHANNELS if c.id == wanted]
        if not match:
            print(
                f"unknown channel: {wanted}; known: {', '.join(channel_ids())}",
                file=sys.stderr,
            )
            return EXIT_USAGE
        selected.extend(match)

    results = [
        run_channel(channel, allow_missing_tools=args.allow_missing_tools)
        for channel in selected
    ]
    print(json.dumps(results, indent=2))
    failed = [r["channel"] for r in results if r["status"] == "failed"]
    for result in results:
        print(f"{result['status']:>8}  {result['channel']}", file=sys.stderr)
    return EXIT_FAIL if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
