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
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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
            message = (
                f"{root.path} is shared: {readers} also load it. Installing "
                f"or uninstalling {_display_name(root.owner)} changes what "
                "those tools load."
            )
            advisories.append(_entry(public_id, root, resolved, "owner", message))
        elif _holds_apothem_content(resolved):
            message = (
                f"{_display_name(public_id)} also loads {root.path}, which holds "
                f"Apothem content from the {_display_name(root.owner)} install."
            )
            advisories.append(_entry(public_id, root, resolved, "reader", message))
    return advisories


__all__ = ["shared_root_advisories"]
