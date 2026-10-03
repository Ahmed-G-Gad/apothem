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

MCP servers. :func:`mcp_profile_advisories` reads the shared profile's MCP
inventory and flags a deprecated transport, plain ``http://`` to a remote host,
and literal credentials in ``headers`` or ``env``, which an install would copy
into every harness config file that takes MCP servers.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import apothem
from apothem.lib.harness_materializer import APOTHEM_BLOCK_BEGIN
from apothem.lib.harness_registry import (
    SHARED_ROOTS,
    SharedRoot,
    get_harness_entry,
)

_HOME_PREFIX = "~/"
_PROJECT_PREFIX = "<project>/"


def _display_name(public_id: str) -> str:
    return get_harness_entry(public_id).display_name


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


def _holds_apothem_content(resolved: Path) -> bool:
    """Return True when *resolved* carries content an Apothem install wrote."""
    if resolved.is_dir():
        return any(
            (resolved / name / "SKILL.md").is_file() for name in _apothem_skill_names()
        )
    if resolved.is_file():
        try:
            return APOTHEM_BLOCK_BEGIN in resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False
    return False


def _entry(
    public_id: str, root: SharedRoot, resolved: Path, role: str, message: str
) -> dict[str, object]:
    return {
        "harness": public_id,
        "outcome": "advisory",
        "operation": "shared_root",
        "role": role,
        "path": str(resolved),
        "owner": root.owner,
        "readers": list(root.readers),
        "message": message,
    }


def shared_root_advisories(
    public_id: str, *, home: Path, project: Path | None
) -> list[dict[str, object]]:
    """Return the shared-root advisories for installing *public_id*.

    For each shared root *public_id* owns, one ``owner`` advisory names every
    reader. For each shared root *public_id* reads that already holds Apothem
    content (an Apothem skill folder in a skills root, or the Apothem managed
    block in an instruction file), one ``reader`` advisory names the owner whose
    install placed it there. Project roots are skipped when *project* is
    ``None``. Reads the filesystem; writes nothing.
    """
    advisories: list[dict[str, object]] = []
    for root in SHARED_ROOTS:
        if public_id != root.owner and public_id not in root.readers:
            continue
        resolved = _resolve(root.path, home=home, project=project)
        if resolved is None:
            continue
        if public_id == root.owner:
            readers = ", ".join(_display_name(reader) for reader in root.readers)
            single = len(root.readers) == 1
            message = (
                f"{root.path} is shared: {readers} also "
                f"{'loads' if single else 'load'} it. Installing or uninstalling "
                f"{_display_name(root.owner)} changes what "
                f"{'that tool loads' if single else 'those tools load'}."
            )
            advisories.append(_entry(public_id, root, resolved, "owner", message))
        elif _holds_apothem_content(resolved):
            message = (
                f"{_display_name(public_id)} also loads {root.path}, which holds "
                f"Apothem content from the {_display_name(root.owner)} install."
            )
            advisories.append(_entry(public_id, root, resolved, "reader", message))
    return advisories


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


__all__ = ["mcp_profile_advisories", "shared_root_advisories"]
