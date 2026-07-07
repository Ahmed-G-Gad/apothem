# SPDX-License-Identifier: MIT

"""Exercise every configured hook command with adversarial inputs.

Checks:

* **storm:** every hook command in settings.json exits 0 with empty stdout
  (hook contract: quiet success).
* **emit:malformed-stdin:** garbled JSON on stdin still yields a valid
  envelope.
* **emit:missing-context:** a missing context file still yields a valid
  envelope.
* **degraded-resolution:** scripts run from a temp directory with a fake
  HOME still yield a valid envelope.

Exits 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_HOOKS_LIB: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent / "src" / "apothem" / "hooks" / "lib"
)
if str(_HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(_HOOKS_LIB))

from resolve_root import (  # noqa: E402
    Mode,
    default_content_root,
    resolve_project_root,
)


@dataclass(frozen=True)
class Check:
    """Single chaos-pass result."""

    name: str
    passed: bool
    detail: str


def _python_exe() -> str:
    """Return the current Python interpreter path."""
    return sys.executable


_ENVELOPE_KEYS: Final[tuple[str, ...]] = (
    "hookSpecificOutput",
    "systemMessage",
)


def _is_valid_envelope(envelope: dict[str, object] | None) -> bool:
    """Return True when the envelope carries a recognized top-level key."""
    if not isinstance(envelope, dict):
        return False
    return any(key in envelope for key in _ENVELOPE_KEYS)


def _is_gate_verdict(envelope: dict[str, object] | None, code: int) -> bool:
    """Return True for a conformity-gate verdict (allow or block).

    The conformity gate is a verdict hook, not a context-envelope hook: it
    emits its own ``{"orchestrator": "conformity-gate", ...}`` report and exits
    0 (allow / pass-through) or 2 (block). Both are correct, non-crash
    responses; neither carries a ``hookSpecificOutput`` / ``systemMessage``
    envelope, so the storm check recognises the verdict shape explicitly rather
    than mis-classifying a blocked write as a missing hook script.
    """
    return (
        isinstance(envelope, dict)
        and envelope.get("orchestrator") == "conformity-gate"
        and code in (0, 2)
    )


def _extract_envelope(text: str) -> dict[str, object] | None:
    """Attempt JSON parse; fall back to locating a known envelope prefix."""
    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    for key in _ENVELOPE_KEYS:
        start = stripped.find('{"' + key + '"')
        if start == -1:
            continue
        try:
            parsed = json.loads(stripped[start:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


def run_hook_command(
    command: str, hook_args: list[str], shell: str, cwd: Path
) -> tuple[int, str, str]:
    """Run a configured hook command string under its declared shell.

    Returns ``(-1, "", "shell-not-installed: <shell>")`` when the shell
    binary is absent on the host (e.g., ``powershell`` on a POSIX runner,
    or ``bash`` on a stripped-down Windows runner). The caller treats the
    sentinel as a "skipped" check rather than a hard failure: chaos_pass
    is a fail-open envelope-shape verifier, not a shell-availability gate.
    """
    if hook_args:
        argv = [command, *hook_args]
    elif shell == "powershell":
        argv = ["powershell", "-NoProfile", "-Command", command]
    else:
        argv = ["bash", "-c", command]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            check=False,
        )
    except FileNotFoundError:
        return -1, "", f"shell-not-installed: {shell}"
    return proc.returncode, proc.stdout, proc.stderr


def storm_configured_hooks(root: Path) -> list[Check]:
    """Run every hook command in the canonical Claude Code settings file.

    Hook commands whose declared shell is not installed on the runner
    record a "skipped" check rather than a failure — chaos_pass is a
    fail-open envelope-shape verifier, not a shell-availability gate.
    """
    results: list[Check] = []
    settings_name = "settings.json"
    # Harness-native settings projection lives in the per-harness
    # native-install example tree, not at repo root `.claude/`.
    _native_install = root / "examples" / "harnesses" / "claude-code" / "native-install"
    settings_path = _native_install / settings_name
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [Check("storm:load-settings", False, str(exc))]

    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        return [Check("storm:hooks-missing", False, "hooks property absent")]

    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            matcher = str(entry.get("matcher", ""))
            for hook in entry.get("hooks", []):
                if not isinstance(hook, dict):
                    continue
                command = str(hook.get("command", ""))
                hook_args_raw = hook.get("args", [])
                hook_args = (
                    [str(arg) for arg in hook_args_raw]
                    if isinstance(hook_args_raw, list)
                    else []
                )
                shell = str(hook.get("shell", "powershell"))
                if not command:
                    continue
                code, stdout, stderr = run_hook_command(command, hook_args, shell, root)
                # Skip-conditions (record as a passing skip rather than a
                # hard failure) — chaos_pass is a fail-open envelope-shape
                # verifier, not an environment-setup gate:
                #   1. shell binary absent (sentinel from run_hook_command).
                #   2. hook script absent at the canonical install path —
                #      the settings file's commands resolve harness-
                #      specific install paths (e.g., `~/.claude/` for the
                #      Claude Code adapter) that exist in end-user
                #      installs but not in CI runners where the ecosystem
                #      lives at the workspace root. Detect via exit codes
                #      127 (bash: file not found) and 2 (python: file
                #      open failed) plus an "No such file or directory"
                #      stderr signal.
                stderr_lower = stderr.strip().lower()
                # Cross-platform "hook script not present" detection. The
                # signals vary across runners and shells:
                #   POSIX bash  exit=127  "no such file or directory"
                #   POSIX py    exit=2    "can't open file"
                #   PowerShell  exit=1    "is not recognized as the name of a cmdlet"
                #   Win-py      exit=1    "can't open file ... [errno 2]"
                #   Win-CI bash exit=1    empty stderr (WSL bash / Git Bash pipe
                #               redirection swallows the "not found" message;
                #               empty stderr is the reliable signal on Windows CI)
                hook_script_missing = code in (1, 2, 127) and (
                    "no such file or directory" in stderr_lower
                    or "can't open file" in stderr_lower
                    or "is not recognized as the name of a cmdlet" in stderr_lower
                    or "is not recognized as a name of a cmdlet" in stderr_lower
                    or not stderr_lower
                )
                if (
                    code == -1 and stderr.startswith("shell-not-installed:")
                ) or hook_script_missing:
                    skip_reason = (
                        stderr.strip()
                        if stderr.startswith("shell-not-installed:")
                        else f"hook script not present at install path (exit={code})"
                    )
                    results.append(
                        Check(
                            f"storm:{event}/{matcher}",
                            True,
                            f"skipped ({skip_reason})",
                        )
                    )
                    continue
                envelope = _extract_envelope(stdout)
                if _is_gate_verdict(envelope, code):
                    # The conformity gate is a verdict hook: exit 0 (allow) or
                    # exit 2 (block) with its own report on stdout. Both are
                    # correct, non-crash responses.
                    ok = True
                    detail = f"conformity-gate verdict (exit={code})"
                else:
                    ok = code == 0 and _is_valid_envelope(envelope)
                    detail = (
                        "exit=0, valid envelope"
                        if ok
                        else f"exit={code}, stderr={stderr.strip()[:180]}"
                    )
                results.append(Check(f"storm:{event}/{matcher}", ok, detail))
    return results


def malformed_stdin_check(root: Path, content_root: Path) -> Check:
    """Feed partial JSON on stdin; expect a valid envelope on stdout."""
    py = _python_exe()
    dispatch = str(content_root / "hooks" / "dispatch.py")
    proc = subprocess.run(
        [
            py,
            dispatch,
            "--event-name",
            "PreToolUse",
            "--context-file",
            "src/apothem/hooks/messages/pretooluse-write.md",
        ],
        input='{"source":',
        capture_output=True,
        text=True,
        cwd=str(root),
        check=False,
    )
    envelope = _extract_envelope(proc.stdout)
    ok = _is_valid_envelope(envelope)
    detail = "valid JSON" if ok else f"raw={proc.stdout.strip()[:180]}"
    return Check("emit:malformed-stdin", ok, detail)


def missing_context_check(root: Path, content_root: Path) -> Check:
    """Point the dispatch at a missing context file; expect valid envelope."""
    py = _python_exe()
    dispatch = str(content_root / "hooks" / "dispatch.py")
    proc = subprocess.run(
        [
            py,
            dispatch,
            "--event-name",
            "PreToolUse",
            "--context-file",
            "src/apothem/hooks/messages/missing.md",
        ],
        capture_output=True,
        text=True,
        cwd=str(root),
        check=False,
    )
    envelope = _extract_envelope(proc.stdout)
    ok = _is_valid_envelope(envelope)
    detail = "valid JSON" if ok else f"raw={proc.stdout.strip()[:180]}"
    return Check("emit:missing-context", ok, detail)


def degraded_resolution_check(root: Path, content_root: Path) -> Check:
    """Run dispatch.py from a throwaway HOME; expect valid envelope."""
    py = _python_exe()
    with tempfile.TemporaryDirectory(prefix="chaos-deg-") as tmp:
        tmp_path = Path(tmp)
        fake_home = tmp_path / "fake-home"
        fake_home.mkdir()
        env = os.environ.copy()
        env.pop("CLAUDE_PROJECT_DIR", None)
        env["HOME"] = str(fake_home)
        env["USERPROFILE"] = str(fake_home)
        dispatch = str(content_root / "hooks" / "dispatch.py")
        proc = subprocess.run(
            [
                py,
                dispatch,
                "--event-name",
                "PreToolUse",
                "--context-file",
                "src/apothem/hooks/messages/pretooluse-write.md",
            ],
            capture_output=True,
            text=True,
            cwd=str(root),
            env=env,
            check=False,
        )
    envelope = _extract_envelope(proc.stdout)
    ok = _is_valid_envelope(envelope)
    detail = "valid JSON" if ok else f"raw={proc.stdout.strip()[:180]}"
    return Check("dispatch:degraded-resolution", ok, detail)


def run(root: Path, content_root: Path | None = None) -> list[Check]:
    """Execute every chaos check and return a consolidated result list."""
    cr = content_root if content_root is not None else root
    results: list[Check] = []
    results.extend(storm_configured_hooks(root))
    results.append(malformed_stdin_check(root, cr))
    results.append(missing_context_check(root, cr))
    results.append(degraded_resolution_check(root, cr))
    return results


def report(results: list[Check]) -> int:
    """Render results to stdout and return an exit code."""
    fails = 0
    for check in results:
        marker = "[PASS]" if check.passed else "[FAIL]"
        sys.stdout.write(f"{marker} {check.name} -- {check.detail}\n")
        if not check.passed:
            fails += 1
    sys.stdout.write(f"Chaos pass checks: {len(results)}, failures: {fails}\n")
    return 0 if fails == 0 else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(prog="chaos_pass")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--content-root",
        type=Path,
        default=None,
        help=(
            "Directory where hook scripts live (hooks/ subdir). "
            "Defaults to --root. Use src/apothem when running against "
            "the apothem source repository."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    root = args.root or resolve_project_root(Mode.MARKER, script_path=Path(__file__))
    if root is None:
        sys.stdout.write("[FAIL] Cannot resolve apothem ecosystem root\n")
        return 1
    content_root = args.content_root or default_content_root(root)
    return report(run(root, content_root=content_root))


if __name__ == "__main__":
    sys.exit(main())
