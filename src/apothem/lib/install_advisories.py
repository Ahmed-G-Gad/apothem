# SPDX-License-Identifier: MIT

"""Install-time advisories that never block an install.

An advisory is a lifecycle-envelope entry with ``outcome: "advisory"``: the CLI
adds it to the ``warnings`` array of the ``--format json`` envelope and prints it
as a ``Note:`` line in plain mode. Advisories carry information the operator
needs to act on, and they never change what an install writes.

Shared roots. :data:`apothem.lib.harness_registry.SHARED_ROOTS` records each
install target that harnesses other than its writer also load. Installing the
owner of a shared root puts Apothem content in front of every reader, so
:func:`shared_root_advisories` names the readers. Installing a reader while the
shared root already holds Apothem content says which install placed it there.
A co-installer writes the same folder as the owner; its advisory (role
``holder``) names the other tools that load it and says the folder stays until
the last install that uses it is uninstalled. The registered owner is a label
for the vendor-documented path. The install that placed the content on a given
machine is the *owner of record*: the registered owner while it still holds the
folder, else the oldest install that does (:func:`owner_of_record`). The caller
passes the installs that hold each folder, read from the install ledger, and the
advisories name those instead of assuming the registered owner wrote the folder.

Hook review. :func:`hook_review_advisories` names the step a harness requires
before hooks written to its settings file by another tool take effect, or the
hazard of a hook file a repository commits, and for a harness that also imports
the hooks Claude Code's settings hold, the switch that stops the two sets running
together.

Instruction overrides. Some harnesses load only the first file with text from a
fixed list in one folder, so a file ahead of the one an install writes hides the
Apothem block. :func:`instruction_override_advisories` names that file when it
has text and is not a symbolic link to the instruction file itself. OpenCode 1
instead lets an ``instructions`` list in ``opencode.jsonc`` replace the list an
install writes in ``opencode.json`` in the same folder, and the function names
that file too. It also names each of ``config.json``, ``opencode.json`` and
``opencode.jsonc`` there that stops OpenCode 1 with an error before it loads
any of its configuration: a file it cannot read or parse, a ``{file:path}`` in
it that names a file it cannot read, a top level that is not an object, or an
``instructions`` value that is not a list of strings. Install and update print
the note; verify prints it only while the instruction file holds what the
install wrote.

MCP servers. :func:`mcp_profile_advisories` reads the shared profile's MCP
inventory and flags a deprecated transport, plain ``http://`` to a remote host,
and literal credentials in ``headers`` or ``env``, which an install would copy
into every harness config file that takes MCP servers.
"""

from __future__ import annotations

import errno
import ipaddress
import json
import os
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit

import apothem
from apothem.lib.codex_home import codex_home
from apothem.lib.harness_materializer import APOTHEM_BLOCK_BEGIN
from apothem.lib.harness_registry import (
    SHARED_ROOTS,
    SharedRoot,
    get_harness_entry,
)

_HOME_PREFIX = "~/"
_PROJECT_PREFIX = "<project>/"
# Claude Code writes agents as ``<name>.md`` and Codex as ``<name>.toml``.
_AGENT_SUFFIXES = (".md", ".toml")


def _display_name(public_id: str) -> str:
    return get_harness_entry(public_id).display_name


def _written_elsewhere(root: SharedRoot, home: Path) -> bool:
    """Return whether the owner's install writes *root* away from its path.

    A Codex root under ``~/.codex/`` moves with ``CODEX_HOME``: the Codex
    install then writes the folder under that home, which the registry does not
    list for the tools that load the registry path. Two spellings of one folder
    (a case-insensitive volume, a bind mount) count as the same folder.
    """
    if root.owner != "codex" or not root.path.startswith(f"{_HOME_PREFIX}.codex/"):
        return False
    moved, default = codex_home(home), home / ".codex"
    try:
        if moved.exists() and default.exists():
            return not moved.samefile(default)
        return moved.resolve() != default.resolve()
    except (OSError, RuntimeError):
        return moved != default


def _resolve(path: str, *, home: Path, project: Path | None) -> Path | None:
    """Resolve a registry-notation *path* against *home* or *project*."""
    if path.startswith(_HOME_PREFIX):
        return home / path[len(_HOME_PREFIX) :].rstrip("/")
    if path.startswith(_PROJECT_PREFIX):
        if project is None:
            return None
        return project / path[len(_PROJECT_PREFIX) :].rstrip("/")
    return None


@lru_cache(maxsize=1)
def _apothem_skill_names() -> frozenset[str]:
    """Return the skill folder names an Apothem install writes.

    Skills keep their folder name, and command prompts become skills named
    after the command file, so both cohorts contribute names.
    """
    package = Path(apothem.__file__).resolve().parent
    names = {child.name for child in (package / "skills").iterdir() if child.is_dir()}
    names |= {child.stem for child in (package / "commands").glob("*.md")}
    names.discard("README")
    return frozenset(names)


@lru_cache(maxsize=1)
def _apothem_agent_names() -> frozenset[str]:
    """Return the agent file stems an Apothem install writes."""
    package = Path(apothem.__file__).resolve().parent
    names = {child.stem for child in (package / "agents").glob("*.md")}
    names.discard("README")
    return frozenset(names)


def _holds_apothem_content(resolved: Path) -> bool:
    """Return True when *resolved* carries content an Apothem install wrote.

    A path the check cannot read holds none, so an unreadable folder never stops
    the install that asked.
    """
    try:
        if resolved.is_dir():
            if any(
                (resolved / name / "SKILL.md").is_file()
                for name in _apothem_skill_names()
            ):
                return True
            return any(
                (resolved / f"{name}{suffix}").is_file()
                for name in _apothem_agent_names()
                for suffix in _AGENT_SUFFIXES
            )
        if resolved.is_file():
            return APOTHEM_BLOCK_BEGIN in resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return False


def _qualified(root: SharedRoot, reader: str) -> str:
    """Return *reader*'s display name plus any condition it loads *root* under."""
    name = _display_name(reader)
    condition = root.reader_conditions.get(reader)
    return f"{name} ({condition})" if condition else name


def owner_of_record(root: SharedRoot, holders: Sequence[str]) -> str | None:
    """Return the install that counts as *root*'s owner on this machine.

    *holders* are the public ids of the installs that hold *root* now, oldest
    first. The registered owner counts while it holds the folder; otherwise the
    oldest holder does. ``None`` when no install is known to hold it. Nothing is
    transferred when the registered owner is uninstalled: the label moves, the
    files stay.
    """
    if root.owner in holders:
        return root.owner
    return holders[0] if holders else None


def _holders_sentence(holders: Sequence[str]) -> str:
    """Return the sentence naming the installs that hold a folder now, or ``""``."""
    if not holders:
        return ""
    names = ", ".join(_display_name(holder) for holder in holders)
    return f" Installs using it now: {names}."


def _entry(
    public_id: str,
    root: SharedRoot,
    resolved: Path,
    role: str,
    message: str,
    holders: Sequence[str] = (),
) -> dict[str, object]:
    return {
        "harness": public_id,
        "outcome": "advisory",
        "operation": "shared_root",
        "role": role,
        "path": str(resolved),
        "owner": root.owner,
        "owner_of_record": owner_of_record(root, holders),
        "holders": list(holders),
        "readers": sorted({*root.readers, *root.co_installers}),
        "message": message,
    }


def _left_behind(
    public_id: str, root: SharedRoot, resolved: Path, loaders: Sequence[str]
) -> dict[str, object]:
    """Return the note for a root an earlier install filled and this one skips.

    ``CODEX_HOME`` points the Codex home elsewhere, so this install writes there,
    but the registry path still holds Apothem content from an install made
    before, which its readers load and which this install neither updates nor
    removes.
    """
    readers = ", ".join(_qualified(root, reader) for reader in loaders)
    message = (
        f"{root.path} still holds Apothem content from an earlier "
        f"{_display_name(root.owner)} install, and {readers} "
        f"{'loads' if len(loaders) == 1 else 'load'} it. CODEX_HOME points the "
        f"Codex home elsewhere, so this install neither updates nor removes that "
        f"copy; delete it if you no longer want it."
    )
    return _entry(public_id, root, resolved, "owner", message)


def shared_root_advisories(
    public_id: str,
    *,
    home: Path,
    project: Path | None,
    holders: Callable[[Path], Sequence[str]] | None = None,
) -> list[dict[str, object]]:
    """Return the shared-root advisories for installing *public_id*.

    For each shared root *public_id* owns, one ``owner`` advisory names every
    tool that loads it, with the condition a reader loads the root under when the
    registry records one. For each shared root *public_id* co-installs, one
    ``holder`` advisory names the other tools that load it. For each shared root
    *public_id* only reads that already holds Apothem content (an Apothem skill
    folder or agent file in a skills or agents root, or the Apothem managed block
    in an instruction file), one ``reader`` advisory names the install that
    placed it there. Project roots are skipped when *project* is ``None``. When
    ``CODEX_HOME`` points the Codex home elsewhere, the Codex install writes a
    root under ``~/.codex/`` there instead, so that root gets no ``owner``
    advisory naming its readers; if an earlier install left Apothem content at
    the registry path, the advisory says this install neither updates nor
    removes it.

    *holders* maps a resolved root path to the public ids of the installs that
    hold it now, oldest first, read from the install ledger. With it the
    advisories name the installs using the folder and the owner of record
    (:func:`owner_of_record`); without it they say only what the registry knows.
    Reads the filesystem; writes nothing.
    """
    advisories: list[dict[str, object]] = []
    for root in SHARED_ROOTS:
        if root.kind == "support":
            continue
        # Every tool besides the owner that loads the folder: the readers, and
        # the co-installers that write the same copy.
        loaders = tuple(sorted({*root.readers, *root.co_installers}))
        if public_id != root.owner and public_id not in loaders:
            continue
        resolved = _resolve(root.path, home=home, project=project)
        if resolved is None:
            continue
        if public_id == root.owner and _written_elsewhere(root, home):
            # The install writes the folder elsewhere, so the registry path is
            # news only when an earlier install left Apothem content there.
            if _holds_apothem_content(resolved):
                advisories.append(_left_behind(public_id, root, resolved, loaders))
            continue
        held = tuple(holders(resolved)) if holders is not None else ()
        if public_id == root.owner:
            readers = ", ".join(_qualified(root, reader) for reader in loaders)
            single = len(loaders) == 1
            if root.co_installers:
                # Several installs write this folder, so removing the owner's
                # install does not remove it while another install holds it.
                tail = (
                    "It stays until the last Apothem install that uses it is "
                    "uninstalled."
                )
            else:
                tail = (
                    f"Installing or uninstalling {_display_name(root.owner)} "
                    f"changes what {'that tool loads' if single else 'those tools load'}."
                )
            message = (
                f"{root.path} is shared: {readers} also "
                f"{'loads' if single else 'load'} it. {tail}"
                f"{_holders_sentence(held) if root.co_installers else ''}"
            )
            advisories.append(_entry(public_id, root, resolved, "owner", message, held))
        elif public_id in root.co_installers:
            # This install writes the folder too: it holds the folder until it is
            # uninstalled, and the folder stays while any other install holds it.
            others = ", ".join(
                _qualified(root, other)
                for other in sorted(
                    {root.owner, *loaders} - {public_id},
                    key=lambda name: _display_name(name),
                )
            )
            message = (
                f"{root.path} is shared: {others} also load it. It stays until "
                f"the last Apothem install that uses it is uninstalled."
                f"{_holders_sentence(held)}"
            )
            advisories.append(
                _entry(public_id, root, resolved, "holder", message, held)
            )
        elif _holds_apothem_content(resolved):
            placed_by = owner_of_record(root, held)
            source = (
                f"the {_display_name(placed_by)} install"
                if placed_by is not None
                else "an Apothem install"
            )
            message = (
                f"{_qualified(root, public_id)} also loads {root.path}, which "
                f"holds Apothem content from {source}."
            )
            advisories.append(
                _entry(public_id, root, resolved, "reader", message, held)
            )
    return advisories


# --- Hook review advisories ---------------------------------------------------

#: Harnesses that load a hook registration an install wrote only after the
#: operator reviews it, mapped to the project-relative file the install wrote
#: and the note the advisory carries. CodeBuddy snapshots its settings at
#: startup and applies an externally edited file only after the entries are
#: confirmed in the /hooks panel (https://www.codebuddy.ai/docs/cli/hooks and
#: /hooks-guide, retrieved 2026-10-28). Kiro CLI loads a workspace's hooks only
#: after the operator trusts the workspace (https://kiro.dev/docs/permissions/,
#: retrieved 2026-10-27), and its Web sessions run none
#: (https://kiro.dev/docs/hooks/, retrieved 2026-10-28). Copilot has no review
#: step; its note names the committed-file hazard instead, because the file
#: lives in a folder repositories commit and holds this machine's paths
#: (https://docs.github.com/en/copilot/reference/hooks-reference, retrieved
#: 2026-10-28). Devin Local loads no hook in Restricted Mode
#: (https://docs.devin.ai/desktop/devin-local/overview.md#restricted-mode,
#: retrieved 2026-11-02) and its
#: config.local.json is gitignored
#: (https://docs.devin.ai/cli/extensibility/hooks/overview.md, retrieved
#: 2026-10-28). Cursor's project hook file is checked into version control, runs
#: in trusted workspaces and is reloaded on save (https://cursor.com/docs/hooks,
#: retrieved 2026-10-28).
_HOOK_REVIEW: dict[str, tuple[str, str]] = {
    "codebuddy": (
        ".codebuddy/settings.local.json",
        "Apothem registers its SessionStart and PostToolUse hooks in "
        "{path}. CodeBuddy does not hot-load a settings file edited from "
        "outside: restart CodeBuddy, then confirm the new entries in the "
        "/hooks panel, and the hooks apply after that review. The docs do not "
        "say whether the review repeats after each change, so check /hooks "
        "again after an update. CodeBuddy documents hooks as Beta, and on "
        "Windows it runs hook commands through Git Bash only.",
    ),
    "kiro": (
        ".kiro/hooks/apothem.json",
        "Apothem registers its SessionStart hook in {path}. Kiro CLI 2.33 and "
        "later loads a workspace's hooks only after you trust the workspace: "
        "accept the 'Trust this workspace?' screen the first time you start an "
        "interactive V3 session (kiro-cli --v3) in this folder. Kiro Web "
        "sessions run no hooks. The file names this machine's Python "
        "interpreter and this project's path, so commit it only if your team "
        "shares that layout; where the command is missing, Kiro shows a "
        "warning and the session goes on.",
    ),
    "github-copilot": (
        ".github/hooks/apothem.json",
        "Apothem registers its sessionStart and postToolUse hooks in {path}. "
        "The file names this machine's Python interpreter and this project's "
        "path, and .github/hooks/ is part of the repository, so commit it "
        "only if your team shares that layout. Copilot's cloud agent reads the "
        "file and runs only its bash command, which finds no interpreter "
        "there; Copilot logs the failure and the run goes on.",
    ),
    "windsurf": (
        ".devin/config.local.json",
        "Apothem registers its SessionStart and PostToolUse hooks in {path}, "
        "the local override Devin documents as gitignored; your own hooks and "
        "keys in it stay. Devin excludes local config files from git itself "
        "(through .git/info/exclude), so the machine-specific interpreter and "
        "project path the file names stay out of the repository. Devin loads "
        "no hook while the workspace is in Restricted Mode, so trust the "
        "workspace first. The Devin docs name no shell for hook commands on "
        "Windows and the command is quoted for sh: open the Hooks tab in Devin "
        "Local's Customizations (or run /hooks in the Devin CLI) to confirm "
        "the hooks loaded.",
    ),
    "cursor": (
        ".cursor/hooks.json",
        "Apothem registers its sessionStart hook in {path}, your project hook "
        "file; your own entries and keys in it stay. Cursor documents project "
        "hooks as checked into version control and runs them in trusted "
        "workspaces, and it reloads the file on save. The command names this "
        "machine's Python interpreter and this project's path, so commit the "
        "file only if your team shares that layout; where the command is "
        "missing, Cursor reports the hook as failed and the session goes on. "
        "On a Windows host the command starts with the PowerShell call "
        "operator (&), because Cursor's desktop app runs hook commands through "
        "PowerShell there.",
    ),
}

#: Harnesses that also load the hooks Claude Code's settings files hold, mapped
#: to the file the install wrote and the note that names the switch and what
#: turning it off costs. Cursor runs every matching hook from every source, and
#: reads the Claude Code hooks while "Include Third-Party Plugins, Skills, and
#: Other Configs" is on, its default
#: (https://cursor.com/docs/reference/third-party-hooks, retrieved 2026-10-27).
#: Devin loads them while read_config_from.claude is on, its default for the CLI
#: (https://docs.devin.ai/cli/extensibility/hooks/overview.md and
#: /cli/reference/configuration/read-config-from.md, retrieved 2026-10-28), and
#: Devin Local in Devin Desktop uses the CLI's discovery
#: (https://docs.devin.ai/desktop/devin-local/customizations.md, retrieved
#: 2026-11-02). The SessionStart command each install registers and the Claude
#: Code copy of it share one per-session marker, so whichever runs second is
#: silent; no PostToolUse counter is de-duplicated.
_HOOK_IMPORT: dict[str, tuple[str, str]] = {
    "windsurf": (
        ".devin/config.local.json",
        "Devin Local also loads the hooks Claude Code's settings files hold "
        "(~/.claude/settings.json, .claude/settings.json and "
        ".claude/settings.local.json) while read_config_from.claude is on, "
        "which is its default: Devin Local finds its files the way the Devin "
        "CLI does. If this machine also has the "
        "Apothem Claude Code install, both sets can run: the SessionStart "
        "command in {path} and the Claude Code copy of it share one marker per "
        "session, so whichever runs second is silent and the bootstrap reaches "
        "the model once, but each PostToolUse counter runs in both places, so "
        "its thresholds are "
        'reached early. To load only the hooks in {path}, set "claude": false '
        'under "read_config_from" in ~/.config/devin/config.json '
        "(%APPDATA%/devin/config.json on Windows) or in the project's "
        ".devin/config.json; that also stops Devin importing Claude Code's "
        "rules, skills, commands and MCP servers.",
    ),
    "cursor": (
        ".cursor/hooks.json",
        "Cursor also loads the hooks Claude Code's settings files hold "
        "(~/.claude/settings.json, .claude/settings.json and "
        ".claude/settings.local.json) while 'Include Third-Party Plugins, "
        "Skills, and Other Configs' is on (Cursor Settings, Agents, "
        "Third-Party Imports), which is its default, and it runs every "
        "matching hook from every source. If this machine also has the Apothem "
        "Claude Code install, both sets can run: the sessionStart command in "
        "{path} and the Claude Code copy of it share one marker per session, "
        "so whichever runs second is silent and the bootstrap reaches the "
        "model once, but each of its PostToolUse counters runs in addition. "
        "To run only the hook in "
        "{path}, turn that setting off; it also stops Cursor importing "
        "third-party plugins, skills and other configs.",
    ),
}


def hook_review_advisories(
    public_id: str, *, project: Path | None
) -> list[dict[str, object]]:
    """Return the notes for *public_id*'s hook registration, if it has any.

    The ``hook_review`` note names the file the install wrote and the step the
    operator takes before the hooks run, or the hazard of the file. The
    ``hook_import`` note names the switch that stops a harness running the hooks
    Claude Code wrote beside Apothem's own. A harness with neither, or an install
    with no *project*, gets none. Reads nothing; writes nothing.
    """
    if project is None:
        return []
    advisories: list[dict[str, object]] = []
    for operation, table in (
        ("hook_review", _HOOK_REVIEW),
        ("hook_import", _HOOK_IMPORT),
    ):
        note = table.get(public_id)
        if note is None:
            continue
        relative, template = note
        path = project / relative
        advisories.append(
            {
                "harness": public_id,
                "outcome": "advisory",
                "operation": operation,
                "path": str(path),
                "message": template.format(path=path),
            }
        )
    return advisories


# --- Instruction-file override advisories -------------------------------------


# For each harness whose install writes an instruction file that a file loaded
# ahead of it in the same folder can hide: the folder (from the user home), the
# file the install writes, and the files ahead of it in the harness's order. The
# harness loads only the first one that has text. Codex reads the first
# non-empty of AGENTS.override.md and AGENTS.md in its home folder
# ($CODEX_HOME, default ~/.codex): load_from_codex_home in
# codex-rs/codex-home/src/instructions/mod.rs at openai/codex c60cda34, and the
# Codex AGENTS.md page, both read 2026-11-03.
_INSTRUCTION_OVERRIDES: dict[
    str, tuple[Callable[[Path], Path], str, tuple[str, ...]]
] = {
    "codex": (codex_home, "AGENTS.md", ("AGENTS.override.md",)),
}

# The Unicode White_Space characters, which Rust's str::trim strips and Codex
# trims a candidate file with. Python's str.strip() with no argument also strips
# U+001C to U+001F, which Codex keeps as text.
_WHITE_SPACE = (
    "\t\n\x0b\x0c\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006"
    "\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"
)


def _has_text(path: Path) -> bool:
    """Return whether *path* is a file whose text is not all whitespace.

    Codex skips a directory, a missing file and one it cannot read, decodes the
    bytes leniently, and trims the Unicode White_Space characters; this check
    does the same.
    """
    try:
        if not path.is_file():
            return False
        text = path.read_bytes().decode("utf-8", errors="replace")
        return bool(text.strip(_WHITE_SPACE))
    except OSError:
        return False


def _links_to(path: Path, target: Path) -> bool:
    """Return whether *path* is a symbolic link to *target*.

    Such a link keeps pointing at *target* when an install replaces it. A hard
    link does not: the replacement splits it into a separate copy, so it counts
    as a file of its own.
    """
    try:
        return path.is_symlink() and path.resolve() == target.resolve()
    except (OSError, RuntimeError):
        return False


def _holds_block(path: Path) -> bool:
    """Return whether the file at *path* holds the Apothem block.

    A missing, unreadable or undecodable file holds none, so a folder the check
    cannot read never stops the command that asked.
    """
    try:
        return path.is_file() and APOTHEM_BLOCK_BEGIN in path.read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeDecodeError):
        return False


def instruction_override_advisories(
    public_id: str, *, home: Path, require_block: bool = False
) -> list[dict[str, object]]:
    """Return a note when a file *public_id* loads first hides its install's file.

    The note names the first file the harness loads ahead of the instruction
    file its install writes, in the same folder, that has text: the harness
    loads that file instead, so the Apothem block does not reach it. An empty
    file falls through, and a symbolic link to the instruction file itself
    hides nothing, so neither gets a note. A hard link or a copy that holds the
    Apothem block is a copy the install does not refresh, so its note says to
    remove it. A harness with no such file gets none. With *require_block*, as
    for ``verify``, the note also needs the Apothem block to be in the
    instruction file; install and update, which write the block, leave it off.
    The folder comes from *home* and the harness's own settings, not from an
    adapter. Reads the folder; writes nothing, and never raises for a folder it
    cannot read. OpenCode has its own check, :func:`_opencode_override_advisories`,
    which finds its folder the way the OpenCode install does and ignores *home*.
    """
    if public_id == "opencode":
        return _opencode_override_advisories(require_block=require_block)
    entry = _INSTRUCTION_OVERRIDES.get(public_id)
    if entry is None:
        return []
    folder_of, written, ahead = entry
    target = folder_of(home) / written
    if require_block and not _holds_block(target):
        return []
    for index, hiding in enumerate(ahead):
        path = target.parent / hiding
        if not _has_text(path) or _links_to(path, target):
            continue
        name = _display_name(public_id)
        order = " and ".join([*ahead[: index + 1], target.name])
        if _holds_block(path):
            remedy = (
                f"{path} holds its own copy of the Apothem block, which installs "
                f"and updates do not refresh: remove it, or replace it with a "
                f"symbolic link to {target.name}."
            )
        else:
            remedy = (
                f"Empty or remove {path}, or move its text into {target.name} "
                f"outside the Apothem block."
            )
        return [
            {
                "harness": public_id,
                "outcome": "advisory",
                "operation": "instruction_override",
                "path": str(path),
                "target": str(target),
                "message": (
                    f"{name} loads {hiding} instead of {target.name} in "
                    f"{target.parent}: it reads only the first of {order} there "
                    f"that has text, so the Apothem block in {target.name} does "
                    f"not reach {name}. {remedy}"
                ),
            }
        ]
    return []


# OpenCode 1 loads the global files config.json, opencode.json and opencode.jsonc
# from its config folder in that order and folds them with remeda's mergeDeep,
# which lets a list in a later file replace the earlier list, an empty one too:
# anomalyco/opencode v1.19.5 packages/opencode/src/config/config.ts:42-44 and
# 272-274, read 2026-11-09 (the same fold in v1.0.0, v1.0.100, v1.1.4 and
# v1.18.35). Only OPENCODE_CONFIG, project files and the OPENCODE_CONFIG_DIR
# folder are merged later by joining the lists (config.ts:46-52, 365-366,
# 412-446), so a same-folder opencode.jsonc is the one file that hides the list
# the install writes, unless OPENCODE_CONFIG names opencode.json or
# OPENCODE_CONFIG_DIR names its folder. OpenCode 2 joins the instructions lists
# of every file it reads (v2.2.5 and v2.2.6
# packages/core/src/config/plugin/instruction.ts:155). Any of the three global
# files can stop OpenCode 1 from loading any configuration: one it cannot parse
# throws JsonError (parse.ts:26); one whose top level is not an object, or whose
# instructions is not a list of strings, throws InvalidError (decodeConfig,
# config.ts:188-199, runs parse.ts:35-61 against the schema at
# packages/core/src/v1/config/config.ts:32 and :124); and a {file:path} it
# cannot read throws InvalidError (variable.ts:67-82). Effect 4.0.0-beta.83
# turns each into a defect that orElseSucceed does not catch (config.ts:297-300
# and 616): the parse and schema errors are thrown inside Effect generators
# (parse.ts:26 in loadConfig; parse.ts:48 in decodeConfig, which loadConfig
# yields at config.ts:241), and the {file:path} rejection comes through
# Effect.promise (config.ts:233-239). A read error it does not skip stops it
# the same way (config.ts:186, Effect.orDie). OpenCode 2 (v2.2.6) reads no
# config.json (packages/core/src/config/discovery.ts:12); it skips a file it
# cannot parse or whose top level is not an object (packages/core/src/config.ts
# :136-166 and 168-174, config/normalize.ts:57-64), ignores an instructions
# value that is not a list and drops the items of a list that are not strings
# (normalize.ts:228-229 and 690-706), puts in empty text for a {file:path} it
# cannot read (config/variable.ts:63-73), and escapes the {env:NAME} values
# when the text would not parse otherwise (variable.ts:27-37).
_OPENCODE_WRITTEN = "opencode.json"
_OPENCODE_LATER = "opencode.jsonc"
_OPENCODE_FOLDED = ("config.json", _OPENCODE_WRITTEN, _OPENCODE_LATER)

# OpenCode 1 parses with jsonc-parser 3.3.1 and allowTrailingComma
# (packages/opencode/src/config/parse.ts:10): JSON plus comments and trailing
# commas, nothing JSON5 adds. Each pattern matches a string first, so a comment
# marker or a comma inside a string is kept.
_JSONC_STRING = r'"(?:[^"\\\n\r]|\\.)*"'
_JSONC_COMMENT = re.compile(_JSONC_STRING + r"|//[^\n\r]*|/\*.*?\*/|/\*", re.DOTALL)
# A comma right after ``[``, ``{`` or another comma has no value before it, which
# jsonc-parser refuses even with allowTrailingComma, so that match is kept.
_JSONC_TRAILING_COMMA = re.compile(
    _JSONC_STRING + r"|[\[{,][ \t\n\r]*,(?=[ \t\n\r]*[}\]])|,(?=[ \t\n\r]*[}\]])"
)


def _drop_comment(match: re.Match[str]) -> str:
    """Return a string as it is; refuse an open comment.

    A comment becomes one space plus the line breaks it held, so removing one
    never joins the lines of a string that has a raw line break, which
    jsonc-parser refuses.
    """
    text = match.group()
    if text == "/*":
        raise ValueError("a block comment is not closed")
    if text.startswith('"'):
        return text
    return " " + "".join(char for char in text if char in "\r\n")


def _drop_comma(match: re.Match[str]) -> str:
    """Drop a trailing comma; keep a string, and a comma with no value before it."""
    text = match.group()
    return "" if text == "," else text


def _refuse_constant(name: str) -> object:
    """Refuse ``NaN`` and ``Infinity``, which JSONC does not have."""
    raise ValueError(f"{name} is not JSONC")


def _jsonc_text(path: Path) -> str | None:
    """Return the text of the file at *path*, decoded the way OpenCode 1 does.

    OpenCode 1 decodes the bytes with ``TextDecoder``, which drops a leading
    byte order mark and replaces bytes that are not UTF-8. A missing file, a
    folder and a file that cannot be read give ``None``.
    """
    try:
        if not path.is_file():
            return None
        return path.read_bytes().decode("utf-8-sig", errors="replace")
    except OSError:
        return None


def _parse_jsonc(text: str) -> object:
    """Return the document in *text*, parsed the way OpenCode 1 parses it.

    OpenCode 1 parses JSONC: comments and trailing commas, nothing else beyond
    JSON. Numbers are read as floats, as JavaScript reads them. Raises
    ``ValueError`` for text that is not JSONC (JSON5 syntax, ``NaN``, an open
    comment, no value at all).
    """
    text = _JSONC_COMMENT.sub(_drop_comment, text)
    text = _JSONC_TRAILING_COMMA.sub(_drop_comma, text)
    return json.loads(text, parse_int=float, parse_constant=_refuse_constant)


def _jsonc_object(path: Path) -> dict[str, object] | None:
    """Return the JSON object in the file at *path*, read the way OpenCode 1 does.

    A missing or unreadable file, an empty one, text that is not JSONC and a
    document that is not an object all give ``None``.
    """
    text = _jsonc_text(path)
    if not text:
        return None
    try:
        document = _parse_jsonc(text)
    except (ValueError, RecursionError):
        return None
    return document if isinstance(document, dict) else None


# OpenCode 1 replaces {env:NAME} and then {file:path} in the text of a config
# file before it parses it, once it has found that text is not empty (v1.19.5
# packages/opencode/src/config/variable.ts, called from config.ts:233-240,
# after the empty check at config.ts:255-256). v1.0.0 config.ts load() also
# replaces both before parsing, but finds a commented {file:path} token and
# puts in the file's text in other ways. Neither pattern stops at a line end.
_OPENCODE_ENV_TOKEN = re.compile(r"\{env:([^}]+)\}")
_OPENCODE_FILE_TOKEN = re.compile(r"\{file:([^}]+)\}")

# What JavaScript's trim() and trimStart() remove: the WhiteSpace and
# LineTerminator characters of ECMA-262 (tab, vertical tab, form feed, the
# Unicode space separators, U+FEFF, and the four line terminators). Python's
# str.strip() removes another set: it keeps U+FEFF and removes U+001C-U+001F
# and U+0085.
_JS_SPACE = (
    "\t\n\v\f\r \u00a0\u1680"
    + "".join(chr(code) for code in range(0x2000, 0x200B))
    + "\u2028\u2029\u202f\u205f\u3000\ufeff"
)

# Windows reports a file the user may not read as EPERM (Bun 1.4.4
# src/errno/windows_errno.rs:736 and :833; Bun 1.3.14, which v1.17.15 through
# v1.19.3 pin, src/errno/windows_errno.zig:1078), which OpenCode 1 does not
# skip; elsewhere such a read is EACCES, which releases from v1.17.15 on skip.
_WINDOWS = os.name == "nt"

# The check reads no file larger than this, and nothing but a regular file or
# a folder: a named pipe or a device could block the read or never end.
_READ_LIMIT = 16 * 1024 * 1024

# What jsonc-parser 3.3.1 skips between tokens: space, tab, line feed and
# carriage return (lib/esm/impl/scanner.js:352-357), and comments. A string
# followed by ":" is a key.
_JSONC_GAP = re.compile(r"(?:[ \t\n\r]|//[^\n\r]*|/\*.*?\*/)*", re.DOTALL)
# The inside of a string up to a point that is not within an escape sequence.
_STRING_PREFIX = re.compile(r"(?:[^\\]|\\u[0-9A-Fa-f]{4}|\\[^u])*", re.DOTALL)


@dataclass(frozen=True)
class _OpencodeFile:
    """What OpenCode 1 makes of one of its global configuration files.

    *refusal* is ``None`` when OpenCode 1 loads the file (or skips it, or the
    check does not read it), else why it stops: ``"folder"``, ``"read"``
    (*detail* is the read error's text), ``"reference"`` (*detail* is the
    ``{file:path}`` token whose file cannot be read), ``"parse"``, ``"env"``
    (the text parses only once its ``{env:NAME}`` values are escaped),
    ``"top-level"`` or ``"instructions"``. *document* is the parsed document
    when there is one; for ``"env"``, the document with the values escaped.
    For ``"env"``, *escaped* is the refusal that document still gets
    (``"top-level"``, ``"instructions"`` or ``None``), and *variables* names
    each variable whose value holds what JSON escapes. *unsure* is True for
    a ``"parse"`` whose escaped text depends on a ``{file:path}`` the check
    does not read, so what OpenCode 2 makes of the file is not known.
    """

    refusal: str | None = None
    detail: str = ""
    document: object = None
    escaped: str | None = None
    variables: tuple[str, ...] = ()
    unsure: bool = False


class _UnreadableReferenceError(Exception):
    """A ``{file:path}`` token names a file that cannot be read."""

    def __init__(self, token: str) -> None:
        """Record the *token* as it is written in the file."""
        super().__init__(token)
        self.token = token


class _UncheckedError(Exception):
    """The outcome depends on the text of a ``{file:path}`` the check does not read.

    The check reads no file larger than ``_READ_LIMIT`` and, on Windows, no
    path rooted without a drive (see :func:`_referenced_text`). Such a
    reference is checked as empty text while it sits inside a string value
    and not within an escape sequence, where no text it puts in changes the
    outcome (see :func:`_inside_strings`); anywhere else its text decides,
    so the file is not checked. A reference whose file the check cannot
    tell OpenCode 1 reads is not checked wherever it sits. *stop* is True
    for a file OpenCode 1 may wait on forever, such as a named pipe: it
    reads the references in order, so none after it counts either.
    """

    def __init__(self, *, stop: bool = False) -> None:
        """Record whether OpenCode 1 may never get past this reference."""
        super().__init__()
        self.stop = stop


def _env_value(match: re.Match[str], *, escape: bool) -> str:
    """Return the value an ``{env:NAME}`` *match* puts in, escaped if asked.

    *escape* escapes it as the inside of a JSON string, the way OpenCode 2's
    ``JSON.stringify(value).slice(1, -1)`` does (v2.2.6 ``variable.ts:30``).
    """
    value = os.environ.get(match.group(1)) or ""
    return json.dumps(value, ensure_ascii=False)[1:-1] if escape else value


def _opencode_substitute(text: str, folder: Path, *, escape: bool = False) -> str:
    """Return *text* with its ``{env:...}`` and ``{file:...}`` tokens replaced.

    Each ``{env:NAME}`` becomes the value of ``NAME`` in this environment, or
    nothing; OpenCode 1 puts it in as it is. *escape* follows OpenCode 2's
    second pass, run when the text would not parse otherwise: it escapes each
    value, and a ``{file:path}`` file it cannot read puts in nothing (v2.2.6
    ``variable.ts:27-37`` and ``:63-73``). Each
    ``{file:path}`` not on a line that starts with ``//``, after any JavaScript
    whitespace, becomes that file's text, trimmed the way JavaScript's
    ``trim()`` trims and escaped as the inside of a JSON string; see
    :func:`_reference_path` for where it is read from.

    Raises:
        _UnreadableReferenceError: Without *escape*, when a ``{file:path}``
            names a file that cannot be read, for which OpenCode 1 stops with
            a ``bad file reference`` error (v1.19.5 ``variable.ts:67-82``).
        _UncheckedError: When the outcome depends on the text of a
            ``{file:path}`` the check does not read (see
            :class:`_UncheckedError`).
    """
    text = _OPENCODE_ENV_TOKEN.sub(lambda m: _env_value(m, escape=escape), text)
    pieces: list[str] = []
    unread: list[int] = []
    unchecked = False
    size = 0
    cursor = 0
    for match in _OPENCODE_FILE_TOKEN.finditer(text):
        start = match.start()
        pieces.append(text[cursor:start])
        size += start - cursor
        cursor = match.end()
        line = text[text.rfind("\n", 0, start) + 1 : start]
        if line.lstrip(_JS_SPACE).startswith("//"):
            pieces.append(match.group())
            size += len(match.group())
            continue
        try:
            content = _referenced_text(match, folder)
        except _UnreadableReferenceError:
            if not escape:
                raise
            content = ""
        except _UncheckedError as error:
            if error.stop:
                raise
            # A later reference OpenCode 1 cannot read still stops it.
            unchecked = True
            continue
        if content is None:
            unread.append(size)
            continue
        piece = json.dumps(content, ensure_ascii=False)[1:-1]
        pieces.append(piece)
        size += len(piece)
    pieces.append(text[cursor:])
    result = "".join(pieces)
    if unchecked or (unread and not _inside_strings(result, unread)):
        raise _UncheckedError
    return result


def _inside_strings(text: str, offsets: list[int]) -> bool:
    """Return whether each of *offsets* in *text* falls inside a string value.

    Text put in at such an offset is escaped as the inside of a string, so it
    cannot change where any string, comment or value of *text* begins or ends.
    That holds only where the offset is not within an escape sequence, whose
    end the text would supply, and the string is a value: the text of a key
    decides which key it is, ``instructions`` among them.
    """
    spans = [
        (found.start(), found.end())
        for found in _JSONC_COMMENT.finditer(text)
        if found.group().startswith('"')
    ]

    def safe(at: int) -> bool:
        for start, end in spans:
            if start < at < end:
                after = _JSONC_GAP.match(text, end)
                key = after is not None and text.startswith(":", after.end())
                whole = _STRING_PREFIX.fullmatch(text, start + 1, at) is not None
                return whole and not key
        return False

    return all(safe(at) for at in offsets)


def _reference_path(name: str, folder: Path) -> str:
    """Return the path OpenCode 1 reads for the ``{file:path}`` path *name*.

    A ``~/`` path is read from the home folder and a relative one from
    *folder*. OpenCode 1 builds the first with Node's ``path.join`` and the
    second with ``path.resolve``, and uses an absolute path as it is written
    (v1.19.5 ``variable.ts:61-66``). ``path.join`` and ``path.resolve`` drop
    ``.`` and ``..`` from the text before the system sees it, so a ``..``
    after a missing folder or a symbolic link counts the way it is written;
    ``path.join`` keeps a trailing ``/`` and ``path.resolve`` drops it.
    On Windows the system folds ``.`` and ``..`` by the text as well, and a
    trailing separator after a file reads in both; a part ending in a dot or
    a space is left to :func:`_referenced_text`. Elsewhere the path is built
    here the way Node builds it, a leading ``//`` made one ``/``, and an
    absolute path is returned exactly as written: Python's ``pathlib`` and
    ``os.path.normpath`` drop a trailing ``/`` or ``/.``, after which a file
    that the system refuses to open as written (``ENOTDIR``) would read.
    """
    if _WINDOWS:
        if name.startswith("~/"):
            return str(Path.home() / name[2:])
        return str(folder / name)
    if name.startswith("/"):
        return name
    home = name.startswith("~/")
    joined = f"{Path.home()}/{name[2:]}" if home else f"{folder}/{name}"
    normal = os.path.normpath(joined)
    if normal.startswith("//"):
        normal = "/" + normal.lstrip("/")
    if home and joined.endswith("/") and not normal.endswith("/"):
        normal += "/"
    return normal


def _referenced_text(match: re.Match[str], folder: Path) -> str | None:
    """Return the trimmed text of the file a ``{file:path}`` *match* names.

    ``None`` when the check does not read it: a file larger than
    ``_READ_LIMIT``, and on Windows a path rooted without a drive, which
    OpenCode 1 reads on the drive of the folder it was started in. The null
    device reads as empty text, as it does for OpenCode 1 (``readFile``), and
    a socket cannot be opened, by OpenCode 1 either.

    Raises:
        _UnreadableReferenceError: When OpenCode 1 cannot read the file.
        _UncheckedError: On Linux and macOS, with *stop*, for a named pipe or
            a device other than the null device, which OpenCode 1 may wait on
            forever. On Windows, for anything but a regular file or a folder,
            and for a path with a part that ends in a dot or a space: Python
            reads a name such as ``NUL`` in any folder as the device and drops
            such a dot or space, but Node 26.7.0 opens the path as written and
            finds no file (``ENOENT`` for ``<folder>\\NUL`` and for
            ``f.txt.`` beside ``f.txt``, and a folder named ``sub.`` reads,
            run 2026-11-10), and the Bun runtime OpenCode 1 ships with was not
            checked, so whether OpenCode 1 can read it is not known here.
    """
    name = match.group(1)
    if _WINDOWS:
        if _rooted_without_drive(name):
            return None
        if any(
            part.endswith((".", " ")) and part not in (".", "..")
            for part in re.split(r"[\\/]", name)
        ):
            raise _UncheckedError
    source = _reference_path(name, folder)
    # The path is used as a string: pathlib would drop a trailing "/" or "/.".
    try:
        mode = os.stat(source)  # noqa: PTH116 - the path exactly as spelled
        if stat.S_ISREG(mode.st_mode) and mode.st_size > _READ_LIMIT:
            return None
        if not stat.S_ISREG(mode.st_mode) and not stat.S_ISDIR(mode.st_mode):
            return _special_text(mode, match.group())
        with open(source, "rb") as handle:  # noqa: PTH123 - as spelled, too
            data = handle.read()
    except (OSError, ValueError) as error:
        raise _UnreadableReferenceError(match.group()) from error
    return data.decode("utf-8", errors="replace").strip(_JS_SPACE)


def _special_text(mode: os.stat_result, token: str) -> str:
    """Return the text OpenCode 1 reads from a file that is not a regular file.

    Only the null device gives known text, none. See :func:`_referenced_text`
    for what this raises for the others.
    """
    if _WINDOWS:
        raise _UncheckedError
    if stat.S_ISSOCK(mode.st_mode):
        raise _UnreadableReferenceError(token)
    if stat.S_ISCHR(mode.st_mode):
        try:
            null = os.stat(os.devnull)  # noqa: PTH116 - a device, not a path
        except OSError:
            null = None
        rdev = getattr(mode, "st_rdev", None)
        if rdev is not None and rdev == getattr(null, "st_rdev", None):
            return ""
    raise _UncheckedError(stop=True)


def _rooted_without_drive(name: str) -> bool:
    """Return whether the Windows path *name* starts at a root but names no drive."""
    path = PureWindowsPath(name)
    return bool(path.root) and not path.drive


def _read_error_refusal(error: OSError) -> str | None:
    """Return the text of a read *error* OpenCode 1 stops for, or ``None``.

    OpenCode 1 releases from v1.17.15 on skip a missing file and a file they
    may not read (v1.19.5 ``packages/core/src/fs-util.ts:62-67``), but only
    ``EACCES`` counts as one they may not read: ``@effect/platform-node-shared``
    4.0.0-beta.83 maps ``EPERM`` to ``Unknown`` (``src/internal/utils.ts:13-41``),
    and Windows reports every denied read as ``EPERM``. Any other read error
    stops the config (``config.ts:186``). A path through a file instead of a
    folder is left alone, since nothing is installed there.
    """
    if isinstance(error, (FileNotFoundError, NotADirectoryError)):
        return None
    if error.errno == errno.EACCES and not _WINDOWS:
        return None
    return error.strerror or type(error).__name__


def _read_opencode_file(path: Path) -> _OpencodeFile:
    """Return what OpenCode 1 makes of the global configuration file at *path*.

    OpenCode 1 reads an empty file as ``{}``: a file with no bytes, or only a
    byte order mark, which current releases drop (v1.19.5
    ``config.ts:255-256``). It checks that before it replaces the file's
    tokens (see :func:`_opencode_substitute`), so a file whose tokens put in
    nothing is parsed as empty text, which fails. Text it cannot parse as
    JSONC, whitespace or comments alone included, stops the whole config from
    loading (``parse.ts:10-31``, ``config.ts:616``). So does a document whose
    top level is not an object or whose ``instructions`` is not a list of
    strings (``config.ts:188-199``, ``parse.ts:35-61``), a ``{file:path}`` it
    cannot read, a folder at *path*, and a read error other than those
    :func:`_read_error_refusal` lets through. A parse failure that goes away
    once the ``{env:NAME}`` values are escaped is ``"env"`` (see
    :func:`_escaped_read`). No other key is checked. Text nested deeper than
    Python's parser goes (about 1000 levels on Python 3.10), and a file that
    is not a regular file or is larger than ``_READ_LIMIT``, are not checked
    and get no note. A ``{file:path}`` the check does not read is checked as
    empty text inside a string value; anywhere else the file is not checked
    (see :class:`_UncheckedError`).
    """
    try:
        mode = path.stat()
        if stat.S_ISDIR(mode.st_mode):
            return _OpencodeFile("folder")
        if not stat.S_ISREG(mode.st_mode) or mode.st_size > _READ_LIMIT:
            return _OpencodeFile()
        data = path.read_bytes()
    except OSError as error:
        detail = _read_error_refusal(error)
        return _OpencodeFile() if detail is None else _OpencodeFile("read", detail)
    text = data.decode("utf-8-sig", errors="replace")
    if not text:
        return _OpencodeFile()
    try:
        document = _parse_jsonc(_opencode_substitute(text, path.parent))
    except _UnreadableReferenceError as error:
        return _OpencodeFile("reference", error.token)
    except _UncheckedError:
        return _OpencodeFile()
    except ValueError:
        return _escaped_read(text, path.parent)
    except RecursionError:
        return _OpencodeFile()
    return _OpencodeFile(_shape_refusal(document), document=document)


def _escaped_read(text: str, folder: Path) -> _OpencodeFile:
    """Return ``"env"`` when *text* parses with its ``{env:NAME}`` values escaped.

    Else ``"parse"``. OpenCode 2 tries that second parse only when the text
    holds an ``{env:`` token (v2.2.6 ``variable.ts:27-37``). The escaped
    document is checked for its shape too: OpenCode 1 refuses it for that
    once the values change, and OpenCode 2 skips it or ignores the value.
    When the escaped text depends on a ``{file:path}`` the check does not
    read, OpenCode 1 still cannot parse the text, but what OpenCode 2 makes
    of it is not known, so the result is ``"parse"`` and *unsure*.
    """
    # What JSON.stringify escapes, as the install's MCP note checks it.
    from apothem.harnesses.opencode.materializer import _UNSAFE

    if "{env:" not in text:
        return _OpencodeFile("parse")
    try:
        document = _parse_jsonc(_opencode_substitute(text, folder, escape=True))
    except _UncheckedError:
        return _OpencodeFile("parse", unsure=True)
    except (ValueError, RecursionError):
        return _OpencodeFile("parse")
    variables = sorted(
        {
            name
            for name in _OPENCODE_ENV_TOKEN.findall(text)
            if _UNSAFE.search(os.environ.get(name) or "")
        }
    )
    return _OpencodeFile(
        "env",
        document=document,
        escaped=_shape_refusal(document),
        variables=tuple(variables),
    )


def _shape_refusal(document: object) -> str | None:
    """Return the refusal for a *document* OpenCode 1's schema refuses.

    Only two shapes are checked: an object at the top level, and an
    ``instructions`` value, when there is one, that is a list of strings.
    """
    if not isinstance(document, dict):
        return "top-level"
    if "instructions" in document and _string_list(document) is None:
        return "instructions"
    return None


def _string_list(document: dict[str, object] | None) -> list[str] | None:
    """Return the top-level ``instructions`` of *document* when it lists strings.

    OpenCode 1 refuses a file whose ``instructions`` is anything else, so such
    a file replaces no list.
    """
    value = document.get("instructions") if document else None
    if not isinstance(value, list) or not all(isinstance(e, str) for e in value):
        return None
    return value


def _listed(target: Path) -> list[str]:
    """Return the strings in the top-level ``instructions`` list of *target*."""
    document = _jsonc_object(target)
    value = document.get("instructions") if document else None
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, str)]


def _opencode_joins_back(root: Path, target: Path) -> bool:
    """Return whether OpenCode 1 joins the list in *target* back in after the fold.

    It does when ``OPENCODE_CONFIG_DIR`` names *root*: OpenCode 1 reads
    ``opencode.json`` and ``opencode.jsonc`` there a second time and joins
    their lists (v1.19.5 ``config.ts:438-446``). It does when
    ``OPENCODE_CONFIG`` names *target* too: OpenCode 1 reads that file again
    and joins its list (``config.ts:415-416``).
    """
    from apothem.harnesses.opencode.materializer import same_path

    folder = os.environ.get("OPENCODE_CONFIG_DIR", "")
    config = os.environ.get("OPENCODE_CONFIG", "")
    return bool(folder and same_path(folder, root)) or bool(
        config and same_path(config, target)
    )


def _opencode_override_advisories(*, require_block: bool) -> list[dict[str, object]]:
    """Return a note for each global file that keeps OpenCode 1 from the written list.

    The folder is the one the OpenCode install writes to (its ``config_root``).
    OpenCode 1 folds ``config.json``, ``opencode.json`` and ``opencode.jsonc``
    there, in that order. Each of them that stops OpenCode 1 from loading its
    config (see :func:`_read_opencode_file`) gets a note; names that lead to
    one file through a symbolic link share one (see :func:`_note_names`). An
    ``opencode.jsonc`` that holds a top-level ``instructions`` list of strings,
    empty or not, gets a note too: OpenCode 1 reads that list in place of the
    one in ``opencode.json`` (see :func:`_opencode_replacing`). A missing file
    gets no note. With *require_block*, as for ``verify``, a note needs
    ``opencode.json`` to list an entry the install writes; the note for
    ``opencode.json`` itself also counts the profile document holding the
    Apothem block, since a file OpenCode 1 refuses may list nothing readable.
    An install or update that cannot parse ``opencode.json`` even as JSON5
    refuses it (``config.unparseable``) and stops before any note, so that
    file never gets the refusal and the note in one command. Never raises for
    a folder it cannot read.
    """
    # Imported here: the materializer imports lib modules this one sits beside.
    from apothem.harnesses.opencode import materializer

    try:
        root = materializer.config_root()
        target = root / _OPENCODE_WRITTEN
        entries = materializer.instruction_entries()
        notes = _opencode_notes(root, target, entries)
        if notes and require_block:
            notes = _installed_notes(notes, root, target, entries)
    except (OSError, RuntimeError, ValueError):
        return []
    return [
        {
            "harness": "opencode",
            "outcome": "advisory",
            "operation": "instruction_override",
            "path": str(path),
            "target": str(target),
            "message": message,
        }
        for path, message in notes
    ]


def _opencode_notes(
    root: Path, target: Path, entries: list[str]
) -> list[tuple[Path, str]]:
    """Return each file in *root* that needs a note, with the note's text."""
    reads = [
        (root / name, _read_opencode_file(root / name)) for name in _OPENCODE_FOLDED
    ]
    refused = [path for path, read in reads if read.refusal is not None]
    notes: list[tuple[Path, str]] = []
    for path, read in reads:
        if read.refusal is not None:
            names = _note_names(path, refused, target)
            if names:
                message = _opencode_refused_message(path, target, read, names)
                notes.append((path, message))
        elif path.name == _OPENCODE_LATER:
            replacing = _opencode_replacing(read, path, target)
            if replacing is not None:
                copy = all(entry in replacing for entry in entries)
                notes.append((path, _opencode_message(path, target, copy=copy)))
    return notes


def _note_names(path: Path, refused: list[Path], target: Path) -> list[Path]:
    """Return the names in *refused* whose note *path* carries; none if another does.

    Names in *refused* that lead to one file through a symbolic link share one
    note, given to *target* when it is one of them, else to the name that is
    not a link, else to the first in the order OpenCode 1 reads them.
    """

    def rank(name: Path) -> tuple[bool, bool, int]:
        return (name != target, name.is_symlink(), refused.index(name))

    same = [
        other
        for other in refused
        if other == path or _links_to(path, other) or _links_to(other, path)
    ]
    return same if min(same, key=rank) == path else []


def _installed_notes(
    notes: list[tuple[Path, str]], root: Path, target: Path, entries: list[str]
) -> list[tuple[Path, str]]:
    """Return the *notes* that ``verify`` gives, for a folder holding the install.

    All of them while *target* lists an entry in *entries*; else only the note
    for *target* itself, while the profile document the install writes holds
    the Apothem block.
    """
    from apothem.harnesses._shared.install_driver_merge import (
        PROFILE_DOCUMENT_RELATIVE,
    )

    listed = _listed(target)
    if any(entry in listed for entry in entries):
        return notes
    if not _holds_block(root / PROFILE_DOCUMENT_RELATIVE):
        return []
    return [note for note in notes if note[0] == target]


def _opencode_replacing(
    read: _OpencodeFile, path: Path, target: Path
) -> list[str] | None:
    """Return the list in the ``opencode.jsonc`` at *path* that hides *target*'s.

    ``None`` when nothing is hidden: the file holds no top-level
    ``instructions`` list of strings, is a symbolic link to *target*, or the
    environment makes OpenCode 1 join the written list back (see
    :func:`_opencode_joins_back`). A file that stops OpenCode 1's config is
    not passed here: OpenCode 1 reads it with the other global files (v1.19.5
    ``config.ts:272-274``) before ``OPENCODE_CONFIG_DIR`` or
    ``OPENCODE_CONFIG`` can join a list back, so its note stays.
    """
    if _links_to(path, target) or _opencode_joins_back(path.parent, target):
        return None
    document = read.document
    return _string_list(document if isinstance(document, dict) else None)


def _opencode_refused_message(
    path: Path, target: Path, read: _OpencodeFile, names: list[Path]
) -> str:
    """Return the note's text for a global file OpenCode 1 cannot load.

    OpenCode 1 turns the error into one that stops the config (v1.19.5
    ``config.ts:186`` and ``:616``). Its CLI reports a parse error as ``Config
    file at <path> is not valid JSON(C)`` followed by the file and the errors,
    and a schema error or a ``{file:path}`` it cannot read as ``Configuration
    is invalid at <path>`` (``packages/opencode/src/cli/error.ts:82`` and
    ``:109-118``); the note names each error without quoting it, since other
    entry points may show it another way. *names* are the names that share
    the note (see :func:`_note_names`). See :func:`_opencode_2_note` for what
    the note says of OpenCode 2.
    """
    detail = read.detail
    reasons = {
        "folder": (
            f"{path} is a folder, which OpenCode 1 cannot read as its "
            f"{path.name} file, so it stops with an error"
        ),
        "read": (
            f"OpenCode 1 cannot read {path} ({detail}), so it stops with an error"
        ),
        "reference": (
            f"OpenCode 1 cannot read the file that {detail} in {path} names, so "
            f'it stops with a "bad file reference" error'
        ),
        "parse": (
            f"OpenCode 1 cannot parse {path} as JSONC (JSON with comments and "
            f"trailing commas), so it stops with an error saying the file is "
            f"not valid JSON(C)"
        ),
        "env": (
            f"OpenCode 1 cannot parse {path} as JSONC once it puts in its "
            f"{{env:NAME}} values, because it does not escape a backslash, a "
            f"double quote or a control character in them, so it stops with an "
            f"error saying the file is not valid JSON(C)"
        ),
        "top-level": (
            f"OpenCode 1 needs an object at the top level of {path}, so it "
            f"stops with an error saying the configuration is invalid"
        ),
        "instructions": (
            f"OpenCode 1 needs the instructions value in {path} to be a list of "
            f"text, so it stops with an error saying the configuration is invalid"
        ),
    }
    remedies = {
        "folder": "until the folder is moved or renamed",
        "read": "until the file can be read or is removed",
        "reference": "until that file can be read or the reference is removed",
        "instructions": "until that value is a list of text or is removed",
    }
    refusal = read.refusal or "parse"
    remedy = remedies.get(refusal, "until the file is fixed or removed")
    extra = ""
    if refusal == "env":
        remedy, extra = _env_remedy(path, target, read)
    return (
        f"{reasons[refusal]} and loads none of its configuration, the Apothem "
        f"profile document and rules included, {remedy}.{extra}"
        f"{_opencode_2_note(path, target, read, names)}"
    )


def _env_remedy(path: Path, target: Path, read: _OpencodeFile) -> tuple[str, str]:
    """Return the remedy of an ``"env"`` note, and any sentence that follows it.

    Changing the values is enough only when the document they leave behind
    has the shape OpenCode 1 needs (see :func:`_shape_refusal`). An
    ``{env:NAME}`` that Apothem writes into the ``mcp`` block of *target* for
    a profile MCP server comes back on the next update when it is removed by
    hand, so the note names that server and the profile override that keeps
    the variable as it is, as the install's MCP note does (see
    ``materializer._mcp_reference_notes``).
    """
    if read.escaped == "top-level":
        return (
            "until the file is fixed or removed",
            " Changing those values is not enough: the top level of that file "
            "is not an object either, which OpenCode 1 also refuses.",
        )
    written = _written_variables(path.parent, target) if path == target else {}
    ours = [name for name in read.variables if name in written]
    if ours and len(ours) == len(read.variables):
        remedy = "until those values change"
    else:
        remedy = "until those values change or their references are removed"
    if read.escaped == "instructions":
        remedy += " and its instructions value is a list of text or is removed"
    if not ours:
        return remedy, ""
    servers = sorted({server for name in ours for server in written[name]})
    references = _joined([f"{{env:{name}}}" for name in ours])
    if len(servers) == 1:
        named = f"the MCP server {servers[0]}"
        restate = f"that server under harnesses.opencode.mcp_servers.{servers[0]}"
    else:
        named = f"the MCP servers {_joined(servers)}"
        restate = "each of those servers under harnesses.opencode.mcp_servers.<name>"
    return remedy, (
        f" Apothem writes {references} there for {named} in the profile, and an "
        f"update writes back a reference removed from {path.name}: to keep the "
        f"variable as it is, restate {restate} (an override replaces the whole "
        f"server) with the value saved in a file and written as a {{file:path}} "
        f"that names it."
    )


def _joined(names: list[str]) -> str:
    """Return *names* as a list in prose: ``a``, ``a and b``, ``a, b and c``."""
    if len(names) < 2:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _written_variables(root: Path, target: Path) -> dict[str, list[str]]:
    """Return each variable an ``{env:NAME}`` Apothem wrote in *target* names.

    Each maps to the MCP servers it was written for, read from what the
    current install record says Apothem owns in *target*: a server under
    ``mcp.<name>``, or one an operator moved to ``mcp.servers.<name>`` (see
    ``materializer.relocated_entries``).
    """
    from apothem.harnesses._shared.install_driver_ownership import prior_ownership

    owned = prior_ownership("opencode", root, target)
    found: dict[str, list[str]] = {}
    for entry in owned if isinstance(owned, tuple) else ():
        where = entry.path
        if len(where) < 2 or where[0] != "mcp":
            continue
        server = where[2] if where[1] == "servers" and len(where) > 2 else where[1]
        for text in _strings_in(entry.value):
            for name in _OPENCODE_ENV_TOKEN.findall(text):
                servers = found.setdefault(name, [])
                if server not in servers:
                    servers.append(server)
    return found


def _strings_in(value: object) -> list[str]:
    """Return every string in *value*, a string, list or mapping at any depth."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        value = list(value.values())
    if isinstance(value, list):
        return [text for item in value for text in _strings_in(item)]
    return []


def _opencode_2_note(
    path: Path, target: Path, read: _OpencodeFile, names: list[Path]
) -> str:
    """Return what the note says of OpenCode 2 for *path*, with a leading space.

    OpenCode 2 (v2.2.6) reads no ``config.json``
    (``packages/core/src/config/discovery.ts:12``), but reads the file a
    ``config.json`` leads to through a symbolic link when one of *names*, the
    names that share the note, is ``opencode.json`` or ``opencode.jsonc``.
    """
    if path.name != _OPENCODE_FOLDED[0]:
        return _opencode_2_sentence(path, target, read)
    alias = next((name for name in names if name.name != path.name), None)
    if alias is None:
        return f" OpenCode 2 does not read {path.name}."
    return (
        f" OpenCode 2 reads that file as {alias.name}, not as {path.name}."
        f"{_opencode_2_sentence(alias, target, read)}"
    )


def _opencode_2_sentence(path: Path, target: Path, read: _OpencodeFile) -> str:
    """Return what OpenCode 2 does with the file it reads as *path*.

    It skips a file it cannot parse or whose top level is not an object, and
    loads the others (v2.2.6 ``packages/core/src/config.ts:136-174`` and
    ``:266-270``, ``config/normalize.ts:57-64``). It escapes the
    ``{env:NAME}`` values when the text would not parse otherwise
    (``config/variable.ts:27-37``) and puts in empty text for a
    ``{file:path}`` it cannot read (``variable.ts:63-73``). It ignores an
    ``instructions`` value that is not a list, a string included, and drops
    the items of a list that are not strings (``normalize.ts:228-229``, where
    ``decodeList`` at ``:690-706`` gives ``[]`` for a value that is not an
    array, and ``instructions`` is kept only for an array). The note says
    nothing of OpenCode 2 for a folder or a read error, which were not
    checked, or when the escaped text depends on a ``{file:path}`` the check
    does not read. Starts with a space.
    """
    refusal = read.refusal
    if read.unsure:
        return ""
    if refusal == "reference":
        return " OpenCode 2 puts in empty text for that reference instead."
    if refusal == "instructions":
        return f" OpenCode 2 instead {_dropped(read.document)}."
    skipped = (
        " so the entries Apothem lists there do not reach it either."
        if path == target
        else f" and still loads {target.name}."
    )
    if refusal == "env":
        escapes = (
            " OpenCode 2 escapes those values when the file would not parse otherwise"
        )
        if read.escaped == "top-level":
            return (
                f"{escapes}, but then skips that file, whose top level is not an "
                f"object,{skipped}"
            )
        if read.escaped == "instructions":
            return f"{escapes}, so it loads that file, but {_dropped(read.document)}."
        return f"{escapes}, so it parses that file."
    if refusal not in ("parse", "top-level"):
        return ""
    if path == target:
        return f" OpenCode 2 skips that file too,{skipped}"
    return f" OpenCode 2 skips that file{skipped}"


def _dropped(document: object) -> str:
    """Return what OpenCode 2 does with the ``instructions`` value of *document*."""
    value = document.get("instructions") if isinstance(document, dict) else None
    if isinstance(value, list):
        return "drops what in that list is not text"
    return "ignores that value, which is not a list"


def _opencode_message(path: Path, target: Path, *, copy: bool) -> str:
    """Return the note's text for an ``opencode.jsonc`` at *path*.

    *copy* is True when that file's list already holds every entry the install
    writes: OpenCode 1 loads them today, from a copy no install refreshes.
    """
    reason = (
        f"OpenCode 1 reads the instructions list in {path} in place of the one "
        f"in {target}: it loads {target.name} and then {path.name} from "
        f"{target.parent}, and a list in the later file replaces the earlier "
        f"one, even an empty list. OpenCode 2 reads both lists. "
    )
    if copy:
        return reason + (
            f"The list in {path.name} holds its own copy of every entry Apothem "
            f"writes, which installs and updates do not refresh: remove the "
            f"instructions key from {path.name}, or move its other entries into "
            f"the list in {target.name}, where installs and updates keep the "
            f"entries they did not write."
        )
    return reason + (
        f"The profile document and rules Apothem lists in {target.name} "
        f"therefore do not reach OpenCode 1. Remove the instructions key from "
        f"{path.name}, or move its entries into the list in {target.name}, where "
        f"installs and updates keep the entries they did not write."
    )


# --- MCP profile advisories ---------------------------------------------------

# The MCP specification deprecates the HTTP+SSE transport in favour of
# Streamable HTTP (https://modelcontextprotocol.io/specification/2026-07-28/deprecated,
# retrieved 2026-10-02).
_DEPRECATED_TRANSPORTS: dict[str, str] = {"sse": "streamable-http"}

_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "::1", "0:0:0:0:0:0:0:1"})

# Token shapes that mark a literal credential. Each pattern matches the secret
# itself, so a ``${VAR}`` reference never matches. The bearer pattern needs a
# token of at least 20 characters, which leaves short placeholders alone.
_CREDENTIAL_SHAPES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "GitHub token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    ),
    ("API key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
    ("bearer token", re.compile(r"(?i)^\s*bearer\s+[A-Za-z0-9._~+/=-]{20,}\s*$")),
)


def _mcp_entry(
    profile_path: Path, operation: str, field: str, message: str
) -> dict[str, object]:
    return {
        "harness": None,
        "outcome": "advisory",
        "operation": operation,
        "path": str(profile_path),
        "field": field,
        "message": message,
    }


def _is_loopback(host: str) -> bool:
    host = host.strip("[]").lower()
    if host in _LOOPBACK_HOSTS or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _server_advisories(
    prefix: str, server: Mapping[str, object], profile_path: Path
) -> list[dict[str, object]]:
    advisories: list[dict[str, object]] = []
    transport = str(server.get("transport", ""))
    replacement = _DEPRECATED_TRANSPORTS.get(transport)
    if replacement is not None:
        advisories.append(
            _mcp_entry(
                profile_path,
                "mcp_deprecated_transport",
                f"{prefix}.transport",
                f"{prefix}.transport is '{transport}', a transport the MCP "
                f"specification deprecates. Set it to '{replacement}' if the "
                "server supports it.",
            )
        )
    url = server.get("url")
    if isinstance(url, str):
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if parsed.scheme.lower() == "http" and host and not _is_loopback(host):
            advisories.append(
                _mcp_entry(
                    profile_path,
                    "mcp_plain_http",
                    f"{prefix}.url",
                    f"{prefix}.url uses plain http:// to {host}, so requests and "
                    "their headers travel unencrypted. Use an https:// URL.",
                )
            )
    for location in ("headers", "env"):
        values = server.get(location)
        if not isinstance(values, Mapping):
            continue
        for key, value in values.items():
            if not isinstance(value, str) or "${" in value:
                continue
            kind = next(
                (name for name, shape in _CREDENTIAL_SHAPES if shape.search(value)),
                None,
            )
            if kind is None:
                continue
            field = f"{prefix}.{location}.{key}"
            advisories.append(
                _mcp_entry(
                    profile_path,
                    "mcp_literal_credential",
                    field,
                    f"{field} holds what looks like a literal {kind}. Apothem "
                    "copies MCP values into each harness config file as written. "
                    "Keep the secret in an environment variable and write the "
                    "value as a reference such as ${GITHUB_TOKEN}.",
                )
            )
    return advisories


def mcp_profile_advisories(
    profile: Mapping[str, object], profile_path: Path
) -> list[dict[str, object]]:
    """Return advisories for the MCP servers a shared *profile* declares.

    Checks the top-level ``mcp_servers`` inventory and every
    ``harnesses.<id>.mcp_servers`` override for three conditions: a deprecated
    transport (``sse``; the advisory names ``streamable-http``), a plain
    ``http://`` URL to a host that is not loopback, and a ``headers`` or ``env``
    value shaped like a literal credential (``ghp_``/``github_pat_``, ``sk-``,
    ``xox*-``, or ``Bearer`` with a long token). A value that contains a
    ``${VAR}`` reference is never flagged. Advisories name the profile field
    and never echo a credential value.
    """
    advisories: list[dict[str, object]] = []
    inventories: list[tuple[str, object]] = [
        ("mcp_servers", profile.get("mcp_servers"))
    ]
    harnesses = profile.get("harnesses")
    if isinstance(harnesses, Mapping):
        for harness_id, override in harnesses.items():
            if isinstance(override, Mapping):
                inventories.append(
                    (f"harnesses.{harness_id}.mcp_servers", override.get("mcp_servers"))
                )
    for prefix, servers in inventories:
        if not isinstance(servers, Mapping):
            continue
        for name, server in servers.items():
            if isinstance(server, Mapping):
                advisories.extend(
                    _server_advisories(f"{prefix}.{name}", server, profile_path)
                )
    return advisories


__all__ = [
    "hook_review_advisories",
    "instruction_override_advisories",
    "mcp_profile_advisories",
    "owner_of_record",
    "shared_root_advisories",
]
