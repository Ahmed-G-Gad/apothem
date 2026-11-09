# SPDX-License-Identifier: MIT

"""What this release writes at a target, for an install recorded without digests.

An install record written before file digests existed (``LedgerTarget.digest``
and ``.files`` absent) cannot show which files Apothem wrote. For such a
target, uninstall compares the files on disk with what this release writes
there from its shipped source: a file with the same bytes is Apothem's and
goes; anything else stays (see :func:`install_driver_written.remove_written`).
"""

from __future__ import annotations

import contextlib
import hashlib
import re
from collections.abc import Callable
from pathlib import Path

from apothem.lib.propagation import HarnessRules, InstallEntry

from .install_driver_agent_emitters import AGENT_EMITTERS
from .install_driver_apply import _cohort_members
from .install_driver_converters import (
    _antigravity_rule_text,
    _claude_rule_text,
    _command_skill_files,
    _gemini_command_text,
    _native_markdown_command_text,
)
from .install_driver_hookfile import HOOK_FILE_MODE
from .install_driver_merge import render_content_tokens
from .install_driver_pathsafety import _root_for
from .install_driver_planvalidation import _generated_targets_for_entry, make_ignore
from .install_driver_shared import emission_name
from .install_driver_treeops import _iter_relative_files, _native_skill_dir_files
from .install_driver_types import (
    IgnoreFn,
    _path_text,
    resolve_source,
    skills_sharing_command_target,
)

#: The rendered-cohort modes that write one file per source member: the
#: renderer and the extension the target gets (``None`` keeps the source name).
#: Modes removed surgically rather than as written files.
_SINGLE_FILE_MODES = frozenset({"write_text", "sentinel_merge", HOOK_FILE_MODE})

_RENDERED: dict[str, tuple[Callable[[Path], str], str | None]] = {
    "gemini_commands": (_gemini_command_text, "toml"),
    "markdown_commands": (_native_markdown_command_text, None),
    "claude_rules": (_claude_rule_text, None),
    "antigravity_rules": (_antigravity_rule_text, None),
}


#: An interpreter path as an install writes it: one line, ending in the
#: Python executable's name (``python``, ``python3.12``, ``python.exe``), with
#: none of the characters a shell command or a comment needs (``;&|<>#$``,
#: backquote, double quote). Spaces, ``()``, ``~``, an apostrophe
#: (``O'Brien``) and non-ASCII letters are allowed, as real paths hold them.
_INTERPRETER = rb"[^\r\n;&|<>#$`\"]*?[Pp]ython[0-9.]*(?:\.[Ee][Xx][Ee])?"

#: The install-time tokens an adapter fills in that the shipped source leaves
#: unrendered, each with what it can stand for: an interpreter path on one
#: line ending in the interpreter (``${PYTHON_BIN}``, see :data:`_INTERPRETER`), or the PowerShell call operator
#: (``${CALL_OP}``, ``"& "`` on a Windows host and empty elsewhere). Any other
#: ``${NAME}`` (``${CLAUDE_SKILL_DIR}``, ``${CLAUDE_PLUGIN_ROOT}``) is text the
#: tool reads, so it must match exactly.
_FILLED: dict[bytes, bytes] = {
    b"${PYTHON_BIN}": _INTERPRETER,
    b"${STATUSLINE_PYTHON_BIN}": _INTERPRETER,
    b"${CALL_OP}": rb"(?:& )?",
}

#: Splits text on the filled tokens, keeping each token.
_TOKEN = re.compile(b"(" + b"|".join(re.escape(token) for token in _FILLED) + b")")


def _filled(expected: bytes, actual: Path) -> bool:
    """Return True when *actual* is *expected* with each filled token in place.

    Everything outside the tokens of :data:`_FILLED` must match byte for byte,
    and each token only what it can stand for.
    """
    try:
        data = actual.read_bytes()
    except OSError:
        return False
    pattern = b"".join(
        _FILLED[part] if part in _FILLED else re.escape(part)
        for part in _TOKEN.split(expected)
    )
    return re.fullmatch(pattern, data, flags=re.DOTALL) is not None


def _digests(files: dict[str, bytes], target: Path) -> dict[str, str]:
    """Return *files* (relative path to bytes) mapped to their SHA-256.

    A file whose expected bytes still hold an install-time token gets the
    on-disk file's digest when that file is the expected text with the token
    filled, so it compares as Apothem's.
    """
    digests = {}
    for path, data in files.items():
        on_disk = target / path if path else target
        if _TOKEN.search(data) and _filled(data, on_disk):
            data = on_disk.read_bytes()
        digests[path] = hashlib.sha256(data).hexdigest()
    return digests


def _tree(folder: Path, ignore: IgnoreFn | None) -> dict[str, bytes]:
    """Return the files a copy of *folder* writes, keyed by relative path."""
    return {
        relative.as_posix(): (folder / relative).read_bytes()
        for relative in _iter_relative_files(folder, ignore)
    }


def _copied_file(
    source: Path,
    entry: InstallEntry,
    *,
    harness_root: Path | None,
    project_root: Path | None,
) -> bytes:
    """Return the bytes ``merge_tree_entries`` writes for the file *source*."""
    data = source.read_bytes()
    if b"${" in data and not entry.user_level:
        with contextlib.suppress(UnicodeDecodeError):
            data = render_content_tokens(
                data.decode("utf-8"),
                harness_root=harness_root,
                project_root=project_root,
            ).encode("utf-8")
    return data


def _rendered_member(
    entry: InstallEntry, src: Path, target: Path
) -> dict[str, bytes] | None:
    """Return the file a rendered-cohort mode writes at *target*, if any."""
    emitter = AGENT_EMITTERS.get(entry.mode)
    if emitter is not None:
        renderer, extension, exclude = (
            emitter.renderer,
            emitter.target_extension,
            emitter.exclude,
        )
    elif entry.mode in _RENDERED:
        renderer, extension = _RENDERED[entry.mode]
        exclude = frozenset()
    else:
        return None
    for source in _cohort_members(src, exclude):
        name = source.name if extension is None else f"{source.stem}.{extension}"
        if name == target.name:
            return {"": renderer(source).encode("utf-8")}
    return None


def _expected_bytes(
    entry: InstallEntry,
    target: Path,
    *,
    harness_name: str,
    harness_root: Path | None,
    project_root: Path | None,
    ignore: IgnoreFn | None,
) -> dict[str, bytes] | None:
    """Return what this release writes at *target* for *entry*, or ``None``."""
    src = resolve_source(entry.source)
    if not src.exists():
        return None
    if entry.mode == "replace_tree":
        return _tree(src, ignore)
    source = src / target.name
    if entry.mode == "merge_tree_entries":
        if source.is_dir():
            return _tree(source, ignore)
        if source.is_file():
            data = _copied_file(
                source, entry, harness_root=harness_root, project_root=project_root
            )
            return {"": data}
        return None
    if entry.mode == "native_skills" and source.is_dir():
        return _native_skill_dir_files(
            source, harness_name=emission_name(entry, harness_name), ignore=ignore
        )
    if entry.mode == "command_skills":
        command = src / f"{target.name}.md"
        if not command.is_file():
            return None
        return _command_skill_files(
            command,
            harness_name=emission_name(entry, harness_name),
            install_root=_root_for(harness_root, project_root),
        )
    return _rendered_member(entry, src, target)


def expected_digests(
    entry: InstallEntry,
    target: Path,
    *,
    harness_name: str,
    harness_root: Path | None,
    project_root: Path | None,
    ignore: IgnoreFn | None,
) -> dict[str, str] | None:
    """Return the SHA-256 of each file this release writes at *target*.

    Keyed like a recorded ``files`` map (``""`` for a file target). ``None``
    when *target* is not one *entry* writes, or its source cannot be read.
    """
    try:
        files = _expected_bytes(
            entry,
            target,
            harness_name=harness_name,
            harness_root=harness_root,
            project_root=project_root,
            ignore=ignore,
        )
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return None if files is None else _digests(files, target)


def expected_lookup(
    rules: HarnessRules,
    *,
    harness_name: str,
    harness_root: Path | None,
    project_root: Path | None,
) -> Callable[[Path], dict[str, str] | None]:
    """Return a function giving this release's digests at any target *rules* write.

    The target belongs to the last entry that writes it (the one whose content
    the install left); a command that shares its name with a skill is left
    out, as the install leaves it out. The map is built on the first call.
    """
    ignore = make_ignore(
        list(rules.exclude), dict(getattr(rules, "per_directory_filters", {}))
    )
    owners: dict[str, InstallEntry] = {}

    def lookup(target: Path) -> dict[str, str] | None:
        if not owners:
            for entry in rules.install:
                if entry.mode in _SINGLE_FILE_MODES:
                    continue
                skip = (
                    skills_sharing_command_target(entry, rules)
                    if entry.mode == "command_skills"
                    else frozenset()
                )
                for path in _generated_targets_for_entry(
                    entry,
                    harness_root=harness_root,
                    project_root=project_root,
                    exclude=rules.exclude,
                ):
                    if path.name not in skip:
                        owners[_path_text(path)] = entry
        owner = owners.get(_path_text(target))
        if owner is None:
            return None
        return expected_digests(
            owner,
            target,
            harness_name=harness_name,
            harness_root=harness_root,
            project_root=project_root,
            ignore=ignore,
        )

    return lookup
