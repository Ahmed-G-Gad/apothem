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

import contextlib
import itertools
import json
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable

_LIB_DIR: Final[Path] = Path(__file__).resolve().parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from events import (
    HOOK_SPECIFIC_OUTPUT_EVENTS as _HOOK_SPECIFIC_OUTPUT_EVENTS,
)
from header_check import edit_lacks_header, project_adopts_header, write_lacks_header
from log import get_logger
from message_text import advisory_section, fill_placeholders, strip_maintainer_text
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

# Public identifiers that share the ``<letters>-<digits>`` shape with a plan id
# but name a standard, an encoding or an advisory: ``UTF-8``, ``SHA-256``,
# ``ISO-8601``, ``CVE-2026-1234``, ``RFC-2119``. Flagging them made the
# isolation guard fire on ordinary prose and commit messages.
_STANDARD_ID_PREFIXES: Final[frozenset[str]] = frozenset(
    {
        "AES", "BSD", "CC", "CVE", "CWE", "GPL", "IEC", "ISO", "OSV",
        "PEP", "RFC", "RSA", "SHA", "SSL", "TLS", "UTF",
    }
)  # fmt: skip

#: Shell-redirection and file-writing forms whose target the Bash plan guard
#: inspects (see ``pretooluse-bash-plan-guard.md``, output-redirection table).
#: Every pattern is linear (no nested quantifiers), so a long command cannot
#: stall the hook.
_QUOTED_OR_BARE: Final[str] = r"(\"[^\"]+\"|'[^']+'|[^\s;&|<>()]+)"
_REDIRECT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:&>>?|\d?>>?\|?)\s*" + _QUOTED_OR_BARE
)
_REDIRECT_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^(?:\d*>|&>|<)")
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"\"[^\"]*\"|'[^']*'|\S+")
_STATEMENT_SPLIT_RE: Final[re.Pattern[str]] = re.compile(r"&&|\|\||[;|\n]")
#: A heredoc opener (not a ``<<<`` here-string): ``<<EOF``, ``<<-'EOF'``.
_HEREDOC_START_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<!<)<<(-?)(?!<)[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2"
)
_NULL_TARGETS: Final[frozenset[str]] = frozenset({"/dev/null", "$null", "nul", "NUL"})
_MSYS_DRIVE_RE: Final[re.Pattern[str]] = re.compile(r"^/([A-Za-z])(?=/|$)")
#: UNC and device paths. Resolving one makes the OS contact a network host.
_REMOTE_PATH_RE: Final[re.Pattern[str]] = re.compile(r"^(?:\\\\|//)")
#: Cap on write targets classified per command: each costs a path resolution.
_MAX_SHELL_TARGETS: Final[int] = 50
#: POSIX write commands and how their destination is found.
_POSIX_COPIERS: Final[frozenset[str]] = frozenset({"cp", "mv", "install"})
_POSIX_EVERY_OPERAND: Final[frozenset[str]] = frozenset({"touch", "tee"})
_COMMAND_PREFIXES: Final[frozenset[str]] = frozenset(
    {"sudo", "command", "builtin", "exec", "nohup", "time", "env"}
)
#: PowerShell write cmdlets: the parameter that names the written path, and the
#: positional slot it takes when the parameter name is omitted.
_PS_WRITERS: Final[dict[str, tuple[frozenset[str], int]]] = {
    "out-file": (frozenset({"-filepath", "-path", "-literalpath"}), 0),
    "set-content": (frozenset({"-path", "-literalpath"}), 0),
    "add-content": (frozenset({"-path", "-literalpath"}), 0),
    "new-item": (frozenset({"-path"}), 0),
    "tee-object": (frozenset({"-filepath", "-literalpath"}), 0),
    "copy-item": (frozenset({"-destination"}), 1),
    "move-item": (frozenset({"-destination"}), 1),
}
#: PowerShell switches that take no value (every other parameter takes one).
_PS_SWITCHES: Final[frozenset[str]] = frozenset(
    {
        "-append", "-confirm", "-force", "-noclobber", "-nonewline",
        "-passthru", "-recurse", "-whatif", "-container",
    }
)  # fmt: skip

#: Agent-attribution shapes the git-write reminder checks for (human-only
#: authorship; ``pretooluse-bash.md`` Scan 3). A product named as the subject of
#: a change is not attribution, so only trailer, address, marker and
#: "generated by" forms match. Trailers are checked line by line.
_AGENT_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(?:claude|anthropic|chatgpt|gpt|openai|copilot|cursor|gemini|bard"
    r"|llama|qwen|kimi|moonshot|codex|deepseek|mistral|glm|zhipu|devin|windsurf"
    r"|kiro|trae|antigravity|hermes|opencode|aider|cline|codebuddy|grok)\b"
)
_BOT_ADDRESS_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\[bot\]|-bot@|\bbot@|noreply@[\w.-]*(?:anthropic|openai)\b"
)
_ATTRIBUTION_RES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"(?i)\b(?:generated|written|drafted|authored) (?:with|by) "
        r"(?:\[?claude|an? ai\b|ai\b|chatgpt|copilot|gpt)"
    ),
    re.compile(r"(?i)\bco-authored by an ai\b"),
    re.compile(r"(?i)\[(?:claude|gpt|ai)\]"),
    re.compile(r"(?i)-c\s+user\.email=\S*(?:noreply@\S*(?:anthropic|openai)|bot@)"),
    re.compile("\U0001f916"),
)
#: Plan-structure vocabulary that must not reach a commit message (Scan 1).
_PLAN_STRUCTURE_PHRASES: Final[tuple[str, ...]] = (
    "resumption contract",
    "phase output registry",
    "convention anchors",
)
#: A numeric prefix on a suite-root plan file (``pretooluse-bash.md`` Scan 2).
_SUITE_ROOT_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:\.apothem/plans|\.plans)/[^/\s]+/0\d-[^/\s]+\.md"
)

_EDIT_HEADER_GUARD_MESSAGE: Final[str] = "pretooluse-edit-header-guard.md"
_HEADER_GUARD_MESSAGES: Final[frozenset[str]] = frozenset(
    {
        "pretooluse-write-header-guard.md",
        _EDIT_HEADER_GUARD_MESSAGE,
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


#: Shell tool names a shell-command guard accepts. Claude Code names its tools
#: ``Bash`` and ``PowerShell``; Qwen Code reports the runtime id
#: ``run_shell_command``. Every one carries the command in ``tool_input.command``.
_SHELL_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {"Bash", "PowerShell", "run_shell_command"}
)
_DEPENDENCY_GUARD_MESSAGE: Final[str] = "pretooluse-dependency-guard.md"
_EVAL_GUARD_MESSAGE: Final[str] = "pretooluse-eval-guard.md"
#: Commands that only search, record text or change directory. A shell command
#: made of nothing else never evaluates the text it names, so the eval scan has
#: nothing to find in it.
_SEARCH_COMMANDS: Final[frozenset[str]] = frozenset(
    {"cd", "grep", "egrep", "fgrep", "rg", "git commit", "git grep", "git log"}
)
#: A lone ``&`` (background): the statement after it is a command the split misses.
#: ``&&`` is split earlier and ``2>&1`` / ``&>`` are redirections.
_BACKGROUND_AMP_RE: Final[re.Pattern[str]] = re.compile(r"(?<![>&])&(?![>&])")
# Mirrors the manifest and lockfile set in
# ``hooks/messages/pretooluse-dependency-guard.md`` (Scope); a change to one
# side is mirrored in the other in the same change-set.
_DEPENDENCY_MANIFEST_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:pyproject\.toml|requirements[^/\\]*\.txt|package\.json|Cargo\.toml|go\.mod"
    r"|Gemfile|uv\.lock|poetry\.lock|package-lock\.json|pnpm-lock\.yaml|yarn\.lock"
    r"|Cargo\.lock|go\.sum|Gemfile\.lock)$"
)
# Mirrors the primitive list in ``hooks/messages/pretooluse-eval-guard.md``
# (Trigger / inspected patterns): dynamic evaluation, shell-out with the shell
# switched on, and unsafe deserialization. A member access (``re.compile(``,
# ``regex.exec(``) is excluded by the look-behind, so only the bare primitive
# matches. The call forms need the parenthesis directly after the name, the
# shape every formatter emits, and an argument after it, so prose such as
# ``eval (one-off)`` or ``eval()`` stays quiet; a definition (``def exec(``,
# ``function eval(``, ``fn``, ``fun``, ``func``, ``class Function(``) is not a
# call either. The shell
# ``eval`` is a command word at a statement start (line start, or after ``;``
# ``&`` ``|``) with a quote, ``$`` or backtick later on its line, the forms that
# carry a dynamic string; the window is bounded because an unbounded one is
# quadratic on a long line. An English line that opens with "eval" does not
# match. ``yaml.load`` is safe when ``SafeLoader`` appears in the call's own
# argument span, which may cross lines and one level of nested parentheses. A
# Bash command reaches the scanner whole, heredoc body included: that body is
# file content, so it is scanned like a Write.
_EVAL_PRIMITIVE_RES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"(?<![\w.])(?<!def )(?<!function )(?<!fn )(?<!fun )(?<!func )"
        r"(?:eval|exec|compile)\((?!\))"
    ),
    re.compile(r"(?<![\w.])(?<!class )(?:new\s+)?Function\((?!\))"),
    re.compile(r"(?:^[ \t]*|[;&|]\s*)eval(?=[ \t][^\n]{0,200}[\"'`$])", re.MULTILINE),
    re.compile(r"\bos\.system\s*\("),
    re.compile(r"\bshell\s*=\s*True\b"),
    re.compile(r"\bchild_process\b"),
    re.compile(r"\b(?:pickle|cPickle|marshal|dill)\.loads?\s*\("),
    re.compile(r"\byaml\.unsafe_load\s*\("),
    re.compile(r"\byaml\.load\s*\((?!(?:[^()]|\([^()]*\)){0,400}?SafeLoader)"),
)
# Codex ``apply_patch`` carries its targets inside the patch body.
_PATCH_TARGET_RE: Final[re.Pattern[str]] = re.compile(
    r"^\*\*\* (?:Add|Update) File: (.+?)\s*$", re.MULTILINE
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
    if not payload or payload.get("tool_name") not in _SHELL_TOOL_NAMES:
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


def target_project_root(payload: dict[str, object] | None) -> Path:
    """Return the root of the project the tool call edits.

    The project is the nearest git root above the payload's ``cwd`` (falling back
    to ``$CLAUDE_PROJECT_DIR`` / ``$LLM_PROJECT_DIR``, then the process cwd). It
    is never the tree the hook ships in: a plugin install lives under the
    harness's plugin cache, so anchoring "inside the project" on that tree made
    every write to the project's own ``.apothem/plans/`` look global.
    """
    raw = payload.get("cwd") if payload else None
    if not isinstance(raw, str) or not raw:
        raw = (
            os.environ.get("CLAUDE_PROJECT_DIR")
            or os.environ.get("LLM_PROJECT_DIR")
            or ""
        )
    try:
        return _nearest_git_root(Path(_native_path(raw)) if raw else Path.cwd())
    except (OSError, RuntimeError, ValueError):
        return Path.cwd()


def _native_path(raw: str) -> str:
    """Map a Git Bash drive path (``/c/...``) to its Windows form (``C:/...``)."""
    if os.name == "nt":
        return _MSYS_DRIVE_RE.sub(lambda m: f"{m.group(1).upper()}:", raw, count=1)
    return raw


def _payload_cwd(payload: dict[str, object] | None, fallback: Path) -> Path:
    """The tool call's working directory, the base for relative paths it names."""
    raw = payload.get("cwd") if payload else None
    if isinstance(raw, str) and raw:
        with contextlib.suppress(OSError, RuntimeError, ValueError):
            return Path(_native_path(raw)).resolve()
    return fallback


def _resolve_target(raw: str, base: Path) -> Path | None:
    """Resolve a tool-supplied path against *base*; ``None`` when unresolvable.

    UNC and device paths (a leading double backslash or double slash) are never
    resolved: resolving one makes the OS contact a network host, which can take
    seconds and reaches out from the user's machine on the strength of a string
    in a tool call. They are treated as unresolvable.
    """
    text = raw.strip().strip("\"'")
    if not text or _REMOTE_PATH_RE.match(text):
        return None
    text = os.path.expandvars(_native_path(text))
    if "$" in text or _REMOTE_PATH_RE.match(text):
        return None
    try:
        candidate = Path(text).expanduser()
        if not candidate.is_absolute():
            candidate = base / candidate
        return candidate.resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def _is_inside(target: Path, root: Path) -> bool:
    """True when *target* lies under *root*; both are already resolved."""
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def _in_plans_tree(target: Path) -> bool:
    parts = target.parts
    return ".plans" in parts or any(
        parts[i] == ".apothem" and parts[i + 1] == "plans"
        for i in range(len(parts) - 1)
    )


#: Plans-locality verdicts, named as in ``pretooluse-write-plan-guard.md``.
PLAN_ALLOW: Final[str] = "allow"
PLAN_REDIRECT: Final[str] = "redirect-required"
PLAN_SOFT_FLAG: Final[str] = "soft-flag"
_PLAN_NAME_HINTS: Final[tuple[str, ...]] = ("plan", "notes", "draft")
#: Shared temp locations on POSIX hosts that do not export ``TMPDIR``. They are
#: compared against, never written to.
_POSIX_TEMP_ROOTS: Final[tuple[str, ...]] = (
    "/tmp",  # noqa: S108  # nosec B108 — an exemption root, never written to
    "/private/tmp",
    "/var/tmp",  # noqa: S108  # nosec B108 — an exemption root, never written to
    "/var/folders",
)


def _exempt_roots(payload: dict[str, object] | None) -> list[Path]:
    """Directories where a plan-shaped file outside the project is expected.

    The session scratchpad (``scratchpad_dir`` in the payload) and the system
    temp directories hold working files by design; soft-flagging a ``notes.md``
    there is noise. The OS temp dir counts even when no temp variable is
    exported. Called only when a target is already outside the project, so the
    ``tempfile`` import stays off the common path.
    """
    import tempfile

    raws: list[str] = []
    scratch = payload.get("scratchpad_dir") if payload else None
    if isinstance(scratch, str):
        raws.append(scratch)
    raws.extend(os.environ.get(name, "") for name in ("TMPDIR", "TEMP", "TMP"))
    raws.append(tempfile.gettempdir())
    if os.name != "nt":
        raws.extend(_POSIX_TEMP_ROOTS)
    roots: list[Path] = []
    for raw in raws:
        if raw:
            with contextlib.suppress(OSError, RuntimeError, ValueError):
                roots.append(Path(_native_path(raw)).resolve())
    return roots


def classify_plan_target(
    raw_path: str,
    text: str,
    project_root: Path,
    exempt: list[Path] | Callable[[], list[Path]] | None = None,
    base: Path | None = None,
) -> str:
    """Apply the plans-locality verdict matrix to one write target.

    Inside the project every write is allowed: the canonical
    ``.apothem/plans/`` tree, a legacy ``.plans/`` tree (the session-start
    bootstrap surfaces its ``apothem migrate-workspace`` upgrade), and any other
    project file. Outside it, a plans tree is redirect-required, and a
    plan-named Markdown file or plan-shaped content is soft-flagged unless it
    sits in an exempt working directory. A relative *raw_path* resolves against
    *base* (the tool call's working directory), else against the project root.
    *exempt* may be a list or a zero-argument function, evaluated only when a
    target is outside the project.
    """
    root = project_root.resolve()
    target = _resolve_target(raw_path, base if base is not None else root)
    if target is None or _is_inside(target, root):
        return PLAN_ALLOW
    if _in_plans_tree(target):
        return PLAN_REDIRECT
    roots = exempt() if callable(exempt) else (exempt or [])
    if any(_is_inside(target, exempt_root) for exempt_root in roots):
        return PLAN_ALLOW
    name = target.name.lower()
    if name.endswith(".md") and any(hint in name for hint in _PLAN_NAME_HINTS):
        return PLAN_SOFT_FLAG
    lowered = text.lower()
    if any(marker in lowered for marker in _PLAN_SHAPED_MARKERS):
        return PLAN_SOFT_FLAG
    return PLAN_ALLOW


def _strip_heredoc_bodies(command: str) -> str:
    """Drop heredoc bodies, keeping each opener line (which holds its redirect).

    A heredoc body is data, not shell: a redirect-looking token inside an
    embedded script is not a write, and classifying each such token cost a path
    resolution.
    """
    kept: list[str] = []
    terminator: str | None = None
    strip_tabs = False
    for line in command.split("\n"):
        if terminator is not None:
            if (line.lstrip("\t") if strip_tabs else line).strip() == terminator:
                terminator = None
            continue
        kept.append(line)
        match = _HEREDOC_START_RE.search(line)
        if match:
            terminator = match.group(3)
            strip_tabs = match.group(1) == "-"
    return "\n".join(kept)


def _statement_tokens(statement: str) -> list[str]:
    """Tokenize one shell statement, dropping an unquoted comment tail."""
    tokens: list[str] = _TOKEN_RE.findall(statement)
    for index, token in enumerate(tokens):
        if token.startswith("#"):
            return tokens[:index]
    return tokens


def _command_word(tokens: list[str]) -> int:
    """Index of the command word: past ``VAR=value`` and wrapper prefixes."""
    index = 0
    while index < len(tokens) and (
        tokens[index] in _COMMAND_PREFIXES
        or ("=" in tokens[index] and not tokens[index].startswith(("-", "'", '"')))
    ):
        index += 1
    return index


def _posix_write_operands(name: str, args: list[str]) -> list[str]:
    """Destinations a ``cp``/``mv``/``install``/``touch``/``tee`` call writes."""
    operands: list[str] = []
    target_dir: str | None = None
    index = 0
    while index < len(args):
        token = args[index]
        if _REDIRECT_TOKEN_RE.match(token):
            break  # the rest belongs to a redirection, found separately
        if token in ("-t", "--target-directory") and index + 1 < len(args):
            target_dir = args[index + 1]
            index += 2
            continue
        if token.startswith("--target-directory="):
            target_dir = token.split("=", 1)[1]
        elif not token.startswith("-"):
            operands.append(token)
        index += 1
    if name in _POSIX_EVERY_OPERAND:
        return operands
    if target_dir is not None:
        return [target_dir]
    return operands[-1:] if len(operands) >= 2 else []


def _powershell_write_operands(name: str, args: list[str]) -> list[str]:
    """The path a PowerShell write cmdlet writes, by parameter or by position."""
    path_params, slot = _PS_WRITERS[name]
    positional: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token.startswith("-") and len(token) > 1:
            param, colon, value = token.partition(":")
            param = param.lower()
            if param in path_params:
                if colon:
                    return [value]
                return [args[index + 1]] if index + 1 < len(args) else []
            index += 1 if (colon or param in _PS_SWITCHES) else 2
            continue
        if _REDIRECT_TOKEN_RE.match(token):
            break
        positional.append(token)
        index += 1
    return [positional[slot]] if len(positional) > slot else []


def shell_write_targets(command: str) -> list[str]:
    """Return the paths a shell command writes, de-duplicated and capped.

    Covers the forms ``pretooluse-bash-plan-guard.md`` names: POSIX redirects
    (``>``, ``>>``, ``2>``, ``&>``, ``>|``), ``tee`` and ``touch`` (every
    operand), the destination of ``cp`` / ``mv`` / ``install`` (``-t`` aware),
    and the PowerShell write cmdlets by parameter or position. Heredoc bodies
    and comments are not inspected, null devices are dropped, and at most
    ``_MAX_SHELL_TARGETS`` distinct targets are returned.
    """
    targets: list[str] = []
    for statement in _STATEMENT_SPLIT_RE.split(_strip_heredoc_bodies(command)):
        tokens = _statement_tokens(statement)
        if not tokens:
            continue
        targets.extend(m.group(1) for m in _REDIRECT_RE.finditer(" ".join(tokens)))
        word = _command_word(tokens)
        if word >= len(tokens):
            continue
        name = tokens[word].lower()
        args = tokens[word + 1 :]
        if name in _POSIX_COPIERS or name in _POSIX_EVERY_OPERAND:
            targets.extend(_posix_write_operands(name, args))
        elif name in _PS_WRITERS:
            targets.extend(_powershell_write_operands(name, args))
    unique: list[str] = []
    for target in targets:
        if (
            target.strip("\"'") in _NULL_TARGETS
            or target.startswith("&")
            or target in unique
        ):
            continue
        unique.append(target)
        if len(unique) >= _MAX_SHELL_TARGETS:
            break
    return unique


def _plan_terms(text: str) -> list[str]:
    """Plan-internal identifiers in *text*, standard ids excluded, first-seen order."""
    found: list[str] = []
    for pattern in _PLAN_TERM_RES:
        for match in pattern.finditer(text):
            token = match.group(0)
            if token.split("-", 1)[0] in _STANDARD_ID_PREFIXES or token in found:
                continue
            found.append(token)
    return found


def _has_agent_attribution(command: str) -> bool:
    """True for an agent trailer, address, marker or "generated by" line."""
    for line in command.splitlines():
        at = line.lower().find("co-authored-by:")
        if at >= 0:
            rest = line[at + len("co-authored-by:") :]
            if _AGENT_NAME_RE.search(rest) or _BOT_ADDRESS_RE.search(rest):
                return True
    return any(pattern.search(command) for pattern in _ATTRIBUTION_RES)


def _git_write_findings(command: str) -> list[str]:
    """Mechanical scans of a git-write command (``pretooluse-bash.md`` Scans 1-3)."""
    findings: list[str] = []
    terms = [f"`{term}`" for term in _plan_terms(command)]
    lowered = command.lower()
    terms.extend(
        f"'{phrase}'" for phrase in _PLAN_STRUCTURE_PHRASES if phrase in lowered
    )
    if terms:
        findings.append("plan-internal term(s) " + ", ".join(terms[:5]))
    prefixed = _SUITE_ROOT_PREFIX_RE.findall(command.replace("\\", "/"))
    if prefixed:
        findings.append(
            "numeric prefix on suite-root plan file(s) " + ", ".join(prefixed[:3])
        )
    if _has_agent_attribution(command):
        findings.append(
            "agent-attribution text (trailer, address, marker or 'generated by' line)"
        )
    return findings


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


def _tool_string(tool_input: dict[str, object], key: str) -> str:
    value = tool_input.get(key)
    return value if isinstance(value, str) else ""


def _missing_header(
    basename: str,
    path: str,
    tool_input: dict[str, object],
    root: Path,
    base: Path,
) -> bool:
    """True when this Write or Edit leaves *path* without the canonical header.

    The header is Apothem's own convention, so only a project that follows it is
    judged: a git project at *root* that carries the header fixture. Of its files,
    only one inside the project is checked, against the exemption globs as the
    project-relative path; a harness config directory such as ``~/.claude`` is not
    a project, and the conformity gate covers it. The checker is ``header_check``,
    standard library only, so it runs where the ``apothem`` package is not
    importable (a plugin install) without paying for that import.
    """
    if not project_adopts_header(root):
        return False
    target = _resolve_target(path, base) if path else None
    if target is None or not _is_inside(target, root):
        return False
    rel_path = target.relative_to(root).as_posix()
    try:
        if basename == _EDIT_HEADER_GUARD_MESSAGE:
            return edit_lacks_header(
                rel_path,
                target,
                _tool_string(tool_input, "old_string"),
                _tool_string(tool_input, "new_string"),
                tool_input.get("replace_all") is True,
            )
        return write_lacks_header(rel_path, _tool_string(tool_input, "content"))
    except Exception as exc:  # code-craft-boundary: broad-except; fail-closed guard.
        # A defect in the checker is not a header-absent verdict, but it must not
        # mute the guard either: fail CLOSED and name the failing class so the
        # defect is distinguishable from a true verdict rather than silently masked.
        _logger.warning(
            "header_check raised %s for %s; failing closed",
            type(exc).__name__,
            path,
        )
        return True


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
    project_root = root if root is not None else target_project_root(payload)
    return guard_values(event_name, context_file, payload, project_root) is None


def guard_values(
    event_name: str,
    context_file: str,
    payload: dict[str, object] | None,
    project_root: Path,
) -> dict[str, str] | None:
    """Decide whether a PreToolUse guard fires, and with which findings.

    Returns ``None`` when the guard stays silent, else the placeholder values the
    message's ``## Advisory`` template is filled with (an empty dict for a message
    no guard owns, which always emits). *project_root* is the project the tool
    call edits (:func:`target_project_root`), not the hook's install tree.
    """
    if event_name != "PreToolUse":
        return {}
    basename = _context_basename(context_file)
    tool_input = _tool_input(payload)
    path = _path_from_tool_input(tool_input)
    text = _text_from_tool_input(tool_input)
    shown = path or "this file"
    try:
        root = project_root.resolve()
    except (OSError, RuntimeError, ValueError):
        root = project_root
    base = _payload_cwd(payload, root)
    # A Codex ``apply_patch`` call names its files inside the patch body.
    targets = [path] if path else _PATCH_TARGET_RE.findall(text)
    plans_dir = str(root / ".apothem" / "plans")
    if basename in _CODEBASE_ISOLATION_MESSAGES:
        # Only the project's own files are product artifacts. A write outside the
        # project (harness config, memory, the session scratchpad) or into its
        # gitignored Apothem working tree (plans, memory, scratch) is where plan
        # identifiers belong.
        resolved = [_resolve_target(t, base) for t in targets]
        product = [
            r
            for r in resolved
            if r is None
            or (_is_inside(r, root) and not _is_inside(r, root / ".apothem"))
        ]
        if targets and not product:
            return None
        terms = _plan_terms(text)
        if not terms:
            return None
        where = shown if path else ", ".join(targets[:3]) or "this file"
        return {"path": where, "terms": ", ".join(f"`{t}`" for t in terms[:5])}
    if basename == "pretooluse-bash-plan-guard.md":
        flagged = [
            (target, verdict)
            for target in shell_write_targets(text)
            if (
                verdict := classify_plan_target(
                    target, "", root, lambda: _exempt_roots(payload), base
                )
            )
            != PLAN_ALLOW
        ]
        if not flagged:
            return None
        return {
            "targets": ", ".join(f"`{t}`" for t, _ in flagged[:3]),
            "verdict": flagged[0][1],
            "plans_dir": plans_dir,
        }
    if basename in _PLAN_GUARD_MESSAGES:
        for target in targets:
            verdict = classify_plan_target(
                target, text, root, lambda: _exempt_roots(payload), base
            )
            if verdict != PLAN_ALLOW:
                return {"path": target, "verdict": verdict, "plans_dir": plans_dir}
        return None
    if basename in _HEADER_GUARD_MESSAGES:
        missing = _missing_header(basename, path, tool_input, root, base)
        return {"path": shown} if missing else None
    if basename == _DEPENDENCY_GUARD_MESSAGE:
        return {"path": shown} if _touches_dependency_manifest(path, text) else None
    if basename == _EVAL_GUARD_MESSAGE:
        if _only_searches(_tool_string(tool_input, "command")):
            return None
        found = _eval_primitives(text)
        if not found:
            return None
        return {
            "path": shown if path else "this command",
            "primitives": ", ".join(found[:3]),
        }
    if basename == "pretooluse-bash.md":
        findings = _git_write_findings(text) if _command_has_git_trigger(text) else []
        return {"findings": "; ".join(findings)} if findings else None
    return {}


def _touches_dependency_manifest(path: str, text: str) -> bool:
    """True when the write targets a dependency manifest or lockfile.

    The target comes from the tool input's path, or, for a Codex ``apply_patch``
    payload that names its files inside the patch body, from each
    ``*** Add File:`` / ``*** Update File:`` line.
    """
    targets = [path] if path else _PATCH_TARGET_RE.findall(text)
    return any(
        _DEPENDENCY_MANIFEST_RE.match(Path(target.replace("\\", "/")).name)
        for target in targets
        if target
    )


def _only_searches(command: str) -> bool:
    """True when every statement of a shell *command* is a search, a commit or a ``cd``.

    Such a command names ``eval(`` as data: a pattern to find, a message to record.
    The test is conservative, because a command substitution, a backtick, a
    here-document or a background ``&`` can run or hide a statement the split does
    not see, and a command word outside :data:`_SEARCH_COMMANDS` is code to scan.
    """
    if "$(" in command or "`" in command or "<<" in command:
        return False
    searches = False
    for statement in _STATEMENT_SPLIT_RE.split(command):
        tokens = _statement_tokens(statement)
        if not tokens:
            continue
        if any(t[0] not in "\"'" and _BACKGROUND_AMP_RE.search(t) for t in tokens):
            return False
        word = _command_word(tokens)
        name = tokens[word] if word < len(tokens) else ""
        if name == "git" and word + 1 < len(tokens):
            name = f"git {tokens[word + 1]}"
        if name not in _SEARCH_COMMANDS:
            return False
        searches = True
    return searches


def _has_eval_primitive(text: str) -> bool:
    """True when *text* contains a dynamic-eval or unsafe-deserialization primitive."""
    return bool(_eval_primitives(text))


def _eval_primitives(text: str) -> list[str]:
    """The distinct eval / unsafe-deserialization constructs in *text*."""
    found: list[str] = []
    for pattern in _EVAL_PRIMITIVE_RES:
        # A few matches per pattern are enough to report; scanning every match
        # of a lookahead pattern over a large file is quadratic.
        for match in itertools.islice(pattern.finditer(text or ""), 3):
            construct = match.group(0).strip(" \t\r\n;&|")
            token = f"`{construct}`"
            if token not in found:
                found.append(token)
        if len(found) >= 3:
            break
    return found


def _leaks_plan_terms(text: str) -> bool:
    """True when *text* carries a plan-internal identifier that must not ship.

    Scans the proposed content for the bracketed task/mandate id shape and the
    phase-campaign name shape. Empty text (no content to inspect) never trips
    the guard, so a bare Write of an empty file stays silent.
    """
    return bool(_plan_terms(text or ""))


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
    """Read one context file + stdin, emit the hook envelope."""
    run_hook_mode_multi(event_name, [context_file], quiet, root)


def message_context(
    event_name: str,
    context_file: str,
    payload: dict[str, object] | None,
    root: Path,
    project_root: Path,
) -> str:
    """Return the text one message contributes for this tool call ("" when silent).

    *root* anchors relative message paths (the hook's install tree);
    *project_root* is the project the tool call edits. A firing guard whose
    message has an ``## Advisory`` section contributes only that template, filled
    with the findings and closed by a pointer to the full procedure; a message
    without one contributes its whole stripped body.
    """
    resolved = resolve_context_path(context_file, root)
    if resolved is None:
        _logger.warning("Refusing context path outside root: %s", context_file)
        return ""
    try:
        raw = resolved.read_text(encoding="utf-8") if resolved.is_file() else ""
    except OSError as exc:
        _logger.debug("Context file unreadable: %s", exc)
        return ""
    message = strip_maintainer_text(raw)
    if not message or should_suppress_bash_hook(event_name, context_file, payload):
        return ""
    values = guard_values(event_name, context_file, payload, project_root)
    if values is None:
        return ""
    template = advisory_section(raw)
    if template is None:
        return message
    filled = fill_placeholders(template, {"message": str(resolved), **values})
    return f"{filled}\nFull procedure: {resolved}"


def run_hook_mode_multi(
    event_name: str,
    context_files: list[str],
    quiet: bool,
    root: Path,
) -> None:
    """Evaluate several messages against one stdin payload; emit one envelope.

    One process per hook event instead of one per message: the payload is read
    once, every guard runs in-process, and the advisories that fire are joined
    under a single metadata prefix. A missing, empty or silent message
    contributes nothing; when nothing fires the envelope is empty.
    """
    payload = read_hook_stdin()
    project_root = target_project_root(payload)
    parts = [
        text
        for context_file in context_files
        if (
            text := message_context(
                event_name, context_file, payload, root, project_root
            )
        )
    ]
    if not parts:
        emit_hook_envelope(event_name, "", quiet)
        return
    combined = compose_context("\n\n".join(parts), payload)
    emit_hook_envelope(event_name, normalize_ascii(combined), quiet)


def run_diagnostic_mode(root: Path) -> None:
    """Print a human-readable ecosystem summary.

    Uses ``print`` deliberately: this is the diagnostic CLI surface, not
    operational logging. ``logging`` would route through handlers that the
    CLI runner doesn't necessarily configure.
    """
    from datetime import datetime, timezone

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
    import argparse

    parser = argparse.ArgumentParser(
        prog="emit_hook_context",
        description="Emit hook context as structured JSON.",
    )
    parser.add_argument("--hook-event-name", "-n", default="")
    parser.add_argument("--context-file", "-c", action="append", default=[])
    parser.add_argument("--quiet", "-q", action="store_true")
    return parser.parse_args(argv)


def _context_root() -> Path:
    """Return the tree relative message paths resolve against (the install tree)."""
    from resolve_root import Mode, resolve_project_root

    root = resolve_project_root(Mode.HOOKS, script_path=Path(__file__))
    return root if root is not None else Path(__file__).resolve().parent.parent


def run_hook_entry(event_name: str, context_files: list[str], quiet: bool) -> None:
    """Hook-mode entry for the dispatcher: no argument parsing, fail-open.

    The dispatcher already knows the event and the messages, so it calls this
    directly rather than re-parsing an argv. Absolute message paths (what every
    shipped hook configuration passes) need no root search, which keeps the
    root resolver and its imports off the per-tool-call path.
    """
    try:
        files = [c for c in context_files if c]
        if all(Path(c).is_absolute() for c in files):
            root = Path(__file__).resolve().parent.parent
        else:
            root = _context_root()
        run_hook_mode_multi(event_name, files, quiet, root)
    except Exception as exc:
        emit_failure_envelope(event_name, str(exc))


def main(argv: list[str] | None = None) -> None:
    """Entry point. Guarantees a valid JSON envelope on any failure.

    ``--context-file`` may repeat: every message is evaluated against the one
    stdin payload and the results share a single envelope.
    """
    args = parse_args(argv)
    try:
        root = _context_root()
        context_files = [c for c in args.context_file if c]
        if not args.hook_event_name or not context_files:
            run_diagnostic_mode(root)
            return
        run_hook_mode_multi(args.hook_event_name, context_files, args.quiet, root)
    except Exception as exc:
        emit_failure_envelope(args.hook_event_name, str(exc))


if __name__ == "__main__":
    main()
