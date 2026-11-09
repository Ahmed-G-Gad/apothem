# SPDX-License-Identifier: MIT

"""The Apothem rules file each OpenClaw agent workspace gets.

OpenClaw puts six files from an agent's workspace into its system prompt, and
its bundled ``bootstrap-extra-files`` hook adds further files that carry one of
those six names. The install writes one such file, ``apothem/AGENTS.md``, into
every workspace it finds, and registers it with the hook (see
:mod:`apothem.harnesses.open_claw.materializer`). The file holds the profile's
managed block and the pointer to the support tree's rule index, so OpenClaw
reaches the whole rule set. It is a managed-block file: the install record
lists it, an uninstall strips the block and deletes the file it leaves empty,
and ``apothem status`` reports an edited block as drift.

The workspace's own ``AGENTS.md`` is never touched: OpenClaw seeds it and the
agent edits it.

Workspaces are found as OpenClaw resolves them (source
``src/agents/agent-scope-config.ts:511-535`` and
``src/agents/workspace-default-path.ts`` at commit ``89ba6b0f12ff``, read
2026-11-08; docs ``gateway/config-agents/workspace-and-bootstrap``, read
2026-11-09). Only folders that exist and sit inside the home directory, reached
without a link, are written: a workspace OpenClaw has not created yet gets its
file from the next ``apothem update``. A file an earlier install wrote that
this install no longer writes (its workspace moved, or the file no longer
fits) loses its managed block on the next install, update or uninstall.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import MaterializationResult
from apothem.harnesses._shared.install_driver_pathsafety import _unsafe_symlink
from apothem.harnesses._shared.install_driver_types import _path_text
from apothem.harnesses.open_claw.materializer import (
    ENTRY_PATH,
    PATTERN_KEYS,
    RULES_FILE_RELATIVE,
    SKILLS_DIRECTORY,
)
from apothem.lib import install_ledger, lenient_json
from apothem.lib.harness_materializer import extract_managed_block, merge_managed_block

#: OpenClaw's default limits on what it injects (``bootstrapMaxChars`` and
#: ``bootstrapTotalMaxChars``; source
#: ``src/agents/embedded-agent-helpers/bootstrap.ts:87-91, 125-156``).
DEFAULT_FILE_MAX_CHARS: Final[int] = 20_000
DEFAULT_TOTAL_MAX_CHARS: Final[int] = 60_000

#: ``USER.md`` keeps a fixed cap whatever the per-file limit is.
_USER_FILE_MAX_CHARS: Final[int] = 4_000

#: Below this much room left in the total, OpenClaw skips a file outright.
_MIN_FILE_BUDGET_CHARS: Final[int] = 64

#: The six files OpenClaw injects before any extra file, in prompt order.
CANONICAL_FILES: Final[tuple[str, ...]] = (
    "AGENTS.md",
    "SOUL.md",
    "IDENTITY.md",
    "USER.md",
    "BOOTSTRAP.md",
    "MEMORY.md",
)

#: The canonical files OpenClaw replaces with a ``[MISSING] Expected at:
#: <path>`` marker when absent (``bootstrap.ts:406-412``); only a missing
#: ``USER.md`` or ``MEMORY.md`` is left out.
_MARKED_WHEN_MISSING: Final[tuple[str, ...]] = (
    "AGENTS.md",
    "SOUL.md",
    "IDENTITY.md",
    "BOOTSTRAP.md",
)

#: OpenClaw's agent-id normalization (``packages/normalization-core/src/
#: agent-id.ts:3-30``): lowercase; characters other than ``a-z0-9_-`` become
#: ``-``; leading and trailing dashes go; at most 64 characters; an id with
#: nothing left is the default id.
_VALID_ID: Final[re.Pattern[str]] = re.compile(
    r"^[a-z0-9][a-z0-9_-]{0,63}$", re.IGNORECASE | re.ASCII
)
_INVALID_ID_CHARS: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9_-]+")
_DEFAULT_AGENT_ID: Final[str] = "main"

#: Characters that make OpenClaw treat a hook path as a glob
#: (``hasGlobPattern``, ``workspace-bootstrap-policy.ts:59-62``); square
#: brackets stay literal.
_GLOB_MARKS: Final[str] = "?*{}"

_HARNESS_NAME: Final[str] = "open_claw"
_HARNESS_ID: Final[str] = "open-claw"
_OPERATION: Final[str] = "open_claw_rules_file"
_RETIRE: Final[str] = "retire_anchor"
_RULES_PARTS: Final[tuple[str, ...]] = tuple(RULES_FILE_RELATIVE.split("/"))


@dataclass(frozen=True)
class Workspace:
    """One workspace and the ``agents.entries`` ids that use it.

    ``agent_ids`` decides which per-entry size limits apply; with none, the
    ``agents.defaults`` limits do.
    """

    path: Path
    agent_ids: tuple[str, ...] = ()

    @property
    def rules_file(self) -> Path:
        """Return where the Apothem rules file sits in this workspace."""
        return self.path / RULES_FILE_RELATIVE


@dataclass(frozen=True)
class Workspaces:
    """The workspaces an install writes into, and the ones it passes over.

    ``missing`` are workspaces OpenClaw has not created yet: the normal state
    before OpenClaw is set up. The install reports nothing for them (there is
    nothing to write, so ``apothem diff`` shows no pending change); once
    OpenClaw creates one, ``apothem verify`` fails until an update fills it.
    ``notes`` describe configured workspaces the install cannot use.
    """

    found: tuple[Workspace, ...]
    notes: tuple[str, ...]
    missing: tuple[Workspace, ...] = ()


@dataclass(frozen=True)
class Limits:
    """OpenClaw's character limits for one workspace."""

    file_max: int = DEFAULT_FILE_MAX_CHARS
    total_max: int = DEFAULT_TOTAL_MAX_CHARS


@dataclass
class _Candidates:
    """Workspace paths in order, each with the entry ids that use it."""

    order: list[Path] = field(default_factory=list)
    ids: dict[Path, list[str]] = field(default_factory=dict)

    def add(self, path: Path, agent_id: str | None) -> None:
        if path not in self.ids:
            self.order.append(path)
            self.ids[path] = []
        if agent_id is not None:
            self.ids[path].append(agent_id)


def read_config(config: Path) -> object:
    """Return the parsed ``openclaw.json`` at *config*, or ``None``.

    The file is read as JSON5, the dialect OpenClaw reads. A missing or
    unreadable file reads as ``None``: the install then refuses or creates it
    through the shared native-config path, which reports why.
    """
    try:
        return lenient_json.loads(config.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, lenient_json.LenientJSONError):
        return None


def editable(config: Path) -> bool:
    """Return False when ``openclaw.json`` parses only as JSON5.

    Apothem rewrites the file as plain JSON, which would drop comments, so the
    shared write path refuses any change to such a file. A missing or
    unparseable file counts as editable: the shared path reports it.
    """
    try:
        json.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return read_config(config) is None
    return True


def json5_leftovers(config: Path) -> tuple[MaterializationResult, ...]:
    """Return an error naming Apothem's entries left in a JSON5 ``openclaw.json``.

    Uninstall cannot take them out without losing the operator's comments, so
    the shared strip leaves the file alone. Reporting it as an error keeps the
    install record and tells the operator what to remove by hand before
    running the uninstall again.
    """
    if not config.is_file() or editable(config):
        return ()
    parsed = read_config(config)
    left: list[str] = []
    dirs = _mapping(parsed, "skills", "load").get("extraDirs")
    if isinstance(dirs, list) and SKILLS_DIRECTORY in dirs:
        left.append(f'"{SKILLS_DIRECTORY}" from skills.load.extraDirs')
    entry = _mapping(parsed, *ENTRY_PATH)
    for key in PATTERN_KEYS:
        items = entry.get(key)
        if isinstance(items, list) and RULES_FILE_RELATIVE in items:
            left.append(
                f'"{RULES_FILE_RELATIVE}" from hooks.internal.entries.{ENTRY_PATH[-1]}'
                f".{key} (and the entry, if nothing of yours is left in it)"
            )
    if not left:
        return ()
    return (
        MaterializationResult(
            outcome="error",
            operation=_RETIRE,
            path=str(config),
            message=(
                "openclaw.json holds comments, a byte-order mark or other JSON5 "
                "syntax, which Apothem "
                "cannot keep when it rewrites the file, so it leaves its "
                "entries "
                f"there. Remove {' and '.join(left)} by hand, then run the uninstall "
                "again."
            ),
        ),
    )


def chars(text: str) -> int:
    """Return the length of *text* as OpenClaw counts it, in UTF-16 code units."""
    return len(text.encode("utf-16-le", errors="surrogatepass")) // 2


def _raw_text(path: Path) -> str | None:
    """Return *path*'s text as OpenClaw reads it, or ``None`` when unreadable.

    Line endings are kept as they are (``\\r\\n`` counts two characters) and
    bytes that are not UTF-8 become U+FFFD, as Node's UTF-8 decoding does.
    """
    try:
        return path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None


def _mapping(value: object, *keys: str) -> dict[str, Any]:
    """Return the mapping at *keys* below *value*, or an empty mapping."""
    for key in keys:
        if not isinstance(value, dict):
            return {}
        value = value.get(key)
    return value if isinstance(value, dict) else {}


def _text(value: object) -> str | None:
    """Return *value* stripped when it is a non-empty string."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _user_path(value: str, home: Path) -> Path | None:
    """Return *value* as an absolute path, expanding a leading ``~``."""
    if value == "~" or value.startswith(("~/", "~\\")):
        return home / value[2:]
    path = Path(value)
    return path if path.is_absolute() else None


def normalize_agent_id(value: object) -> str:
    """Return *value* as OpenClaw spells an agent id in folder names.

    A value that is not a string (an ``agents.list`` item without ``id``) is
    the default id, as ``normalizeAgentId(undefined)`` gives.
    """
    if not isinstance(value, str):
        return _DEFAULT_AGENT_ID
    trimmed = value.strip()
    lowered = trimmed.lower()
    if _VALID_ID.match(trimmed):
        return lowered
    cleaned = _INVALID_ID_CHARS.sub("-", lowered).strip("-")[:64]
    return cleaned or _DEFAULT_AGENT_ID


def roster_list(config: object) -> list[tuple[str, dict[str, Any]]]:
    """Return the configured entries with normalized ids, as OpenClaw lists them.

    ``agents.entries`` (a mapping keyed by id) when that key is present, even
    as ``null``, else the older ``agents.list`` (an array of objects, each
    named by its ``id``), which OpenClaw still reads (``agent-roster.ts:89-126,
    138-154``). Values that are not mappings are not entries. Duplicates are
    kept, as OpenClaw keeps them when it counts entries.
    """
    agents = _mapping(config, "agents")
    if "entries" in agents:
        return [
            (normalize_agent_id(str(agent_id)), entry)
            for agent_id, entry in _mapping(agents, "entries").items()
            if isinstance(entry, dict)
        ]
    listed = agents.get("list")
    if not isinstance(listed, list):
        return []
    # Any non-null object counts, arrays included (``entry !== null &&
    # typeof entry === "object"``); one without a string ``id`` is ``main``.
    return [
        (normalize_agent_id(entry.get("id")), entry)
        if isinstance(entry, dict)
        else (normalize_agent_id(None), {})
        for entry in listed
        if isinstance(entry, dict | list)
    ]


def roster(config: object) -> dict[str, dict[str, Any]]:
    """Return the configured entries by normalized id; the first of a duplicate wins."""
    found: dict[str, dict[str, Any]] = {}
    for agent_id, entry in roster_list(config):
        found.setdefault(agent_id, entry)
    return found


def default_owner(config: object) -> str | None:
    """Return the entry that owns the default workspace, if any.

    The one entry marked ``default: true`` (unless ``agents.ownership`` is
    ``"explicit"``), else a sole entry (``agent-roster.ts:217-239``); entries
    are counted as OpenClaw counts them, duplicates included.
    """
    listed = roster_list(config)
    if _mapping(config, "agents").get("ownership") != "explicit":
        marked = [
            agent_id for agent_id, entry in listed if entry.get("default") is True
        ]
        if len(marked) == 1:
            return marked[0]
    if len(listed) == 1:
        return listed[0][0]
    return None


def candidate_workspaces(
    config: object, home: Path, env: Mapping[str, str] | None = None
) -> tuple[list[Workspace], list[str]]:
    """Return every workspace *config* names, and notes on unusable ones.

    The default workspace is ``agents.defaults.workspace``, else
    ``OPENCLAW_WORKSPACE_DIR``, else ``~/.openclaw/workspace``. An entry with
    its own ``workspace`` uses it. The entry that owns the default workspace
    (:func:`default_owner`) uses it directly when it has none; any other entry
    without one uses ``<agents.defaults.workspace>/<id>``, else
    ``~/.openclaw/workspace-<id>``, with the id normalized as OpenClaw does.
    The default workspace is always a candidate.
    """
    environ = os.environ if env is None else env
    notes: list[str] = []
    found = _Candidates()
    defaults_workspace = _text(_mapping(config, "agents", "defaults").get("workspace"))
    from_env = _text(environ.get("OPENCLAW_WORKSPACE_DIR"))
    default: str | None = defaults_workspace or "~/.openclaw/workspace"
    if defaults_workspace is None and from_env is not None:
        # OpenClaw takes the variable as given (``path.resolve``): no ``~``
        # expansion, and a relative value depends on its working folder.
        if Path(from_env).is_absolute():
            default = from_env
        else:
            default = None
            notes.append(
                f"OPENCLAW_WORKSPACE_DIR {from_env!r} is not an absolute path, so "
                "the default workspace depends on the folder OpenClaw runs in; "
                "skipped"
            )
    entries = roster(config)
    owner = default_owner(config)
    raw: list[tuple[str, str | None]] = [] if default is None else [(default, None)]
    for agent_id, entry in entries.items():
        own = _text(entry.get("workspace"))
        if own is not None:
            raw.append((own, agent_id))
        elif agent_id == owner:
            if default is not None:
                raw.append((default, agent_id))
        elif defaults_workspace is not None:
            raw.append((f"{defaults_workspace.rstrip('/')}/{agent_id}", agent_id))
        else:
            raw.append((f"~/.openclaw/workspace-{agent_id}", agent_id))
    for value, owner in raw:
        path = _user_path(value, home)
        if path is None:
            notes.append(f"workspace {value!r} is not an absolute path; skipped")
        else:
            found.add(path, owner)
    workspaces = [Workspace(path, tuple(found.ids[path])) for path in found.order]
    return workspaces, notes


def find_workspaces(
    config: object, home: Path, env: Mapping[str, str] | None = None
) -> Workspaces:
    """Return the workspaces to write into: existing folders inside *home*.

    A workspace reached through a link is skipped: Apothem never writes through
    a link (the shared path-safety rule), so it reports that once here instead
    of failing on every run. So is a workspace whose ``apothem`` folder is
    itself another workspace: its rules file would be that workspace's own
    ``AGENTS.md``.
    """
    candidates, notes = candidate_workspaces(config, home, env)
    others = {_key(workspace.path) for workspace in candidates}
    found: list[Workspace] = []
    missing: list[Workspace] = []
    resolved_home = home.resolve()
    for workspace in candidates:
        path = workspace.path
        link = _unsafe_symlink(workspace.rules_file, home)
        if link is not None:
            notes.append(
                f"workspace {path} is reached through a link ({link}); Apothem "
                "writes nothing through a link, so it is skipped"
            )
        elif not path.resolve().is_relative_to(resolved_home):
            notes.append(f"workspace {path} is outside the home directory; skipped")
        elif path.exists() and not path.is_dir():
            notes.append(f"workspace {path} is not a folder; skipped")
        elif workspace.rules_file.exists() and not workspace.rules_file.is_file():
            notes.append(
                f"{workspace.rules_file} is not a file, so Apothem cannot write its "
                "rules file there; skipped"
            )
        elif _key(workspace.rules_file.parent) in others:
            notes.append(
                f"workspace {path} holds another workspace at "
                f"{workspace.rules_file.parent}, whose own AGENTS.md the rules "
                "file would be; skipped"
            )
        elif not path.is_dir():
            missing.append(workspace)
        else:
            found.append(workspace)
    return Workspaces(tuple(found), tuple(notes), tuple(missing))


def _positive(value: object) -> int | None:
    """Return *value* floored, as OpenClaw takes a limit, or ``None``.

    A positive finite number is floored (``0.5`` gives ``0``, a limit no file
    meets); anything else is ``None``, which means the built-in default.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if not math.isfinite(value) or value <= 0:
        return None
    return math.floor(value)


def limits_for(config: object, agent_ids: Iterable[str]) -> Limits:
    """Return the limits that apply to a workspace the *agent_ids* use.

    As OpenClaw resolves them (``bootstrap.ts:125-139``): an entry's own value
    when it sets one, else the ``agents.defaults`` value; a value that is not
    a positive number gives the built-in default, not the next level. When
    several entries share a workspace, the smallest limit counts, so the file
    fits every one of them.
    """
    defaults = _mapping(config, "agents", "defaults")
    entries = roster(config)

    def resolve(key: str, fallback: int) -> int:
        def one(raw: object) -> int:
            value = _positive(raw)
            return fallback if value is None else value

        values = []
        for agent_id in agent_ids:
            own = entries.get(agent_id, {}).get(key)
            values.append(one(defaults.get(key) if own is None else own))
        return min(values) if values else one(defaults.get(key))

    return Limits(
        resolve("bootstrapMaxChars", DEFAULT_FILE_MAX_CHARS),
        resolve("bootstrapTotalMaxChars", DEFAULT_TOTAL_MAX_CHARS),
    )


def _expand_braces(pattern: str) -> list[str]:
    """Return *pattern* with its ``{a,b}`` groups expanded, nested ones too.

    A group without a top-level comma stays literal, as in minimatch. Numeric
    and letter ranges (``{a..c}``) are not expanded.
    """
    start = pattern.find("{")
    while start >= 0:
        depth, options, piece = 0, [], start + 1
        for index in range(start, len(pattern)):
            char = pattern[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    options.append(pattern[piece:index])
                    if len(options) > 1:
                        head, tail = pattern[:start], pattern[index + 1 :]
                        return [
                            expanded
                            for option in options
                            for expanded in _expand_braces(head + option + tail)
                        ]
                    break
            elif char == "," and depth == 1:
                options.append(pattern[piece:index])
                piece = index + 1
        start = pattern.find("{", start + 1)
    return [pattern]


def _matches(workspace: Path, pattern: str) -> list[Path]:
    """Return the files *pattern* names in *workspace*, as OpenClaw reads it.

    A pattern without ``?``, ``*``, ``{`` or ``}`` is a literal path, square
    brackets included. Otherwise braces are expanded and each result is
    matched with Python's glob, square brackets kept literal; this is close
    to, but not the same as, OpenClaw's minimatch.
    """
    if Path(pattern).is_absolute() or Path(pattern).drive or Path(pattern).root:
        return []
    if not any(mark in pattern for mark in _GLOB_MARKS):
        return [workspace / pattern]
    found: list[Path] = []
    for option in _expand_braces(pattern):
        if not any(mark in option for mark in "?*"):
            found.append(workspace / option)
            continue
        literal = option.replace("[", "[[]")
        try:
            found.extend(sorted(workspace.glob(literal)))
        except (ValueError, OSError, NotImplementedError):
            continue
    return found


def operator_extras(config: object, workspace: Path) -> list[Path]:
    """Return the operator's extra bootstrap files the hook loads in *workspace*.

    They come from the list the hook reads (the first non-empty of ``paths``,
    ``patterns`` and ``files``) and load before Apothem's path, which comes
    last. Only files named like one of the six bootstrap files count; the six
    at the workspace root are counted once, as the canonical files, and the
    Apothem rules file never counts against itself.
    """
    entry = _mapping(config, *ENTRY_PATH)
    patterns: list[str] = []
    for key in PATTERN_KEYS:
        items = entry.get(key)
        if isinstance(items, list) and items:
            patterns = [
                item
                for item in items
                if isinstance(item, str)
                and item.strip()
                and item != RULES_FILE_RELATIVE
            ]
            break
    root = workspace.resolve()
    skip = {root / name for name in CANONICAL_FILES} | {
        (workspace / RULES_FILE_RELATIVE).resolve()
    }
    seen: list[Path] = []
    for pattern in patterns:
        for match in _matches(workspace, pattern):
            resolved = match.resolve()
            if (
                match.name in CANONICAL_FILES
                and match.is_file()
                and resolved.is_relative_to(root)
                and resolved not in skip
                and resolved not in seen
            ):
                seen.append(resolved)
    return seen


def used_chars(config: object, workspace: Path, limits: Limits) -> int:
    """Return how much of the total the files loaded before the rules file take.

    The six canonical files (each capped at the per-file limit, ``USER.md`` at
    4,000), the ``[MISSING]`` marker OpenClaw puts in for an absent
    ``AGENTS.md``, ``SOUL.md``, ``IDENTITY.md`` or ``BOOTSTRAP.md``, and the
    operator's extra files from the same hook entry. OpenClaw trims trailing
    whitespace (``trimEnd``) before it counts a file, so counting it here, as
    this does, errs on the side of refusing.
    """
    used = 0
    for name in CANONICAL_FILES:
        path = workspace / name
        text = _raw_text(path) if path.is_file() else None
        if text is None:
            if name in _MARKED_WHEN_MISSING:
                used += chars(f"[MISSING] Expected at: {path}")
            continue
        cap = limits.file_max
        if name == "USER.md":
            cap = min(cap, _USER_FILE_MAX_CHARS)
        used += min(chars(text), cap)
    for extra in operator_extras(config, workspace):
        text = _raw_text(extra)
        if text is not None:
            used += min(chars(text), limits.file_max)
    return used


def _warning(target: Path, message: str) -> MaterializationResult:
    """Return a warning result about *target*."""
    return MaterializationResult(
        outcome="warning", operation=_OPERATION, path=str(target), message=message
    )


def _error(target: Path, message: str) -> MaterializationResult:
    """Return an error result about *target*."""
    return MaterializationResult(
        outcome="error", operation=_RETIRE, path=str(target), message=message
    )


def file_text(workspace: Workspace, body: str) -> str:
    """Return the rules file as the install would leave it in *workspace*.

    The managed block merged into what the file holds now, so text the
    operator keeps beside the block counts against the limits too.
    """
    existing = (
        _raw_text(workspace.rules_file) if workspace.rules_file.is_file() else None
    )
    return merge_managed_block(existing or "", body)


def refusal(text: str, config: object, workspace: Workspace) -> str | None:
    """Return why the rules file *text* is not written in *workspace*, if so.

    Past the per-file limit OpenClaw keeps the head and tail and drops the
    middle, and past the room the total leaves it cuts the file short or skips
    it; either way the rules arrive broken, so the file is not written.
    """
    size = chars(text)
    limits = limits_for(config, workspace.agent_ids)
    if size > limits.file_max:
        block = extract_managed_block(text)
        own = size - chars(block) if block is not None else 0
        yours = (
            f", {own:,} of them text you keep beside the Apothem block"
            if own > 64
            else ""
        )
        return (
            f"the Apothem rules file is {size:,} characters{yours}, over "
            f"OpenClaw's {limits.file_max:,}-character limit per file "
            "(bootstrapMaxChars), which would cut the middle out of it, so it is "
            "not written there. Shorten the profile's custom rules or that text, "
            "or raise the limit."
        )
    left = limits.total_max - used_chars(config, workspace.path, limits)
    if size <= left:
        return None
    effect = (
        "OpenClaw would skip it"
        if left < _MIN_FILE_BUDGET_CHARS
        else f"OpenClaw would keep only {max(left, 0):,} of its {size:,} characters"
    )
    others = (
        " and the other extra files of the bootstrap-extra-files entry"
        if operator_extras(config, workspace.path)
        else ""
    )
    return (
        f"the workspace files{others} already use most of OpenClaw's "
        f"{limits.total_max:,}-character total (bootstrapTotalMaxChars), so "
        f"{effect}; the Apothem rules file is not written there. Shorten those "
        "files or raise that limit."
    )


def fits_somewhere(body: str, config: object, home: Path) -> bool:
    """Return True when the rules file would be written in some workspace.

    With workspaces to write into, at least one of them must take the file
    within both limits. With none yet (OpenClaw is not set up), the per-file
    limit of the configured workspaces decides, so the path is registered for
    the workspaces OpenClaw will create.
    """
    found = find_workspaces(config, home)
    if found.found:
        return any(
            refusal(file_text(workspace, body), config, workspace) is None
            for workspace in found.found
        )
    if not found.missing:
        # No workspace can hold a file (each is skipped with its own note);
        # the path loads nothing, and the size limits are not the reason.
        return True
    size = chars(merge_managed_block("", body))
    return any(
        size
        <= min(
            limits_for(config, workspace.agent_ids).file_max,
            limits_for(config, workspace.agent_ids).total_max,
        )
        for workspace in found.missing
    )


def rules_text(harness_root: Path, profile: dict[str, Any]) -> tuple[str, str]:
    """Return the managed-block body and the full file text for *profile*."""
    body = install_driver.profile_document_body(
        harness_root,
        harness_id=_HARNESS_ID,
        harness_name=_HARNESS_NAME,
        profile=profile,
    )
    return body, merge_managed_block("", body)


def targets(config_path: Path) -> tuple[Path, ...]:
    """Return the rules file of every workspace the install writes into."""
    found = find_workspaces(read_config(config_path), config_path.parent.parent)
    return tuple(workspace.rules_file for workspace in found.found)


def _key(path: Path | str) -> str:
    """Return a comparison key for a path as the install record spells it."""
    return os.path.normcase(str(Path(path).resolve(strict=False)))


def _same(path: Path, others: Iterable[Path]) -> bool:
    """Return True when *path* is one of *others*, also on a case-folding volume."""
    key = _key(path)
    for other in others:
        if _key(other) == key:
            return True
        try:
            if path.exists() and other.exists() and path.samefile(other):
                return True
        except OSError:
            continue
    return False


def _earlier_rules_files(harness_root: Path) -> tuple[list[Path], set[str]]:
    """Return the rules files earlier installs wrote, and the folders they made.

    Read from every install still in effect (since the last uninstall), so a
    file an interrupted update failed to clean is found again.
    """
    try:
        records = install_ledger.active_install_records(
            _HARNESS_NAME, root=harness_root
        )
    except install_ledger.LedgerError:
        return [], set()
    files: list[Path] = []
    for record in records:
        for target in record.targets:
            path = Path(target.path)
            if (
                target.mode == "sentinel_merge"
                and path.parts[-len(_RULES_PARTS) :] == _RULES_PARTS
                and path not in files
            ):
                files.append(path)
    created = {_key(path) for record in records for path in record.created_dirs}
    return files, created


def _holds_block(path: Path) -> bool:
    """Return True when *path* still carries an Apothem managed block."""
    text = _raw_text(path)
    return text is not None and extract_managed_block(text) is not None


def _retire_one(
    path: Path,
    harness_root: Path,
    created: set[str],
    *,
    dry_run: bool,
    strict: bool = False,
) -> list[MaterializationResult]:
    """Take the managed block out of one earlier rules file.

    With *strict* (uninstall), a file reached through a link that still holds
    the block is a ``blocked`` warning, and a block the strip could not take
    out is an ``error``; either way the uninstall is recorded unfinished and
    the install stays active, so the file is not forgotten.
    """
    home = harness_root.parent
    flag = _error if strict else _warning
    if not _holds_block(path):
        # Nothing of Apothem's is left in it (reading through a link changes
        # nothing), so there is nothing to take out.
        return []
    link = _unsafe_symlink(path, home)
    if link is not None:
        detail = {"symlink": _path_text(link)}
        if strict:
            # Apothem's block stays in a file it wrote, so the uninstall is
            # unfinished. OpenClaw no longer loads it: the uninstall removes
            # the hook entry's path (``loaded: "0"`` lets the report say so).
            detail["blocked"] = "1"
            detail["loaded"] = "0"
        return [
            MaterializationResult(
                outcome="warning",
                operation=_RETIRE,
                path=str(path),
                message=(
                    f"an earlier Apothem rules file is reached through a link "
                    f"({link}); Apothem changes nothing through a link, so it is "
                    "left in place. Delete the Apothem block in it, or the file, "
                    "by hand, then run the command again."
                ),
                detail=detail,
            )
        ]
    if dry_run:
        return [
            MaterializationResult(
                outcome="updated",
                operation=_RETIRE,
                path=str(path),
                message="would take the Apothem block out of this rules file",
            )
        ]
    result = install_driver.strip_managed_anchor(
        path, install_root=harness_root, harness_name=_HARNESS_NAME, allowed_root=home
    )
    results = [] if result is None else [result]
    if result is not None and result.outcome == "error":
        return [result if strict else replace(result, outcome="warning")]
    if path.exists() and _holds_block(path):
        return [
            flag(
                path,
                "could not take the Apothem block out of this earlier rules file; "
                "the next install, update or uninstall tries again",
            )
        ]
    folder = path.parent
    if not path.exists() and _key(folder) in created:
        results.extend(
            replace(removed, operation=_RETIRE)
            for removed in install_driver.remove_created_dirs(
                [folder], allowed_root=home
            )
        )
    return results


def retire_earlier_files(
    harness_root: Path, keep: Iterable[Path], *, dry_run: bool, strict: bool = False
) -> list[MaterializationResult]:
    """Take the managed block out of rules files this run no longer keeps.

    Covers a workspace that moved or went away from the config and a file that
    no longer fits. Only Apothem's block goes (operator text beside it stays);
    an emptied file is deleted, and its ``apothem/`` folder too when an install
    created it and it is empty. A file reached through a link is left in place
    with a warning, and one whose block could not be taken out is reported and
    tried again next time (it stays in the records still in effect).
    """
    kept = list(keep)
    earlier, created = _earlier_rules_files(harness_root)
    results: list[MaterializationResult] = []
    for path in earlier:
        if _same(path, kept) or not path.is_file():
            continue
        results.extend(
            _retire_one(path, harness_root, created, dry_run=dry_run, strict=strict)
        )
    return results


def apply(
    config_path: Path, profile: dict[str, Any], dry_run: bool, *, register: bool = True
) -> tuple[MaterializationResult, ...]:
    """Write the rules file into every workspace; return results and warnings.

    *register* is False when the install leaves the hook without Apothem's
    path because the file fits no workspace: then no file is written. A
    workspace whose limits the file exceeds gets a warning and no file (see
    :func:`refusal`). Files earlier installs wrote that this run does not
    keep lose their managed block (see :func:`retire_earlier_files`); a file
    whose write failed is kept, never retired.
    """
    harness_root = config_path.parent
    home = harness_root.parent
    config = read_config(config_path)
    found = find_workspaces(config, home)
    results: list[MaterializationResult] = [
        _warning(harness_root, note) for note in found.notes
    ]
    body, _ = rules_text(harness_root, profile)
    keep: list[Path] = []
    for workspace in found.found:
        reason = refusal(file_text(workspace, body), config, workspace)
        if reason is not None:
            results.append(_warning(workspace.rules_file, reason))
            continue
        if not register:
            continue
        keep.append(workspace.rules_file)
        results.append(
            install_driver.apply_managed_block_anchor(
                workspace.rules_file,
                body,
                install_root=harness_root,
                harness_name=_HARNESS_NAME,
                allowed_root=home,
                dry_run=dry_run,
            )
        )
    results.extend(retire_earlier_files(harness_root, keep, dry_run=dry_run))
    return tuple(results)


def before_uninstall(config_path: Path) -> tuple[MaterializationResult, ...]:
    """Clear what the open-claw uninstall must handle before the shared steps.

    A commented ``openclaw.json`` that still holds Apothem's entries stops the
    uninstall first, before anything changes (:func:`json5_leftovers`).
    Otherwise every rules file an install still in effect wrote loses its
    managed block (:func:`retire_all`).
    """
    leftovers = json5_leftovers(config_path)
    if leftovers:
        return leftovers
    return tuple(retire_all(config_path.parent))


def retire_all(harness_root: Path) -> list[MaterializationResult]:
    """Take the managed block out of every rules file installs still in effect wrote.

    Runs before an uninstall closes the records, so a file an earlier update
    failed to clean, which only an older record lists, is cleaned too.
    """
    return retire_earlier_files(harness_root, (), dry_run=False, strict=True)
