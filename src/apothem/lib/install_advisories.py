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
has text and is not a symbolic link to the instruction file itself. Install and
update print the note; verify prints it only while the instruction file holds
the Apothem block.

MCP servers. :func:`mcp_profile_advisories` reads the shared profile's MCP
inventory and flags a deprecated transport, plain ``http://`` to a remote host,
and literal credentials in ``headers`` or ``env``, which an install would copy
into every harness config file that takes MCP servers.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
from pathlib import Path
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
    except OSError:
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
    """Return True when *resolved* carries content an Apothem install wrote."""
    if resolved.is_dir():
        if any(
            (resolved / name / "SKILL.md").is_file() for name in _apothem_skill_names()
        ):
            return True
        return any(
            (resolved / f"{name}{suffix}").is_file()
            for name in _apothem_agent_names()
            for suffix in _AGENT_SUFFIXES
        )
    if resolved.is_file():
        try:
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
    except OSError:
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
    cannot read.
    """
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
