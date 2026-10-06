# SPDX-License-Identifier: MIT

"""Hook-chain end-to-end latency benchmark per the per-event budgets in
`src/apothem/rules/performance-discipline.md` §1.

What is measured. For each event the plugin registers in
``src/apothem/hooks/hooks.json``, every ``shell: bash`` command of every
matcher runs exactly as written (``bash -c <command>`` with
``CLAUDE_PLUGIN_ROOT`` set to the repository root), with a realistic event
payload on stdin: a ``Write`` of ``app.py`` for ``PreToolUse:Write``, an
``ls -la`` for ``PreToolUse:Bash``, a two-option question for
``PreToolUse:AskUserQuestion``, and so on. That is the full path a harness
takes on a real event: the bootstrap stub, interpreter discovery, the
dispatcher, the handler, and the message emission. ``PowerShell`` entries are
the Windows twins of the bash entries and are not run.

Each run uses a fresh session id, a scratch ``HOME``, ``TMPDIR`` and project
directory, so per-session state (the Stop gate, the compaction tracker) starts
clean every run. A chain's figures are medians over ``--runs`` runs:

* ``median_sum_ms`` — the chain's commands run one after another, summed: the
  total handler time one event costs;
* ``median_max_ms`` — the slowest single command: the wall time when the
  harness runs a matcher's hooks in parallel;
* ``injected_chars`` — characters of ``additionalContext`` and
  ``systemMessage`` the chain emits for that payload (what lands in context).

Verdicts and exit codes (the worst chain decides):

* ``0`` pass — every measured chain's slowest command is inside its event's
  budget;
* ``1`` over budget;
* ``2`` error — a command could not run as registered (for example exit 126,
  a script without its executable bit), exited non-zero, printed output that is
  not JSON, or reported that it skipped itself (the bootstrap is fail-open and
  exits 0 with a diagnostic envelope when the dispatcher or interpreter is
  missing), or the manifest or dispatcher is missing;
* ``3`` not measured — no hook is registered for the requested event (the
  budget table lists ``UserPromptSubmit`` and ``Notification``, which the
  plugin does not register).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

_BUDGETS: Final[dict[str, float]] = {
    "PreToolUse": 10.0,
    "PostToolUse": 10.0,
    "UserPromptSubmit": 10.0,
    "Notification": 10.0,
    "SessionStart": 30.0,
    "PreCompact": 30.0,
    "PostCompact": 30.0,
    "Stop": 60.0,
}

EXIT_PASS: Final[int] = 0
EXIT_OVER_BUDGET: Final[int] = 1
EXIT_ERROR: Final[int] = 2
EXIT_NOT_MEASURED: Final[int] = 3

# bench_hooks.py lives at <repo>/src/apothem/benchmarks/; four parents up is
# the repository root, which is also ${CLAUDE_PLUGIN_ROOT} for the source-tree
# manifest (its commands address src/apothem/hooks/...).
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_DISPATCHER: Final[Path] = _REPO_ROOT / "src" / "apothem" / "hooks" / "dispatch.py"
_HOOKS_JSON: Final[Path] = _REPO_ROOT / "src" / "apothem" / "hooks" / "hooks.json"

_DEFAULT_RUNS: Final[int] = 5
_SESSION_PREFIX: Final[str] = "apothem-bench"

# Diagnostic envelopes the fail-open bootstrap, dispatcher and emitter print
# (exit 0) when the handler did not run. A chain that emits one has measured
# nothing real.
_SKIP_ENVELOPE: Final[re.Pattern[str]] = re.compile(
    r"^(?:hook bootstrap:|hook \S+ skipped:|Hook (?:bootstrap|execution) failure:)"
)


@dataclass(frozen=True)
class ChainResult:
    """One measured (event, matcher) chain."""

    event: str
    matcher: str
    commands: int
    runs: int
    budget_s: float
    status: str
    detail: str
    median_sum_ms: float | None = None
    median_max_ms: float | None = None
    injected_chars: int | None = None


def registered_chains(manifest: Path) -> dict[str, list[tuple[str, list[str]]]]:
    """Return ``{event: [(matcher, [bash commands]), ...]}`` from a hooks.json."""
    document = json.loads(manifest.read_text(encoding="utf-8"))
    chains: dict[str, list[tuple[str, list[str]]]] = {}
    for event, groups in document.get("hooks", {}).items():
        for group in groups:
            commands = [
                str(hook["command"])
                for hook in group.get("hooks", [])
                if hook.get("type") == "command" and hook.get("shell", "bash") == "bash"
            ]
            if commands:
                chains.setdefault(event, []).append(
                    (str(group.get("matcher", "*")), commands)
                )
    return chains


def _tool_call(matcher: str, project: Path) -> tuple[str, dict[str, object]]:
    """Return a realistic ``(tool_name, tool_input)`` for a PreToolUse matcher."""
    app = str(project / "app.py")
    calls: dict[str, tuple[str, dict[str, object]]] = {
        "Write": ("Write", {"file_path": app, "content": "print('hello')\n"}),
        "Edit": (
            "Edit",
            {"file_path": app, "old_string": "hello", "new_string": "world"},
        ),
        "NotebookEdit": (
            "NotebookEdit",
            {
                "notebook_path": str(project / "analysis.ipynb"),
                "cell_id": "cell-1",
                "new_source": "total = 1 + 1\n",
            },
        ),
        "Bash": ("Bash", {"command": "ls -la", "description": "List files"}),
        "AskUserQuestion": (
            "AskUserQuestion",
            {
                "questions": [
                    {
                        "question": "Which database should the service use?",
                        "header": "Database",
                        "multiSelect": False,
                        "options": [
                            {
                                "label": "PostgreSQL (Recommended)",
                                "description": "Matches the existing deployment.",
                            },
                            {
                                "label": "SQLite",
                                "description": "Simpler, single-node only.",
                            },
                        ],
                    }
                ]
            },
        ),
    }
    return calls.get(matcher, calls["Write"] if matcher == "*" else (matcher, {}))


def build_payload(
    event: str, matcher: str, project: Path, transcript: Path, session_id: str
) -> dict[str, object]:
    """Return the stdin payload a harness sends for ``event`` / ``matcher``."""
    payload: dict[str, object] = {
        "session_id": session_id,
        "transcript_path": str(transcript),
        "cwd": str(project),
        "hook_event_name": event,
        "permission_mode": "default",
    }
    if event in {"PreToolUse", "PostToolUse"}:
        tool_name, tool_input = _tool_call(matcher, project)
        payload["tool_name"] = tool_name
        payload["tool_input"] = tool_input
        if event == "PostToolUse":
            payload["tool_response"] = {
                "filePath": str(project / "app.py"),
                "success": True,
            }
    elif event == "SessionStart":
        payload["source"] = "startup"
    elif event in {"PreCompact", "PostCompact"}:
        payload["trigger"] = "auto"
        payload["custom_instructions"] = ""
    elif event == "Stop":
        payload["stop_hook_active"] = False
    elif event == "UserPromptSubmit":
        payload["prompt"] = "Add a test for the parser."
    return payload


class _ChainError(Exception):
    """A chain command did not run its handler; the message says why."""


def _injected_chars(stdout: str) -> int:
    """Characters of context a hook output injects (0 for empty output).

    Raises ``json.JSONDecodeError`` for output that is not JSON and
    ``_ChainError`` for a fail-open diagnostic envelope.
    """
    if not stdout.strip():
        return 0
    envelope = json.loads(stdout)
    if not isinstance(envelope, dict):
        return 0
    texts = [str(envelope.get("systemMessage", ""))]
    specific = envelope.get("hookSpecificOutput")
    if isinstance(specific, dict):
        texts.append(str(specific.get("additionalContext", "")))
    for text in texts:
        if _SKIP_ENVELOPE.match(text):
            raise _ChainError(f"handler did not run: {text.strip()[:200]}")
    return sum(len(text) for text in texts)


def _run_command(
    command: str, stdin: str, env: dict[str, str], cwd: Path, timeout: float
) -> tuple[float, int]:
    """Run one registered command; return ``(seconds, injected_chars)``."""
    bash = shutil.which("bash")
    if bash is None:
        raise _ChainError("bash is not on PATH")
    start = time.perf_counter()
    try:
        completed = subprocess.run(  # noqa: S603 — the command is the repository's own registered hook, run as the harness runs it
            [bash, "-c", command],
            input=stdin,
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise _ChainError(f"timed out after {timeout:g}s: {command}") from exc
    elapsed = time.perf_counter() - start
    if completed.returncode != 0:
        reason = {126: "not executable", 127: "not found"}.get(
            completed.returncode, "non-zero exit"
        )
        first_line = (completed.stderr.strip().splitlines() or [""])[0]
        raise _ChainError(
            f"exit {completed.returncode} ({reason}) running as registered: "
            f"{command} {first_line}".rstrip()
        )
    try:
        injected = _injected_chars(completed.stdout)
    except json.JSONDecodeError as exc:
        raise _ChainError(
            f"output is not JSON: {completed.stdout.strip()[:120]!r}"
        ) from exc
    return elapsed, injected


def measure_chain(
    event: str, matcher: str, commands: list[str], runs: int
) -> ChainResult:
    """Run one chain ``runs`` times on a fresh scratch world; return its result."""
    budget = _BUDGETS.get(event, 10.0)
    sums: list[float] = []
    maxima: list[float] = []
    injected = 0
    try:
        with tempfile.TemporaryDirectory(prefix="apothem-bench-hooks-") as scratch:
            root = Path(scratch)
            for run in range(runs):
                world = root / f"run-{run}"
                home, project, tmp = world / "home", world / "project", world / "tmp"
                for directory in (home, project, tmp):
                    directory.mkdir(parents=True)
                transcript = world / "transcript.jsonl"
                transcript.write_text("", encoding="utf-8")
                env = dict(os.environ)
                env.update(
                    {
                        "CLAUDE_PLUGIN_ROOT": str(_REPO_ROOT),
                        "CLAUDE_PROJECT_DIR": str(project),
                        "HOME": str(home),
                        "TMPDIR": str(tmp),
                    }
                )
                payload = json.dumps(
                    build_payload(
                        event, matcher, project, transcript, f"{_SESSION_PREFIX}-{run}"
                    )
                )
                times: list[float] = []
                injected = 0
                for command in commands:
                    elapsed, chars = _run_command(
                        command, payload, env, project, budget * 2 + 5
                    )
                    times.append(elapsed)
                    injected += chars
                sums.append(sum(times))
                maxima.append(max(times))
    except _ChainError as exc:
        return ChainResult(
            event, matcher, len(commands), runs, budget, "error", str(exc)
        )
    median_max = statistics.median(maxima)
    status = "pass" if median_max <= budget else "over-budget"
    detail = (
        f"slowest command {median_max:.3f}s "
        f"{'within' if status == 'pass' else 'exceeds'} budget {budget}s"
    )
    return ChainResult(
        event,
        matcher,
        len(commands),
        runs,
        budget,
        status,
        detail,
        median_sum_ms=round(statistics.median(sums) * 1000, 1),
        median_max_ms=round(median_max * 1000, 1),
        injected_chars=injected,
    )


def _exit_code(results: list[ChainResult]) -> int:
    statuses = {result.status for result in results}
    if "error" in statuses:
        return EXIT_ERROR
    if "over-budget" in statuses:
        return EXIT_OVER_BUDGET
    if statuses <= {"not-measured"}:
        return EXIT_NOT_MEASURED
    return EXIT_PASS


def _label(result: ChainResult) -> str:
    return result.event if result.matcher == "*" else f"{result.event}:{result.matcher}"


def main(argv: list[str] | None = None) -> int:
    """Run the hook-chain benchmark; return the exit code (see module docstring).

    Pre-conditions: ``argv`` is the argument vector without the program name
    (``None`` reads ``sys.argv``). ``--event`` selects one event from the
    budget table; without it every registered event is measured.

    Post-conditions: prints one line per chain (or a JSON report with
    ``--json``) and returns 0 pass, 1 over budget, 2 error, 3 not measured.
    """
    parser = argparse.ArgumentParser(prog="bench_hooks")
    parser.add_argument(
        "--event",
        choices=sorted(_BUDGETS),
        default=None,
        help="Hook event to benchmark; default: every event the manifest registers.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=_DEFAULT_RUNS,
        help=f"Runs per chain; the median is reported (default {_DEFAULT_RUNS}).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print a JSON report instead of lines."
    )
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    for target, what in ((_DISPATCHER, "dispatcher"), (_HOOKS_JSON, "hook manifest")):
        if not target.is_file():
            print(f"ERROR: {what} not found: {target}", file=sys.stderr)
            return EXIT_ERROR

    chains = registered_chains(_HOOKS_JSON)
    events = [args.event] if args.event else sorted(chains)
    results: list[ChainResult] = []
    for event in events:
        if event not in chains:
            results.append(
                ChainResult(
                    event,
                    "*",
                    0,
                    0,
                    _BUDGETS.get(event, 10.0),
                    "not-measured",
                    f"no hook is registered for {event} in {_HOOKS_JSON.name}",
                )
            )
            continue
        for matcher, commands in chains[event]:
            results.append(measure_chain(event, matcher, commands, args.runs))

    code = _exit_code(results)
    if args.json:
        report = {
            "manifest": str(_HOOKS_JSON),
            "runs": args.runs,
            "exit_code": code,
            "chains": {_label(result): asdict(result) for result in results},
        }
        print(json.dumps(report, indent=2))
        return code
    for result in results:
        label = _label(result)
        if result.status == "not-measured":
            print(f"NOT MEASURED: {label} — {result.detail}")
        elif result.status == "error":
            print(f"ERROR: {label} — {result.detail}")
        else:
            verdict = "PASS" if result.status == "pass" else "FAIL"
            print(
                f"{verdict}: {label} chain of {result.commands} = "
                f"{result.median_sum_ms}ms total, {result.median_max_ms}ms slowest, "
                f"{result.injected_chars} chars injected ({result.detail})"
            )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
