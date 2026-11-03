# SPDX-License-Identifier: MIT

"""Materializer for the opencode harness — renders JSON config.

OpenCode combines every file its ``instructions`` list resolves to into every
session (https://opencode.ai/docs/rules/, retrieved 2026-10-03). The list
therefore names the profile document (the operator's identity and
preferences, and where Apothem's support files are installed) and only the
rules whose source frontmatter sets ``alwaysApply: true``: the core rules and
the rule index. OpenCode scopes no rule by path, so every other rule stays
installed under the support tree and is read on demand: the index names each
rule and when to read it, and a skill or command that needs one cites it.

An entry starting with ``~/`` is expanded against the home directory, and an
absolute entry is matched as a glob on its final segment, so an explicit file
path names exactly that file. A relative entry is resolved against the project
directory, not the config file, which is why every entry is home-anchored
(absolute when the config folder is outside the home directory). These
semantics were observed at opencode-ai 1.19.0 on 2026-10-14, and v2.2.5 keeps
them (``packages/core/src/config/plugin/instruction.ts:99-112``).

OpenCode 1 and OpenCode 2 read the same folder (see :func:`config_root`). OpenCode
2 reads the OpenCode 1 shapes this module writes in place, converting them in
memory; an operator may still convert an MCP server Apothem wrote to OpenCode
2's own shape, which :func:`relocated_entries` accounts for.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from pathlib import Path
from string import Template
from typing import Any, Final

from apothem.harnesses._shared import install_driver
from apothem.lib import install_ledger, lenient_json
from apothem.lib.frontmatter import field_value
from apothem.lib.install_ledger import OwnedEntry
from apothem.lib.profile import coerce_profile
from apothem.lib.profile_projection import mcp_servers_for, render_mcp_opencode
from apothem.lib.propagation import load_manifest

#: The default OpenCode configuration directory, relative to the home directory.
CONFIG_DIR: Final[str] = ".config/opencode"


def config_root() -> Path:
    """Return the folder OpenCode loads its global configuration from.

    Both OpenCode lines read ``$XDG_CONFIG_HOME/opencode`` when
    ``XDG_CONFIG_HOME`` is set, else ``~/.config/opencode`` (v1.19.5
    ``packages/core/src/global.ts:13``, through xdg-basedir; v2.2.5
    ``packages/util/src/global-roots.ts:7``). A value that is not an absolute
    path, or that names a filesystem root, is not used (see
    :func:`install_notes`): OpenCode would resolve a relative value against
    its own working directory, which an install cannot match, and a filesystem
    root would make the whole drive the allowed write boundary.
    ``OPENCODE_CONFIG_DIR`` is not followed, because the two lines disagree
    on it: OpenCode 1 reads that folder as well as this one, OpenCode 2
    instead of it (v2.2.5 ``packages/util/src/global.ts:79``).

    When ``XDG_CONFIG_HOME`` is unset, or names the same folder as
    ``~/.config`` (through a link, a junction or a change of case), an install
    already recorded for that folder keeps the spelling it is recorded under
    (see :func:`_default_spellings`), so it stays one install. Otherwise the
    folder is ``XDG_CONFIG_HOME`` as resolved, or ``~/.config/opencode``.
    """
    default = Path.home() / ".config"
    configured = _xdg_config_home()
    preferred = (default if configured is None else configured) / "opencode"
    if configured is not None and not _names_same_folder(configured, default):
        return preferred
    return next(
        (spelling for spelling in _default_spellings() if _recorded(spelling)),
        preferred,
    )


def _default_spellings() -> list[Path]:
    """Return the spellings an install in ``~/.config/opencode`` is recorded under.

    ``~/.config/opencode`` as written, then through the folder ``~/.config``
    leads to when that is a link staying inside the home. A link that leaves
    the home is not followed, so a record there never takes a write out of the
    home while ``XDG_CONFIG_HOME`` is unset (the write guard refuses that link
    instead). Should both spellings hold a record, the first wins.
    """
    default = Path.home() / ".config"
    spellings = [default / "opencode"]
    resolved = install_driver._normalized(default)
    if resolved != default and install_driver._within_allowed_root(
        resolved, Path.home()
    ):
        spellings.append(resolved / "opencode")
    return spellings


def _recorded(root: Path) -> bool:
    """Return True when an OpenCode install is recorded at *root*, spelled as it is."""
    try:
        record = install_ledger.current_install_record("opencode", root=root)
    except (install_ledger.LedgerError, OSError):
        return False
    return record is not None


def _names_same_folder(first: Path, second: Path) -> bool:
    """Return True when *first* and *second* name one folder.

    When both exist they are compared by file identity, which also matches a
    change of case on a case-insensitive volume, a bind mount, a link or a
    junction. Otherwise, or when the filesystem reports no inode numbers (some
    network and FUSE mounts do), their resolved paths are compared.
    """
    try:
        stats = [first.stat(), second.stat()]
    except OSError:
        stats = []
    if stats and all(stat.st_ino for stat in stats):
        return os.path.samestat(stats[0], stats[1])
    return install_driver._normalized(first) == install_driver._normalized(second)


def _xdg_config_home() -> Path | None:
    """Return ``XDG_CONFIG_HOME`` when it names an absolute folder, else ``None``."""
    value = os.environ.get("XDG_CONFIG_HOME", "")
    if not value:
        return None
    path = Path(os.path.normpath(value))
    if not path.is_absolute() or path.parent == path:
        return None
    # The install record matches a root by its exact spelling, so the folder
    # is named as it is on disk: a change of case on Windows, or a link to
    # it, then names the same install.
    return path.resolve(strict=False)


def _anchored_root() -> str:
    """Return the config folder the way an ``instructions`` entry names it.

    Under the home directory it is ``~/``-anchored, which OpenCode expands;
    elsewhere it is the absolute path with forward slashes. Both sides are
    compared with ``..`` segments folded and, on Windows, case folded, but
    links are not resolved: a ``~/.config/opencode`` that is a link keeps
    naming the link, as OpenCode itself does.
    """
    root = os.path.normpath(config_root())
    home = os.path.normpath(Path.home())
    if not os.path.normcase(root).startswith(os.path.normcase(home) + os.sep):
        return Path(root).as_posix()
    return f"~/{Path(root[len(home) + 1 :]).as_posix()}"


#: The single ``instructions`` entry earlier releases wrote: a glob that made
#: OpenCode load every installed rule, path-scoped ones included, at launch.
LEGACY_RULES_GLOB: Final[str] = "~/.config/opencode/.apothem/support/rules/*.md"

#: Rules that earlier releases listed in ``instructions`` by explicit path
#: because their source set ``alwaysApply: true``, and that now load on demand
#: through the rule index. The name list is fixed: the frontmatter no longer
#: says which rules these were.
_DEMOTED_RULES: Final[tuple[str, ...]] = (
    "agent-orchestration",
    "agile-sprints",
    "authoritative-referencing",
    "auto-memory",
    "canonical-layout",
    "clean-room-generation",
    "cognitive-identity",
    "definitiveness",
    "disclosure-ledger",
    "etc-extension",
    "expertise-posture",
    "freshness-facade",
    "host-discovery",
    "interactive-questions",
    "multi-agent-workflow",
    "operational-mandates",
    "option-annotation",
    "persistent-conventions-vigilance",
    "pre-emission-gate",
    "production-ready-prs",
    "source-accessibility",
    "systemic-participation",
    "ten-dimension-check",
    "tool-use-discipline",
)

#: The ``instructions`` entries those releases wrote for :data:`_DEMOTED_RULES`.
RETIRED_ALWAYS_ON_RULES: Final[tuple[str, ...]] = tuple(
    f"{LEGACY_RULES_GLOB.removesuffix('*.md')}{name}.md" for name in _DEMOTED_RULES
)


def always_on_rule_instructions() -> list[str]:
    """Return the ``instructions`` entries for the always-on rules.

    Read at materialize time from the opencode ``rules/`` install entry of the
    canonical propagation manifest (not an install plan a caller may have
    trimmed): its source directory supplies the rules (minus the manifest's
    excluded files), and its target directory, named the way
    :func:`_anchored_root` names the config folder, supplies the installed
    location. A rule is listed when its frontmatter sets
    ``alwaysApply: true``. Entries are sorted by file name.

    Raises:
        RuntimeError: When the manifest has no opencode ``rules/`` entry.
    """
    rules = load_manifest()["opencode"]
    entry = next(
        (item for item in rules.install if item.source.rstrip("/") == "rules"), None
    )
    if entry is None:
        raise RuntimeError(
            "propagation manifest has no opencode 'rules/' install entry"
        )
    source_dir = install_driver.resolve_source(entry.source)
    target_dir = Template(entry.target).substitute(HARNESS_ROOT=_anchored_root())
    names = sorted(
        path.name
        for path in source_dir.glob("*.md")
        if not install_driver._is_excluded_path(path, rules.exclude)
        and (field_value(path, "alwaysApply") or "").strip().lower() == "true"
    )
    return [f"{target_dir.rstrip('/')}/{name}" for name in names]


def profile_document_instruction() -> str:
    """Return the ``instructions`` entry for the projected profile document.

    The install projects the shared profile into
    ``<harness root>/apothem/rules/00-apothem-profile.md``; OpenCode reads no
    other file Apothem writes for it, so without this entry the operator's
    identity, preferences and the support-file locations never reach it.
    """
    return f"{_anchored_root()}/{install_driver.PROFILE_DOCUMENT_RELATIVE}"


def instruction_entries() -> list[str]:
    """Return every ``instructions`` entry: the profile document, then the rules."""
    return [profile_document_instruction(), *always_on_rule_instructions()]


def materialize_native_config(profile: dict[str, Any]) -> str:
    """Render the opencode native configuration from *profile*.

    Renders the ``instructions`` list (see :func:`instruction_entries`) plus
    the profile's MCP inventory into opencode's native ``mcp`` surface.
    Returns a JSON string ready to be written to ``output_path``.
    """
    for_harness = coerce_profile(profile).for_harness("opencode")
    config: dict[str, Any] = {
        "$schema": "https://opencode.ai/config.json",
        "instructions": instruction_entries(),
    }
    mcp = render_mcp_opencode(mcp_servers_for(for_harness))
    if mcp:
        config["mcp"] = mcp
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"


def retired_entries(profile: dict[str, Any]) -> tuple[OwnedEntry, ...]:
    """Return what earlier releases wrote that this release no longer writes.

    Earlier releases listed :data:`LEGACY_RULES_GLOB` in ``instructions``, and
    later ones listed every ``alwaysApply`` rule by path, among them the
    :data:`RETIRED_ALWAYS_ON_RULES` this release leaves to the rule index. An
    install, update or uninstall over such a config removes those entries; the
    operator's own ``instructions`` entries are kept. A config whose install
    record predates ownership recording cannot tell the retired paths from an
    operator's own, so this list is what removes them.
    """
    del profile  # the retired entries do not depend on the profile
    return tuple(
        OwnedEntry(("instructions",), "item", entry)
        for entry in (LEGACY_RULES_GLOB, *RETIRED_ALWAYS_ON_RULES)
    )


#: Keys OpenCode 2 reads as members of the ``mcp`` block, not as server names.
_MCP_BLOCK_MEMBERS: Final[frozenset[str]] = frozenset({"servers", "timeout"})


def relocated_entries(
    owned: tuple[OwnedEntry, ...], current: str | None
) -> tuple[OwnedEntry, ...]:
    """Return Apothem's MCP servers that an operator converted to OpenCode 2's shape.

    OpenCode 2 keeps a server under ``mcp.servers.<name>``
    (https://opencode.ai/v2/docs/migrate-v1/) and reads a bare ``mcp.<name>``
    in place, converting it in memory: ``enabled`` becomes the inverse
    ``disabled`` and the other fields carry over (v2.2.5
    ``packages/core/src/v1/config/migrate.ts:81-108``). It never rewrites the
    file, but an operator may convert it, by hand or by asking OpenCode to.

    A server under ``mcp.servers`` in *current* (the config's text) is taken
    for one Apothem wrote only when Apothem wrote that whole server, its
    ``mcp.<name>`` is gone from *current* (the entry moved rather than being
    copied), and it equals that server as a whole, as written or with
    ``enabled`` converted. It is returned as one ``key`` entry holding the
    whole server, plus the ``mcp.servers`` mapping, which goes only once
    empty, so an update or uninstall removes it whole or not at all. An
    operator's own server of the same name, a converted server the operator
    edited, and one the operator disabled are left as they are.
    """
    mcp = _mcp_block(current)
    servers = mcp.get("servers") if mcp is not None else None
    if mcp is None or not isinstance(servers, dict):
        return ()
    moved: list[OwnedEntry] = []
    for name, server in _owned_servers(owned).items():
        if name in mcp:
            continue
        found = servers.get(name)
        if any(found == shape for shape in _converted_shapes(server)):
            moved.append(OwnedEntry(("mcp", "servers", name), "key", found))
    if moved:
        moved.append(OwnedEntry(("mcp", "servers"), "container"))
    return tuple(moved)


def _mcp_block(current: str | None) -> dict[str, object] | None:
    """Return the ``mcp`` mapping of the config text *current*, if it has one."""
    if not current:
        return None
    try:
        document = json.loads(current)
    except json.JSONDecodeError:
        try:
            document = lenient_json.loads(current)
        except lenient_json.LenientJSONError:
            return None
    mcp = document.get("mcp") if isinstance(document, dict) else None
    return mcp if isinstance(mcp, dict) else None


def _owned_servers(owned: tuple[OwnedEntry, ...]) -> dict[str, dict[str, object]]:
    """Return each MCP server Apothem wrote whole, rebuilt from *owned*.

    A server counts when its ``mcp.<name>`` mapping is an owned container (the
    install created it); its keys and list items come back in recorded order.
    """
    servers: dict[str, dict[str, object]] = {
        entry.path[1]: {}
        for entry in owned
        if entry.kind == "container"
        and len(entry.path) == 2
        and entry.path[0] == "mcp"
        and entry.path[1] not in _MCP_BLOCK_MEMBERS
    }
    for entry in owned:
        server = servers.get(entry.path[1]) if len(entry.path) > 2 else None
        if server is None or entry.path[0] != "mcp" or entry.kind == "container":
            continue
        node = server
        for key in entry.path[2:-1]:
            child = node.setdefault(key, {})
            if not isinstance(child, dict):
                break
            node = child
        else:
            if entry.kind == "key":
                node[entry.path[-1]] = entry.value
            else:
                items = node.setdefault(entry.path[-1], [])
                if isinstance(items, list):
                    items.append(entry.value)
    return servers


def _converted_shapes(server: dict[str, object]) -> list[dict[str, object]]:
    """Return *server* as written and as a conversion to OpenCode 2's shape."""
    enabled = server.get("enabled")
    rest = {key: value for key, value in server.items() if key != "enabled"}
    shapes = [server]
    if isinstance(enabled, bool):
        shapes.append({**rest, "disabled": not enabled})
        if enabled:
            shapes.append(rest)
    return shapes


#: A braced reference OpenCode leaves as written; a doubled ``$${...}`` too.
_BRACED: Final[re.Pattern[str]] = re.compile(r"\$?\$\{[^}]*\}")

#: A bare ``$NAME`` reference.
_BARE: Final[re.Pattern[str]] = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")

#: An ``{env:NAME}`` reference the install wrote.
_ENV: Final[re.Pattern[str]] = re.compile(r"\{env:([A-Za-z_][A-Za-z0-9_]*)\}")

#: Characters a JSON string cannot hold as they are. OpenCode inserts an
#: ``{env:NAME}`` value into the config text unescaped (U+007F is legal).
_UNSAFE: Final[re.Pattern[str]] = re.compile(r'[\\"\x00-\x1f]')


def install_notes(root: Path, profile: dict[str, Any]) -> list[str]:
    """Return what keeps OpenCode from loading the install at *root* as written.

    One note each when ``OPENCODE_CONFIG_DIR`` names another folder (OpenCode
    2 then reads that folder instead of *root*), when ``XDG_CONFIG_HOME`` is
    set but not used (see :func:`config_root`), when the files of an earlier
    install are still in ``~/.config/opencode`` while *root* is elsewhere, and
    for each MCP server whose rendered entry keeps a ``$`` reference OpenCode
    does not expand.
    """
    notes: list[str] = []
    override = os.environ.get("OPENCODE_CONFIG_DIR", "")
    if override and not _same_folder(override, root):
        notes.append(
            f"OPENCODE_CONFIG_DIR is set to {override}. OpenCode 1 reads that "
            f"folder as well as {root}, where Apothem installed, but OpenCode 2 "
            f"reads it instead, so OpenCode 2 does not load this install. Unset "
            f"OPENCODE_CONFIG_DIR or set it to {root}."
        )
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg and _xdg_config_home() is None:
        notes.append(
            f"XDG_CONFIG_HOME is set to {xdg}, which is not an absolute folder "
            f"below the filesystem root, so Apothem installed into {root}. "
            "OpenCode reads XDG_CONFIG_HOME as it is and does not load this "
            "install. Set XDG_CONFIG_HOME to an absolute folder or unset it."
        )
    notes.extend(_earlier_root_notes(root))
    notes.extend(_mcp_reference_notes(profile))
    return notes


def _same_folder(configured: str, root: Path) -> bool:
    """Return True when *configured* names *root* the way OpenCode reads it.

    OpenCode does not expand ``~`` and resolves a relative path against its
    own working directory, so only an absolute path can name *root*.
    """
    path = Path(configured)
    if not path.is_absolute():
        return False
    return _names_same_folder(path, root)


def _earlier_root_notes(root: Path) -> list[str]:
    """Return a note when an earlier install is still in the default folder.

    Only while its files are there: when they are gone (the folder was moved
    or deleted) nothing is left to remove, and an uninstall would find nothing
    installed.
    """
    default = Path.home() / CONFIG_DIR
    if _names_same_folder(default, root):
        return []
    if not any(
        _recorded(spelling)
        and install_driver.detect_install("opencode", harness_root=spelling)
        for spelling in _default_spellings()
    ):
        return []
    return [
        f"An earlier Apothem install is still in {default}, which OpenCode "
        "does not read while XDG_CONFIG_HOME names another folder. To remove "
        "it, run apothem uninstall --harness opencode with XDG_CONFIG_HOME "
        "unset."
    ]


def _mcp_reference_notes(profile: dict[str, Any]) -> list[str]:
    """Return what each MCP server's ``$`` references do in OpenCode.

    For each server: where a ``${...}`` form is left as written (a command
    argument included) or an environment or header value holds a bare
    ``$NAME``; where a ``$${...}`` is copied unchanged; and each ``{env:NAME}``
    whose variable now holds a backslash, a double quote or a control
    character. A note names the place (``environment.TOKEN``), never the text,
    so no part of a literal secret reaches install output.

    OpenCode inserts an ``{env:NAME}`` value into the config text it reads
    without escaping it (v1.19.5 ``packages/opencode/src/config/variable.ts``;
    v2.2.5 ``packages/core/src/config/variable.ts`` escapes it only when that
    text would not parse), so such a value can stop OpenCode 1 from reading
    the file, and in both lines a ``\\t`` or ``\\n`` in it reaches the server as
    a control character.
    """
    for_harness = coerce_profile(profile).for_harness("opencode")
    notes: list[str] = []
    for name, entry in render_mcp_opencode(mcp_servers_for(for_harness)).items():
        unexpanded: set[str] = set()
        doubled: set[str] = set()
        variables: set[str] = set()
        for where, value in _located_strings(entry):
            braced = _BRACED.findall(value)
            secret = where.startswith(("environment.", "headers."))
            if any(not m.startswith("$$") for m in braced) or (
                secret and _BARE.search(value)
            ):
                unexpanded.add(where)
            if any(m.startswith("$$") for m in braced):
                doubled.add(where)
            if where != "command":
                variables.update(_ENV.findall(value))
        if unexpanded:
            notes.append(
                f"MCP server {name}: OpenCode does not expand the $ reference in "
                f"{', '.join(sorted(unexpanded))}, so the server receives that "
                "text as written. In an environment, header or URL value, a "
                "plain ${NAME} is written as {env:NAME}, which OpenCode "
                "substitutes."
            )
        if doubled:
            notes.append(
                f"MCP server {name}: the $${{...}} in "
                f"{', '.join(sorted(doubled))} is copied unchanged."
            )
        for variable in sorted(variables):
            if _UNSAFE.search(os.environ.get(variable, "")):
                notes.append(
                    f"MCP server {name}: {variable} holds a backslash, a double "
                    "quote or a control character. OpenCode inserts "
                    f"{{env:{variable}}} into the config text it reads without "
                    "escaping it, so OpenCode 1 may not read the file, and in "
                    "both lines a \\t or \\n in the value can reach the server as "
                    "a control character. Restate that server under "
                    f"harnesses.opencode.mcp_servers.{name} (an override "
                    "replaces the whole server) with the value as {file:path}, "
                    "so the other tools keep the ${NAME} reference."
                )
    return notes


def _located_strings(entry: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Yield each string value of a rendered server with the place it sits."""
    for item in entry.get("command") or []:
        if isinstance(item, str):
            yield "command", item
    url = entry.get("url")
    if isinstance(url, str):
        yield "url", url
    for key in ("environment", "headers"):
        values = entry.get(key)
        if isinstance(values, dict):
            for field, value in values.items():
                if isinstance(value, str):
                    yield f"{key}.{field}", value
