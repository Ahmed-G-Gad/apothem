# SPDX-License-Identifier: MIT

"""Authorship-header check for the Write and Edit header guards, standard library only.

Why this module exists. ``apothem.conformity.file_header_grep`` is the repository's
validator for the header, but the guards cannot call it. A plugin install ships the
hooks and the ``apothem`` package in separate directories and puts only the hooks on
``sys.path``, so the import fails and the guard went silent on every write; where the
package is importable, loading it costs several hundred milliseconds, too much for a
hook that runs before every Write and Edit. This module decides the same question with
the standard library and reads the two fixtures it needs from the ``schemas/``
directory beside ``hooks/`` in the tree the hook runs from: the plugin tree, the
engine's support tree, and a source checkout all ship them there.

The rules are those of ``scripts/inject-header.py``. A path is checked when it matches
no glob in ``header-exceptions.txt`` and its suffix or basename names a comment family;
the canonical block, the SPDX line in that family's syntax plus one blank line, must
then sit at the insertion site (after a shebang and, for Markdown and MDX, after YAML
frontmatter). The variant tables below are a third copy of that script's tables, held
equal by ``tests/hooks/test_header_check.py``.

Scope. The SPDX line is Apothem's own convention, so the guard has no business in a
project that has not adopted it. ``project_adopts_header`` is the gate: a git project
that carries its own copy of the header fixture. A directory with no ``.git``, or a
project without the fixture, is never judged, whatever the file.

Fail-disposition. A fixture that is missing or unreadable means there is nothing to
check against, so the file is reported as fine: the header invariant is enforced
mechanically in CI and pre-commit, and a guard that cannot check must not nag on every
write.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Final, NamedTuple

__all__ = [
    "SCHEMAS_DIR",
    "edit_lacks_header",
    "project_adopts_header",
    "write_lacks_header",
]

#: ``schemas/`` beside ``hooks/`` in every tree that ships this module.
SCHEMAS_DIR: Final[Path] = Path(__file__).resolve().parents[2] / "schemas"

_BANNER_FIXTURE: Final[str] = "authorship-header.txt"
_EXCEPTIONS_FIXTURE: Final[str] = "header-exceptions.txt"
#: Where a project that follows the convention keeps its own copy of the header fixture.
_PROJECT_BANNER: Final[Path] = Path("src", "apothem", "schemas", _BANNER_FIXTURE)
# Split so REUSE does not parse this literal as a license expression.
_SPDX_PREFIX_TEXT: Final[str] = "SPDX" + "-License-Identifier:"

#: An existing file larger than this is not read to judge an Edit; the guard stays
#: quiet rather than parse a file this size on the tool-call path.
_MAX_EDIT_BYTES: Final[int] = 1_048_576

VARIANT_HASH: Final[str] = "hash"
VARIANT_DOUBLE_SLASH: Final[str] = "double-slash"
VARIANT_HTML: Final[str] = "html"
VARIANT_MDX: Final[str] = "mdx"
VARIANT_C_BLOCK: Final[str] = "c-block"
VARIANT_SEMICOLON: Final[str] = "semicolon"
VARIANT_DOUBLE_DASH: Final[str] = "double-dash"

# Suffix -> comment family. Equal to SUFFIX_VARIANT in scripts/inject-header.py.
SUFFIX_VARIANT: Final[dict[str, str]] = {
    ".sh": VARIANT_HASH,
    ".bash": VARIANT_HASH,
    ".zsh": VARIANT_HASH,
    ".py": VARIANT_HASH,
    ".rb": VARIANT_HASH,
    ".pl": VARIANT_HASH,
    ".ps1": VARIANT_HASH,
    ".psm1": VARIANT_HASH,
    ".psd1": VARIANT_HASH,
    ".yml": VARIANT_HASH,
    ".yaml": VARIANT_HASH,
    ".toml": VARIANT_HASH,
    ".cff": VARIANT_HASH,
    ".cfg": VARIANT_HASH,
    ".conf": VARIANT_HASH,
    ".js": VARIANT_DOUBLE_SLASH,
    ".jsx": VARIANT_DOUBLE_SLASH,
    ".mjs": VARIANT_DOUBLE_SLASH,
    ".cjs": VARIANT_DOUBLE_SLASH,
    ".ts": VARIANT_DOUBLE_SLASH,
    ".tsx": VARIANT_DOUBLE_SLASH,
    ".go": VARIANT_DOUBLE_SLASH,
    ".rs": VARIANT_DOUBLE_SLASH,
    ".java": VARIANT_DOUBLE_SLASH,
    ".kt": VARIANT_DOUBLE_SLASH,
    ".swift": VARIANT_DOUBLE_SLASH,
    ".scala": VARIANT_DOUBLE_SLASH,
    ".dart": VARIANT_DOUBLE_SLASH,
    ".cs": VARIANT_DOUBLE_SLASH,
    ".jsonc": VARIANT_DOUBLE_SLASH,
    ".html": VARIANT_HTML,
    ".htm": VARIANT_HTML,
    ".md": VARIANT_HTML,
    ".markdown": VARIANT_HTML,
    ".mdc": VARIANT_HTML,
    ".mdx": VARIANT_MDX,
    ".xml": VARIANT_HTML,
    ".vue": VARIANT_HTML,
    ".php": VARIANT_HTML,
    ".c": VARIANT_C_BLOCK,
    ".cc": VARIANT_C_BLOCK,
    ".cpp": VARIANT_C_BLOCK,
    ".h": VARIANT_C_BLOCK,
    ".hpp": VARIANT_C_BLOCK,
    ".css": VARIANT_C_BLOCK,
    ".scss": VARIANT_C_BLOCK,
    ".less": VARIANT_C_BLOCK,
    ".sql": VARIANT_DOUBLE_DASH,
    ".ini": VARIANT_SEMICOLON,
    ".lisp": VARIANT_SEMICOLON,
    ".scm": VARIANT_SEMICOLON,
    ".lua": VARIANT_DOUBLE_DASH,
    ".hs": VARIANT_DOUBLE_DASH,
    ".elm": VARIANT_DOUBLE_DASH,
    ".ada": VARIANT_DOUBLE_DASH,
}

# Basename -> comment family for files without a suffix. Equal to BASENAME_VARIANT in
# scripts/inject-header.py; a basename wins over the suffix.
BASENAME_VARIANT: Final[dict[str, str]] = {
    "Makefile": VARIANT_HASH,
    "Dockerfile": VARIANT_HASH,
    "Procfile": VARIANT_HASH,
    "CODEOWNERS": VARIANT_HASH,
    "apothem": VARIANT_HASH,
    "PKGBUILD": VARIANT_HASH,
    ".gitignore": VARIANT_HASH,
    ".gitattributes": VARIANT_HASH,
    ".editorconfig": VARIANT_HASH,
    ".shellcheckrc": VARIANT_HASH,
    ".env.example": VARIANT_HASH,
    ".cursorrules": VARIANT_HASH,
    ".windsurfrules": VARIANT_HASH,
}

#: Comment marker that replaces the fixture's ``#`` in the line-comment families.
_LINE_MARKER: Final[dict[str, str]] = {
    VARIANT_DOUBLE_SLASH: "//",
    VARIANT_SEMICOLON: ";",
    VARIANT_DOUBLE_DASH: "--",
}
#: Opening and closing wrapper around the SPDX text in the wrapper families.
_WRAPPER: Final[dict[str, tuple[str, str]]] = {
    VARIANT_HTML: ("<!-- ", " -->"),
    VARIANT_MDX: ("{/* ", " */}"),
    VARIANT_C_BLOCK: ("/* ", " */"),
}


class _Requirement(NamedTuple):
    """The block one path must carry, and the family that fixes where it sits.

    A named tuple, not a dataclass: importing ``dataclasses`` costs more than the
    rest of this module on the tool-call path.
    """

    variant: str
    block: tuple[str, ...]

    def satisfied_by(self, text: str) -> bool:
        """Whether *text* carries the canonical block at its insertion site."""
        lines = text.replace("\r\n", "\n").split("\n")
        start = _insertion_index(lines, self.variant)
        return tuple(lines[start : start + len(self.block)]) == self.block


def project_adopts_header(root: Path) -> bool:
    """Whether the project at *root* follows the Apothem header convention.

    True for a git project whose tree carries the header fixture. ``.git`` may be a
    directory or the file a worktree leaves. A path that cannot be examined reports
    ``False``, so the guard stays quiet where it cannot tell.
    """
    try:
        return (root / ".git").exists() and (root / _PROJECT_BANNER).is_file()
    except OSError:
        return False


def write_lacks_header(
    rel_path: str, content: str, schemas_dir: Path = SCHEMAS_DIR
) -> bool:
    """Whether a Write of *content* to *rel_path* leaves it without the header.

    *rel_path* is the posix path relative to the project root, the base the
    exemption globs are written against. A path that needs no header, an empty
    *content* and an unusable fixture all report ``False``.
    """
    requirement = _requirement(rel_path, schemas_dir)
    if requirement is None or not content:
        return False
    return not requirement.satisfied_by(content)


def edit_lacks_header(
    rel_path: str,
    target: Path,
    old_string: str,
    new_string: str,
    replace_all: bool,
    schemas_dir: Path = SCHEMAS_DIR,
) -> bool:
    """Whether an Edit of *target* creates it without the header or strips it.

    Two cases fire, the two the Edit guard message names. When *target* does not
    exist and *old_string* is empty the edit creates it and *new_string* is the whole
    file; with an *old_string* to find, the Edit tool rejects the call and creates
    nothing, so the guard stays quiet. When *target* exists and carries the header,
    the edit is applied to the file's text and fires only if the result no longer
    does. An edit that leaves the header alone, and an edit to a file that never had
    one, stay quiet, as does a *target* that cannot be examined.
    """
    requirement = _requirement(rel_path, schemas_dir)
    if requirement is None:
        return False
    try:
        exists = target.exists()
    except OSError:
        return False
    if not exists:
        return (
            not old_string
            and bool(new_string)
            and not requirement.satisfied_by(new_string)
        )
    current = _read_text(target)
    if current is None or not old_string or not requirement.satisfied_by(current):
        return False
    edited = current.replace(
        old_string.replace("\r\n", "\n"),
        new_string.replace("\r\n", "\n"),
        -1 if replace_all else 1,
    )
    return not requirement.satisfied_by(edited)


def _read_text(target: Path) -> str | None:
    """The text of *target* as LF lines, or ``None`` when it cannot be judged."""
    try:
        if not target.is_file() or target.stat().st_size > _MAX_EDIT_BYTES:
            return None
        return target.read_bytes().decode("utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError):
        return None


def _requirement(rel_path: str, schemas_dir: Path) -> _Requirement | None:
    """The block *rel_path* must carry, or ``None`` when no check applies to it."""
    variant = _variant_family(PurePosixPath(rel_path))
    if variant is None:
        return None
    spdx_line = _read_banner(schemas_dir / _BANNER_FIXTURE)
    exceptions = _read_exception_globs(schemas_dir / _EXCEPTIONS_FIXTURE)
    if spdx_line is None or exceptions is None:
        return None
    if any(_glob_matches(rel_path, pattern) for pattern in exceptions):
        return None
    return _Requirement(variant, (*_render_variant(spdx_line, variant), ""))


def _variant_family(path: PurePosixPath) -> str | None:
    """The comment family for *path*, or ``None`` when it names none."""
    if path.name in BASENAME_VARIANT:
        return BASENAME_VARIANT[path.name]
    return SUFFIX_VARIANT.get(path.suffix.lower())


def _read_banner(fixture: Path) -> str | None:
    """The hash-form SPDX line from the fixture, or ``None`` when it is unusable."""
    try:
        raw = fixture.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) != 1:
        return None
    line = lines[0]
    if _SPDX_PREFIX_TEXT not in line or not line.startswith("#"):
        return None
    return line


def _read_exception_globs(fixture: Path) -> tuple[str, ...] | None:
    """The exemption globs in declaration order, or ``None`` when unreadable."""
    try:
        raw = fixture.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    stripped = (line.strip() for line in raw.splitlines())
    return tuple(line for line in stripped if line and not line.startswith("#"))


def _render_variant(hash_form_line: str, variant: str) -> tuple[str, ...]:
    """The SPDX line in *variant*'s comment syntax (no trailing blank line)."""
    if variant == VARIANT_HASH:
        return (hash_form_line,)
    if variant in _LINE_MARKER:
        return (_LINE_MARKER[variant] + hash_form_line[1:],)
    opener, closer = _WRAPPER[variant]
    return (f"{opener}{hash_form_line[1:].strip()}{closer}",)


def _frontmatter_close_index(lines: list[str], start: int) -> int | None:
    """The index of the YAML fence closing a block that opens at *start*, if any."""
    if start >= len(lines) or lines[start] != "---":
        return None
    for index in range(start + 1, len(lines)):
        if lines[index] == "---":
            return index
    return None


def _insertion_index(lines: list[str], variant: str) -> int:
    """The line index where the canonical block belongs.

    A shebang stays first. For Markdown and MDX a YAML frontmatter block stays
    ahead of the block too, and one blank line directly after its closing fence is
    skipped, as ``determine_insertion_index`` in scripts/inject-header.py does.
    """
    index = 1 if lines and lines[0].startswith("#!") else 0
    if variant in (VARIANT_HTML, VARIANT_MDX):
        close = _frontmatter_close_index(lines, index)
        if close is not None:
            index = close + 1
            if index < len(lines) and lines[index].strip() == "":
                index += 1
    return index


def _glob_matches(path: str, pattern: str) -> bool:
    """Whether *path* matches *pattern*, with ``**`` crossing path segments.

    ``*`` and ``?`` stay inside one segment; ``**/`` matches zero or more whole
    segments and a bare ``**`` matches anything. Same semantics as the matcher in
    scripts/inject-header.py (gitignore-style).
    """
    posix = path.replace("\\", "/")
    if not any(char in pattern for char in "*?["):
        return posix == pattern
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*":
            if pattern.startswith("**", i):
                if pattern.startswith("/", i + 2):
                    parts.append("(?:.*/)?")
                    i += 3
                else:
                    parts.append(".*")
                    i += 2
                continue
            parts.append("[^/]*")
        elif char == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(char))
        i += 1
    return re.match("^" + "".join(parts) + "$", posix) is not None
