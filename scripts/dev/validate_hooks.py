# SPDX-License-Identifier: MIT

"""Hook infrastructure validator for the apothem ecosystem.

Validates:

* Presence and JSON-validity of the Claude Code ``settings.json`` template.
* Required hook events declared for each runtime.
* Presence of the Python hook scripts (``dispatch.py``,
  ``emit_hook_context.py``, ``session_start_bootstrap.py``) and their
  import-time syntactic validity.
* Presence of hook message files.
* Absence of hardcoded absolute user paths.
* Core artifact counts (rules / commands / agents).

Exits 0 when no FAIL outcomes occur, 1 otherwise.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Final

_HOOKS_LIB: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent / "src" / "apothem" / "hooks" / "lib"
)
if str(_HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(_HOOKS_LIB))

_LIB_DIR: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent / "src" / "apothem" / "lib"
)
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from reporter import Reporter  # noqa: E402
from resolve_root import (  # noqa: E402
    Mode,
    default_content_root,
    resolve_project_root,
)

_REQUIRED_EVENTS: Final[tuple[str, ...]] = (
    "SessionStart",
    "PreToolUse",
    "PreCompact",
    "PostCompact",
    "Stop",
)

_PYTHON_SCRIPTS: Final[tuple[str, ...]] = (
    "dispatch.py",
    "emit_hook_context.py",
    "session_start_bootstrap.py",
)

_MESSAGE_FILES: Final[tuple[str, ...]] = (
    "pretooluse-write.md",
    "pretooluse-edit.md",
    "pretooluse-notebookedit.md",
    "pretooluse-bash.md",
    "precompact.md",
    "postcompact.md",
    "stop.md",
)

# Absolute home-directory roots, across the platforms a hook script may be
# authored on. The original pattern was Windows-backslash only, so a script
# carrying `/home/someone/...` passed and the validator reported "No hardcoded
# absolute paths" — an affirmative clean bill for the majority platform.
#
# The separator repeats (`[\\/]+`) because a Windows path in Python source is
# normally written escaped — `"C:\\Users\\me"` is two backslash characters on
# disk, which a single-separator pattern reads straight past. Both the escaped
# and the raw-string form have to match.
_HARDCODED_USER_PATTERN: Final[str] = (
    r"(?:[C-Z]:[\\/]+Users[\\/]+|/home/[^/\s\"']+|/Users/[^/\s\"']+|/root/)"
)


def validate_settings_file(path: Path, label: str, reporter: Reporter) -> None:
    """Validate a single settings JSON file."""
    if not path.is_file():
        reporter.fail(f"{label} not found")
        return

    reporter.ok(f"{label} exists")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        reporter.fail(f"{label} JSON error: {exc}")
        return

    reporter.ok(f"{label} is valid JSON")

    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        reporter.warn(f"{label} has no hooks property")
        return

    for event in _REQUIRED_EVENTS:
        if event in hooks:
            reporter.ok(f"{label}: hook defined: {event}")
        else:
            reporter.warn(f"{label}: hook missing: {event}")

    validate_hook_command_shape(hooks, label, reporter)


def _iter_hook_commands(hooks: dict[str, object]) -> list[str]:
    """Return every ``command`` string across every hook entry in *hooks*."""
    commands: list[str] = []
    for entries in hooks.values():
        if not isinstance(entries, list):
            continue
        for matcher_block in entries:
            if not isinstance(matcher_block, dict):
                continue
            inner = matcher_block.get("hooks")
            if not isinstance(inner, list):
                continue
            for hook in inner:
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    commands.append(hook["command"])
    return commands


def validate_hook_command_shape(
    hooks: dict[str, object], label: str, reporter: Reporter
) -> None:
    """Assert the actual hook ``command`` shape — never a bare ``python``.

    The shipped ``settings.json`` (template / native-install example) carries
    the ``${PYTHON_BIN}`` placeholder on every hook ``command``; the
    ``claude_code`` adapter resolves it to an absolute CPython >= 3.10 path at
    install time. The validated entry shape is therefore: every ``command`` is
    either the ``${PYTHON_BIN}`` placeholder (un-rendered template) or an
    absolute interpreter path — never the bare name ``python`` (which a host
    PATH can resolve to a Microsoft Store WindowsApps launcher stub) and never
    the legacy bootstrap-stub entry shape.
    """
    commands = _iter_hook_commands(hooks)
    if not commands:
        reporter.warn(f"{label}: no hook commands found to validate")
        return
    bare = [cmd for cmd in commands if cmd in {"python", "python3"}]
    if bare:
        reporter.fail(
            f"{label}: {len(bare)} hook command(s) invoke a bare interpreter "
            "name (PATH may resolve it to a WindowsApps stub)"
        )
        return
    placeholder_or_absolute = all(
        cmd == "${PYTHON_BIN}" or Path(cmd).is_absolute() for cmd in commands
    )
    if placeholder_or_absolute:
        reporter.ok(
            f"{label}: every hook command is ${{PYTHON_BIN}} or an absolute "
            "interpreter path (no bare python)"
        )
    else:
        reporter.fail(
            f"{label}: a hook command is neither ${{PYTHON_BIN}} nor an "
            "absolute interpreter path"
        )


def validate_python_scripts(hooks_dir: Path, reporter: Reporter) -> None:
    """Verify each required Python hook script exists and parses."""
    for name in _PYTHON_SCRIPTS:
        path = hooks_dir / name
        if not path.is_file():
            reporter.fail(f"Missing hook script: {name}")
            continue
        reporter.ok(f"Hook script present: {name}")
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            reporter.ok(f"  syntax valid: {name}")
        except SyntaxError as exc:
            reporter.fail(f"  syntax error in {name}: {exc}")


def validate_messages(messages_dir: Path, reporter: Reporter) -> None:
    """Verify every referenced hook message file exists."""
    for name in _MESSAGE_FILES:
        if (messages_dir / name).is_file():
            reporter.ok(f"Hook message: {name}")
        else:
            reporter.warn(f"Hook message missing: {name}")


def validate_no_hardcoded_paths(hooks_dir: Path, reporter: Reporter) -> None:
    """Scan every `.py` file under hooks_dir for absolute user paths."""
    import re

    pattern = re.compile(_HARDCODED_USER_PATTERN)
    offenders: list[str] = []
    for path in hooks_dir.rglob("*.py"):
        try:
            if pattern.search(path.read_text(encoding="utf-8", errors="replace")):
                offenders.append(path.name)
        except OSError:
            continue
    if offenders:
        for name in offenders:
            reporter.fail(f"Hardcoded absolute path in {name}")
    else:
        reporter.ok("No hardcoded absolute paths in Python hook scripts")


def validate_python_hygiene(content_root: Path, reporter: Reporter) -> None:
    """Confirm shell files under ``hooks/`` are limited to approved stubs.

    The approved surface is the interpreter locators
    (``find-python.{ps1,sh}``, ``find-pwsh.{ps1,sh}``) plus the
    hook-bootstrap wrappers (``bootstrap.{ps1,sh}``). The bootstrap stubs
    are the documented shell path that locates an interpreter and execs the
    dispatcher; the shipped ``settings.json`` hook entries do not invoke them
    as the entry point — each entry's ``command`` is an install-resolved
    absolute CPython path (the ``${PYTHON_BIN}`` placeholder substituted at
    install time), invoking ``dispatch.py`` directly. Every other ``.ps1`` or
    ``.sh`` file under ``hooks/`` is treated as rogue shell logic and causes
    a FAIL.
    """
    allowed_shell = {
        "find-python.ps1",
        "find-python.sh",
        "find-pwsh.ps1",
        "find-pwsh.sh",
        "bootstrap.ps1",
        "bootstrap.sh",
    }
    hooks_dir = content_root / "hooks"
    rogue: list[str] = []
    if hooks_dir.is_dir():
        for ext in ("*.ps1", "*.sh"):
            for path in hooks_dir.rglob(ext):
                if path.name in allowed_shell:
                    continue
                rogue.append(str(path.relative_to(content_root)))
    if rogue:
        for name in rogue:
            reporter.fail(f"Unexpected shell artifact: {name}")
    else:
        reporter.ok("Python hygiene: only approved locator and bootstrap stubs present")


def validate_artifact_counts(root: Path, reporter: Reporter) -> None:
    """Report counts for rules / commands / agents with minimum thresholds."""
    counts = {
        "Rules": sum(1 for _ in (root / "rules").glob("*.md"))
        if (root / "rules").is_dir()
        else 0,
        "Commands": sum(1 for _ in (root / "commands").glob("*.md"))
        if (root / "commands").is_dir()
        else 0,
        "Agents": sum(1 for _ in (root / "agents").glob("*.md"))
        if (root / "agents").is_dir()
        else 0,
    }
    minimums = {"Rules": 10, "Commands": 5, "Agents": 4}
    for name, count in counts.items():
        reporter.info(f"{name}: {count}")
        if count >= minimums[name]:
            reporter.ok(f"{name} count sufficient")
        else:
            reporter.warn(f"{name} count below recommended {minimums[name]}")


def run(root: Path, reporter: Reporter, content_root: Path | None = None) -> None:
    """Execute every validation stage in order."""
    cr = content_root if content_root is not None else root
    reporter.info(f"Root: {root}")
    if cr != root:
        reporter.info(f"Content-root: {cr}")

    # Harness-native settings projection lives in the per-harness
    # native-install example tree, not at repo root `.claude/`.
    _native_install = root / "examples" / "harnesses" / "claude-code" / "native-install"

    reporter.section("settings.json")
    validate_settings_file(_native_install / "settings.json", "settings.json", reporter)

    reporter.section("Hook Scripts")
    validate_python_scripts(cr / "hooks", reporter)

    reporter.section("Hook Messages")
    validate_messages(cr / "hooks" / "messages", reporter)

    reporter.section("Path Hygiene")
    validate_no_hardcoded_paths(cr / "hooks", reporter)
    validate_python_hygiene(cr, reporter)

    reporter.section("Artifact Counts")
    validate_artifact_counts(cr, reporter)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(prog="validate_hooks")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--content-root",
        type=Path,
        default=None,
        help=(
            "Directory where hook scripts and messages live (hooks/ subdir). "
            "Defaults to --root. Use src/apothem when running against the "
            "apothem source repository."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success, 1 on any FAIL."""
    args = parse_args(argv)
    root = args.root or resolve_project_root(Mode.MARKER, script_path=Path(__file__))
    if root is None:
        print("[FAIL] Cannot resolve apothem ecosystem root")
        return 1

    content_root = args.content_root or default_content_root(root)

    reporter = Reporter()
    run(root, reporter, content_root=content_root)
    reporter.summary()
    return reporter.exit_code


if __name__ == "__main__":
    sys.exit(main())
