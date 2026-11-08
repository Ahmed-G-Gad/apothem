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
2026-11-08). Only folders that exist and sit inside the home directory are
written: a workspace OpenClaw has not created yet gets its file from the next
``apothem update``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import MaterializationResult
from apothem.harnesses.open_claw.materializer import RULES_FILE_RELATIVE
from apothem.lib import lenient_json
from apothem.lib.harness_materializer import merge_managed_block

#: OpenClaw's default limits on what it injects (``bootstrapMaxChars`` and
#: ``bootstrapTotalMaxChars`` under ``agents.defaults``; source
#: ``src/agents/embedded-agent-helpers/bootstrap.ts``).
DEFAULT_FILE_MAX_CHARS: Final[int] = 20_000
DEFAULT_TOTAL_MAX_CHARS: Final[int] = 60_000

#: ``USER.md`` keeps a fixed cap whatever the per-file limit is.
_USER_FILE_MAX_CHARS: Final[int] = 4_000

#: The six files OpenClaw injects before any extra file, in prompt order.
CANONICAL_FILES: Final[tuple[str, ...]] = (
    "AGENTS.md",
    "SOUL.md",
    "IDENTITY.md",
    "USER.md",
    "BOOTSTRAP.md",
    "MEMORY.md",
)

_HARNESS_NAME: Final[str] = "open_claw"
_HARNESS_ID: Final[str] = "open-claw"
_OPERATION: Final[str] = "open_claw_rules_file"


@dataclass(frozen=True)
class Workspaces:
    """The workspaces an install writes into, and the ones it passes over.

    ``missing`` are workspaces OpenClaw has not created yet: the normal state
    before OpenClaw is set up, reported as skipped, not as a warning.
    ``notes`` describe configured workspaces the install cannot use.
    """

    found: tuple[Path, ...]
    notes: tuple[str, ...]
    missing: tuple[Path, ...] = ()


def read_config(config: Path) -> object:
    """Return the parsed ``openclaw.json`` at *config*, or ``None``.

    The file is read as JSON5, the dialect OpenClaw reads. A missing or
    unreadable file reads as ``None``: the install then refuses or creates it
    through the shared native-config path, which reports why.
    """
    try:
        return lenient_json.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, lenient_json.LenientJSONError):
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


def _plain_id(agent_id: str) -> bool:
    """Return True when *agent_id* can name a folder without leaving its parent."""
    return (
        bool(agent_id.strip())
        and agent_id not in {".", ".."}
        and not any(separator in agent_id for separator in ("/", "\\", ":"))
    )


def candidate_workspaces(
    config: object, home: Path, env: Mapping[str, str] | None = None
) -> tuple[list[Path], list[str]]:
    """Return every workspace path *config* names, and notes on unusable ones.

    The default workspace is ``agents.defaults.workspace``, else
    ``OPENCLAW_WORKSPACE_DIR``, else ``~/.openclaw/workspace``. Each
    ``agents.entries.<id>`` uses its own ``workspace`` when set, else
    ``<agents.defaults.workspace>/<id>``, else ``~/.openclaw/workspace-<id>``.
    The entry OpenClaw treats as the one owning the default workspace also
    uses it; the default workspace is always a candidate, which covers it.
    """
    environ = os.environ if env is None else env
    notes: list[str] = []
    raw: list[str] = []
    defaults_workspace = _text(_mapping(config, "agents", "defaults").get("workspace"))
    default = defaults_workspace or _text(environ.get("OPENCLAW_WORKSPACE_DIR"))
    raw.append(default or "~/.openclaw/workspace")
    for agent_id, entry in _mapping(config, "agents", "entries").items():
        own = _text(entry.get("workspace")) if isinstance(entry, dict) else None
        if own is not None:
            raw.append(own)
        elif not _plain_id(agent_id):
            notes.append(f"entry id {agent_id!r} is not a plain folder name; skipped")
        elif defaults_workspace is not None:
            raw.append(f"{defaults_workspace.rstrip('/')}/{agent_id}")
        else:
            raw.append(f"~/.openclaw/workspace-{agent_id}")
    paths: list[Path] = []
    for value in raw:
        path = _user_path(value, home)
        if path is None:
            notes.append(f"workspace {value!r} is not an absolute path; skipped")
        elif path not in paths:
            paths.append(path)
    return paths, notes


def find_workspaces(
    config: object, home: Path, env: Mapping[str, str] | None = None
) -> Workspaces:
    """Return the workspaces to write into: candidates that exist inside *home*."""
    candidates, notes = candidate_workspaces(config, home, env)
    found: list[Path] = []
    missing: list[Path] = []
    resolved_home = home.resolve()
    for path in candidates:
        if not path.resolve().is_relative_to(resolved_home):
            notes.append(f"workspace {path} is outside the home directory; skipped")
        elif path.exists() and not path.is_dir():
            notes.append(f"workspace {path} is not a folder; skipped")
        elif not path.is_dir():
            missing.append(path)
        else:
            found.append(path)
    return Workspaces(tuple(found), tuple(notes), tuple(missing))


def _limit(config: object, key: str, default: int) -> int:
    """Return the ``agents.defaults.<key>`` character limit, or *default*."""
    value = _mapping(config, "agents", "defaults").get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return default


def _canonical_chars(workspace: Path, file_max: int) -> int:
    """Return how many characters the six workspace files take, as injected."""
    used = 0
    for name in CANONICAL_FILES:
        try:
            size = len((workspace / name).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        cap = min(file_max, _USER_FILE_MAX_CHARS) if name == "USER.md" else file_max
        used += min(size, cap)
    return used


def _warning(target: Path, message: str) -> MaterializationResult:
    """Return a warning result about *target*."""
    return MaterializationResult(
        outcome="warning", operation=_OPERATION, path=str(target), message=message
    )


def check_limits(
    text: str, workspace: Path, *, file_max: int, total_max: int
) -> MaterializationResult | None:
    """Return a warning when *text* would be cut in *workspace*, else ``None``.

    OpenClaw injects extra files after the six workspace files, so the room
    left in the total budget is what the rules file gets; below 64 characters
    it is skipped.
    """
    target = workspace / RULES_FILE_RELATIVE
    left = total_max - _canonical_chars(workspace, file_max)
    if len(text) <= left:
        return None
    if left < 64:
        effect = "OpenClaw skips the Apothem rules file"
    else:
        effect = f"OpenClaw keeps only {left:,} of its {len(text):,} characters"
    return _warning(
        target,
        f"the workspace files already use most of OpenClaw's {total_max:,}-character "
        f"total (agents.defaults.bootstrapTotalMaxChars), so {effect}. Shorten the "
        "workspace files or raise that limit.",
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
    return tuple(workspace / RULES_FILE_RELATIVE for workspace in found.found)


def apply(
    config_path: Path, profile: dict[str, Any], dry_run: bool
) -> tuple[MaterializationResult, ...]:
    """Write the rules file into every workspace; return results and warnings.

    A file longer than OpenClaw's per-file limit is refused, not written: past
    it OpenClaw keeps the head and tail and drops the middle of the rules. A
    file the workspace's total budget would cut is written with a warning.
    """
    harness_root = config_path.parent
    home = harness_root.parent
    config = read_config(config_path)
    found = find_workspaces(config, home)
    results: list[MaterializationResult] = [
        _warning(harness_root, note) for note in found.notes
    ]
    results.extend(
        MaterializationResult(
            outcome="skipped",
            operation=_OPERATION,
            path=str(workspace / RULES_FILE_RELATIVE),
            message=(
                f"workspace {workspace} does not exist yet; run `apothem update "
                "--harness open-claw` once OpenClaw has created it"
            ),
        )
        for workspace in found.missing
    )
    body, text = rules_text(harness_root, profile)
    file_max = _limit(config, "bootstrapMaxChars", DEFAULT_FILE_MAX_CHARS)
    total_max = _limit(config, "bootstrapTotalMaxChars", DEFAULT_TOTAL_MAX_CHARS)
    for workspace in found.found:
        target = workspace / RULES_FILE_RELATIVE
        if len(text) > file_max:
            results.append(
                MaterializationResult(
                    outcome="skipped",
                    operation=_OPERATION,
                    path=str(target),
                    message=(
                        f"the Apothem rules file is {len(text):,} characters, over "
                        f"OpenClaw's {file_max:,}-character limit per file "
                        "(agents.defaults.bootstrapMaxChars), which would cut the "
                        "middle out of it; not written. Shorten the profile's "
                        "custom rules or raise that limit."
                    ),
                )
            )
            continue
        warning = check_limits(text, workspace, file_max=file_max, total_max=total_max)
        if warning is not None:
            results.append(warning)
        results.append(
            install_driver.apply_managed_block_anchor(
                target,
                body,
                install_root=harness_root,
                harness_name=_HARNESS_NAME,
                allowed_root=home,
                dry_run=dry_run,
            )
        )
    return tuple(results)
