# SPDX-License-Identifier: MIT

"""Emit structured JSON context for supported harness hook events.

Two modes of operation:

* **Hook mode** — when both ``--hook-event-name`` and ``--context-file``
  are supplied, read a context-message file plus hook metadata from
  stdin and emit a single-line ``hookSpecificOutput`` envelope.
* **Diagnostic mode** — when either argument is absent, print a human-
  readable ecosystem summary (counts of rules/commands/agents/skills
  and presence of core files).

On any unexpected failure, emit a valid JSON envelope with a failure
message and exit 0 — never surface raw tracebacks to the hook runtime.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

_LIB_DIR: Final[Path] = Path(__file__).resolve().parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from events import (
    HOOK_SPECIFIC_OUTPUT_EVENTS as _HOOK_SPECIFIC_OUTPUT_EVENTS,
)
from log import get_logger
from resolve_root import Mode, resolve_project_root
from stdin_json import read_stdin_json

_logger = get_logger(__name__)

_UNICODE_MAP: Final[dict[str, str]] = {
    "\u2013": "-",
    "\u2014": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00d7": "x",
    "\u2212": "-",
    "\u2192": "->",
    "\u2264": "<=",
}


def normalize_ascii(text: str) -> str:
    """Transliterate common typographic Unicode to ASCII, preserving other UTF-8.

    Maps the handful of typographic characters in ``_UNICODE_MAP`` (curly quotes,
    dashes, arrows) to their ASCII equivalents so the emitted envelope reads
    cleanly across terminals, but PRESERVES every other non-ASCII character. The
    consumer is the hook envelope's ``additionalContext`` / ``systemMessage``
    field — carried as UTF-8 JSON, which represents any Unicode faithfully — so
    non-Latin MEMORY / plan content (e.g. a project overview in another script)
    survives into the SessionStart summary instead of being silently deleted.
    The prior wholesale non-ASCII strip is retired: only a consumer that truly
    requires 7-bit ASCII (the statusline renderer, whose ``_ascii_safe`` still
    drops unmapped code points) transliterates-and-drops.
    """
    if not text:
        return ""
    for source, target in _UNICODE_MAP.items():
        text = text.replace(source, target)
    return text


def read_hook_stdin() -> dict[str, object] | None:
    """Read and parse the hook's stdin JSON payload, if any.

    Thin wrapper over the shared :func:`stdin_json.read_stdin_json` so the four
    hook stdin readers share one fail-open read path (terminal stdin, read
    error, empty input, malformed JSON, or a non-object value all → ``None``).
    """
    return read_stdin_json()


def build_metadata_prefix(payload: dict[str, object] | None) -> str:
    """Return a bracketed metadata prefix, or empty string when absent."""
    if not payload:
        return ""
    parts: list[str] = []
    for field, label in (
        ("source", "source"),
        ("tool_name", "tool"),
        ("matcher", "matcher"),
    ):
        value = payload.get(field)
        if isinstance(value, str) and value:
            parts.append(f"{label}={value}")
    return f"[{' | '.join(parts)}]" if parts else ""


_BASH_GIT_TRIGGERS: Final[tuple[str, ...]] = (
    "git commit",
    "git checkout -b",
    "git branch",
    "git tag",
    "git merge -m",
    "git rebase --exec",
    "git stash push -m",
    "git notes add",
    "git mv",
    "git rm",
)

# Compiled boundary-anchored matchers for the git-mutation triggers above.
# ``git`` must sit at a command-word boundary — start of string or after
# whitespace / a shell separator (``;`` ``&`` ``|`` ``(`` ``{`` backtick) — so a
# bare substring inside another token (``echo "git commit"`` inside a quoted
# string, ``mygit commit``, ``digit branch``) does not trip the git reminder,
# and inter-token whitespace is matched flexibly (one or more spaces/tabs).
# The trigger's own trailing token is boundary-anchored too, so ``git branch``
# still fires on ``git branch feature`` (a branch-CREATE) — the reminder's
# intended target — as it did before.
_BASH_GIT_TRIGGER_RES: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(
        r"(?:^|[\s;&|(){}`])"
        + r"[ \t]+".join(re.escape(word) for word in trigger.split())
        + r"(?![\w-])"
    )
    for trigger in _BASH_GIT_TRIGGERS
)


def _command_has_git_trigger(command: str) -> bool:
    """Return True when *command* invokes a git-mutation trigger at a word boundary."""
    return any(pattern.search(command) for pattern in _BASH_GIT_TRIGGER_RES)


# The three base codebase-isolation guards. Their STOP guidance is only relevant
# when a Write/Edit/NotebookEdit would actually leak plan-internal terminology
# into a product artifact, so they emit conditionally: a clean scan suppresses
# the context (the silent, low-noise default), a detected leak emits it. Firing
# them on every Write/Edit — as an unconditional suppression bypass would — is
# pure noise; suppressing them unconditionally means the guidance never reaches
# the model even when a leak is present. The conditional gate is the middle
# ground. (``pretooluse-conformity`` is intentionally absent: it is not wired as
# a dispatch-routed context — the mechanical conformity check ships as the
# ``gate.py --hook`` entry — so it never reaches this emitter to be suppressed.)
_CODEBASE_ISOLATION_MESSAGES: Final[frozenset[str]] = frozenset(
    {
        "pretooluse-write.md",
        "pretooluse-edit.md",
        "pretooluse-notebookedit.md",
    }
)

# Plan-internal identifier shapes that must not leak into a product artifact:
# bracketed task/mandate ids (``TM-10``, ``CM-7``, ``CP-20``), phase-campaign
# names (``Phase-B``, ``AD-1``), and plan-suite folder references. The token
# matcher requires a word boundary so an unrelated word (``EC-2`` in a URL,
# ``I-9``) is matched only in the id shape ``<1-3 uppercase letters>-<digits>``.
_PLAN_TERM_RES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\b[A-Z]{1,3}-\d+\b"),
    re.compile(r"\bPhase-[A-Z0-9]+\b"),
)

_HEADER_GUARD_MESSAGES: Final[frozenset[str]] = frozenset(
    {
        "pretooluse-write-header-guard.md",
        "pretooluse-edit-header-guard.md",
    }
)

_PLAN_GUARD_MESSAGES: Final[frozenset[str]] = frozenset(
    {
        "pretooluse-write-plan-guard.md",
        "pretooluse-bash-plan-guard.md",
    }
)

_PLAN_SHAPED_MARKERS: Final[tuple[str, ...]] = (
    "master-plan:",
    "phase-id:",
    "phases:",
    "resumption contract",
    "phase output registry",
)

# Path fragments that mark a write as targeting a plans tree. Anchored to the
# two recognized plans-tree stems — the canonical ``.apothem/plans`` and the
# legacy ``.plans`` — so an unrelated ``docs/plans/roadmap.md`` (a bare
# ``/plans/`` segment that is NOT a plans tree) does not trip the plan guard.
_PLAN_PATH_MARKERS: Final[tuple[str, ...]] = (
    ".apothem/plans/",
    ".plans/",
)


def should_suppress_bash_hook(
    event_name: str,
    context_file: str,
    payload: dict[str, object] | None,
) -> bool:
    """Return True when a Bash PreToolUse hook should emit no context.

    The pretooluse-bash context message is a git-artifact-isolation
    reminder keyed to the fixed git-mutation trigger set above. For
    non-git Bash invocations the message adds noise, so the hook emits
    an empty envelope instead. Mirrors the trigger declaration in
    ``hooks/messages/pretooluse-bash.md`` to preserve the message-
    dispatcher paired-shape invariant.

    Degraded stdin (no payload, a non-Bash tool, or an unreadable command
    string) suppresses the reminder: with no command to inspect the guard
    cannot confirm a git mutation, and the git-artifact reminder is only
    relevant to a git-write command — firing it on every Bash call when
    stdin is unavailable is pure noise. The reminder fires ONLY when a
    git-mutation trigger is positively matched at a command-word boundary.
    """
    # "Not the bash hook" guards return False: this predicate has no opinion on
    # a non-bash message and must not suppress it (another predicate decides).
    if event_name != "PreToolUse":
        return False
    if not context_file.endswith("pretooluse-bash.md"):
        return False
    # From here the context IS the bash git-artifact reminder. Degraded stdin —
    # no payload, a non-Bash tool, or an unreadable command string — means the
    # command cannot be inspected: suppress (return True), because the reminder
    # is only relevant to a positively-matched git-write command and firing it
    # blind on every Bash call is pure noise.
    if not payload or payload.get("tool_name") != "Bash":
        return True
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return True
    command = tool_input.get("command")
    if not isinstance(command, str):
        return True
    return not _command_has_git_trigger(command)


def _context_basename(context_file: str) -> str:
    return Path(context_file).name


def _tool_input(payload: dict[str, object] | None) -> dict[str, object]:
    if not payload:
        return {}
    raw = payload.get("tool_input")
    return raw if isinstance(raw, dict) else {}


def _path_from_tool_input(tool_input: dict[str, object]) -> str:
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str):
            return value
    return ""


def _text_from_tool_input(tool_input: dict[str, object]) -> str:
    chunks: list[str] = []
    for key in ("content", "new_string", "command", "cell_source"):
        value = tool_input.get(key)
        if isinstance(value, str):
            chunks.append(value)
    return "\n".join(chunks)


def _nearest_git_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _is_project_local_plan_path(path: str, root: Path | None = None) -> bool:
    if not path:
        return False
    try:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            base = root if root is not None else Path.cwd()
            candidate = base / candidate
        resolved = candidate.resolve()
        # Anchor the "inside the project" test on the RESOLVED project root the
        # hook runner already computed (run_hook_mode threads it through), not
        # on Path.cwd(). When the hook fires with a cwd that differs from the
        # project root, a cwd-anchored git-ascent misclassifies a legitimate
        # ``.apothem/plans/`` write; the resolved root fixes that. When no root
        # is supplied (direct callers), fall back to the git root of the cwd.
        project_root = (
            root.resolve() if root is not None else _nearest_git_root(Path.cwd())
        )
        resolved.relative_to(project_root)
    except (OSError, RuntimeError, ValueError):
        return False
    # The canonical project-local plans tree is ``.apothem/plans/``; a legacy
    # ``.plans/`` tree is still recognized as project-local (its upgrade path
    # is ``apothem migrate-workspace``, surfaced elsewhere — this predicate
    # only answers "is this a plans write inside the project").
    parts = resolved.parts
    if ".plans" in parts:
        return True
    return any(
        parts[index] == ".apothem" and parts[index + 1] == "plans"
        for index in range(len(parts) - 1)
    )


def _looks_plan_shaped(path: str, text: str, root: Path | None = None) -> bool:
    if _is_project_local_plan_path(path, root):
        return False
    haystack = f"{path}\n{text}".lower().replace("\\", "/")
    if any(marker in haystack for marker in _PLAN_PATH_MARKERS):
        return True
    return any(marker in haystack for marker in _PLAN_SHAPED_MARKERS)


def _missing_header(path: str, text: str) -> bool:
    if not path or not text:
        return False
    try:
        from apothem.conformity import file_header_grep
    except ImportError as exc:
        # Plugin-alone installs ship the dispatcher without the ``apothem``
        # package on the path, so the conformity import is unresolvable. That
        # is an ABSENT checker, not a header-absent verdict: degrade to
        # no-advisory (return False) so the header guard does not fire on
        # EVERY Write/Edit where it cannot actually check the header. The
        # header invariant is still enforced mechanically in CI and pre-commit.
        _logger.debug(
            "file_header_grep unavailable (%s); header guard degraded to no-advisory",
            type(exc).__name__,
        )
        return False
    try:
        result = file_header_grep.check(text, Path(path))
    except Exception as exc:  # code-craft-boundary: broad-except; fail-closed guard.
        # A genuine internal defect in file_header_grep.check (the module
        # imported, but the call raised) fails CLOSED — treat as header-absent
        # and surface the failing class so a real bug is distinguishable from a
        # true header-absent verdict rather than silently masked.
        _logger.warning(
            "file_header_grep.check raised %s for %s; failing closed",
            type(exc).__name__,
            path,
        )
        return True
    return not result.passed


def should_suppress_pretooluse_context(
    event_name: str,
    context_file: str,
    payload: dict[str, object] | None,
    root: Path | None = None,
) -> bool:
    """Suppress allow-class PreToolUse context messages.

    The actual conformity hooks still run. This emitter only controls
    advisory context volume, so pass-class tool calls should return an
    empty envelope and reserve prose for findings or guarded actions.

    *root* is the resolved project root the hook runner already computed; it is
    threaded into the plan-guard predicate so a relative target and the
    "inside the project" test anchor on the real root rather than ``Path.cwd()``
    (which can differ from the project root when the hook fires).
    """
    if event_name != "PreToolUse":
        return False
    basename = _context_basename(context_file)
    tool_input = _tool_input(payload)
    path = _path_from_tool_input(tool_input)
    text = _text_from_tool_input(tool_input)
    if basename in _CODEBASE_ISOLATION_MESSAGES:
        # Emit the codebase-isolation STOP guidance only when the write would
        # actually leak a plan-internal identifier; a clean scan suppresses it.
        return not _leaks_plan_terms(text)
    if basename in _PLAN_GUARD_MESSAGES:
        return not _looks_plan_shaped(path, text, root)
    if basename in _HEADER_GUARD_MESSAGES:
        return not _missing_header(path, text)
    return False


def _leaks_plan_terms(text: str) -> bool:
    """True when *text* carries a plan-internal identifier that must not ship.

    Scans the proposed content for the bracketed task/mandate id shape and the
    phase-campaign name shape. Empty text (no content to inspect) never trips
    the guard, so a bare Write of an empty file stays silent.
    """
    if not text:
        return False
    return any(pattern.search(text) for pattern in _PLAN_TERM_RES)


def compose_context(message: str, payload: dict[str, object] | None) -> str:
    """Combine a metadata prefix (if any) with the message body."""
    prefix = build_metadata_prefix(payload)
    body = message or ""
    if prefix and body:
        return f"{prefix}\n{body}"
    return prefix or body


def resolve_context_path(context_file: str, root: Path) -> Path | None:
    """Return `context_file` as an absolute path within `root`.

    Absolute paths are accepted as-is (the caller — typically a hook
    configuration in ``settings.json`` — explicitly chose them). Relative
    paths are joined against `root` and verified not to escape it via
    parent-directory traversal; on escape, returns ``None`` so the caller
    can decline the read instead of leaking arbitrary file contents.
    """
    candidate = Path(context_file)
    if candidate.is_absolute():
        return candidate
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def build_envelope(event_name: str, additional_context: str) -> dict[str, object]:
    """Return the schema-valid envelope for `event_name`."""
    if event_name in _HOOK_SPECIFIC_OUTPUT_EVENTS:
        return {
            "hookSpecificOutput": {
                "hookEventName": event_name,
                "additionalContext": additional_context,
            }
        }
    return {"systemMessage": additional_context}


def emit_hook_envelope(event_name: str, additional_context: str, quiet: bool) -> None:
    """Print the schema-appropriate JSON envelope (unless quiet)."""
    envelope = build_envelope(event_name, additional_context)
    if not quiet:
        sys.stdout.write(json.dumps(envelope, separators=(",", ":")) + "\n")


def emit_failure_envelope(event_name: str, message: str) -> None:
    """Print a failure envelope to stdout; used as the last-resort path."""
    envelope = build_envelope(
        event_name or "UnknownEvent",
        f"Hook execution failure: {message}",
    )
    sys.stdout.write(json.dumps(envelope, separators=(",", ":")) + "\n")


def run_hook_mode(
    event_name: str,
    context_file: str,
    quiet: bool,
    root: Path,
) -> None:
    """Read context file + stdin, emit the hook envelope."""
    resolved = resolve_context_path(context_file, root)
    message = ""
    if resolved is None:
        _logger.warning("Refusing context path outside root: %s", context_file)
    elif resolved.is_file():
        try:
            message = resolved.read_text(encoding="utf-8")
        except OSError as exc:
            _logger.debug("Context file unreadable: %s", exc)

    payload = read_hook_stdin()
    if should_suppress_bash_hook(event_name, context_file, payload):
        emit_hook_envelope(event_name, "", quiet)
        return
    if should_suppress_pretooluse_context(event_name, context_file, payload, root):
        emit_hook_envelope(event_name, "", quiet)
        return
    combined = compose_context(message, payload)
    additional = normalize_ascii(combined)
    emit_hook_envelope(event_name, additional, quiet)


def run_diagnostic_mode(root: Path) -> None:
    """Print a human-readable ecosystem summary.

    Uses ``print`` deliberately: this is the diagnostic CLI surface, not
    operational logging. ``logging`` would route through handlers that the
    CLI runner doesn't necessarily configure.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("=== Apothem Ecosystem Diagnostics ===")
    print(f"Timestamp: {now}")
    print(f"PROJECT_ROOT: {root}")
    print()

    counts: dict[str, int] = {
        "Rules": _count(root / "rules", "*.md"),
        "Commands": _count(root / "commands", "*.md"),
        "Agents": _count(root / "agents", "*.md", recursive=False),
        "Skills": _count(root / "skills", "SKILL.md", recursive=True),
    }
    print("  ".join(f"{k}: {v}" for k, v in counts.items()))
    print()

    probes = (
        "CLAUDE.md",
        "settings.json",
        "site/content/docs/reference/settings-reference.mdx",
        "hooks/emit_hook_context.py",
        "hooks/session_start_bootstrap.py",
    )
    for rel in probes:
        marker = "+" if (root / rel).exists() else "-"
        print(f"{marker} {rel}")


def _count(directory: Path, pattern: str, *, recursive: bool = False) -> int:
    """Return the number of files matching `pattern` in `directory`."""
    if not directory.is_dir():
        return 0
    matcher = directory.rglob if recursive else directory.glob
    return sum(1 for _ in matcher(pattern))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="emit_hook_context",
        description="Emit hook context as structured JSON.",
    )
    parser.add_argument("--hook-event-name", "-n", default="")
    parser.add_argument("--context-file", "-c", default="")
    parser.add_argument("--quiet", "-q", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point. Guarantees a valid JSON envelope on any failure."""
    args = parse_args(argv)
    try:
        root = resolve_project_root(Mode.HOOKS, script_path=Path(__file__))
        if root is None:
            root = Path(__file__).resolve().parent.parent

        if not args.hook_event_name or not args.context_file:
            run_diagnostic_mode(root)
            return
        run_hook_mode(args.hook_event_name, args.context_file, args.quiet, root)
    except Exception as exc:
        emit_failure_envelope(args.hook_event_name, str(exc))


if __name__ == "__main__":
    main()
