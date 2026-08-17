# SPDX-License-Identifier: MIT

"""Walk an ecosystem root and produce a machine-readable inventory.

Why this tool exists. Subsequent audit work (drift detection, header
coverage, multi-surface conventions, validator authoring) needs a single
authoritative description of every file in the working tree: its path,
size, content hash, line count, ecosystem-class, and authorship-banner
status. Without that one source of truth, each consumer would re-walk
the tree with subtly different filters and produce drift between scans.
This tool emits ``inventory.json`` once; every downstream pass reads it.

What the inventory captures. Per file: ``path`` (relative to root),
``size`` (bytes), ``mtime`` (ISO 8601 UTC), ``sha256`` (hex digest),
``line-count`` (text files only — None for binaries), ``class`` (one of
the canonical thirteen classes below), ``header-status`` (
``present-canonical`` / ``present-malformed`` / ``absent`` /
``not-applicable``), and ``header-variant`` (the comment-syntax family
the file's authorship banner would use, when applicable).

What the inventory excludes. Version-control internals (``.git``),
Python bytecode caches (``__pycache__``), virtual environments
(``.venv`` / ``venv`` / ``env`` / ``.tox``), node modules, and the
audit-output directory itself (``.audit``). The exclusion list is
deliberate: these are derivative state, not source artifacts, and
including them would inflate aggregate counts without informing any
downstream consumer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

# Thirteen canonical ecosystem classes. The classification matrix at the
# next audit phase refines these verdicts; this pass assigns one class per
# file via path-prefix lookup with extension-based fallbacks.
CLASS_MEMORY: Final[str] = "memory"
CLASS_AGENT: Final[str] = "agent"
CLASS_COMMAND: Final[str] = "command"
CLASS_SKILL: Final[str] = "skill"
CLASS_HOOK: Final[str] = "hook"
CLASS_OUTPUT_STYLE: Final[str] = "output-style"
CLASS_STATUSLINE: Final[str] = "statusline"
CLASS_SETTINGS: Final[str] = "settings"
CLASS_MCP: Final[str] = "mcp"
CLASS_DOCS: Final[str] = "docs"
CLASS_SCAFFOLDING: Final[str] = "scaffolding"
CLASS_PLAN_ARTIFACT: Final[str] = "plan-artifact"
CLASS_UNKNOWN: Final[str] = "unknown"

ALL_CLASSES: Final[tuple[str, ...]] = (
    CLASS_MEMORY,
    CLASS_AGENT,
    CLASS_COMMAND,
    CLASS_SKILL,
    CLASS_HOOK,
    CLASS_OUTPUT_STYLE,
    CLASS_STATUSLINE,
    CLASS_SETTINGS,
    CLASS_MCP,
    CLASS_DOCS,
    CLASS_SCAFFOLDING,
    CLASS_PLAN_ARTIFACT,
    CLASS_UNKNOWN,
)

# Header-status taxonomy. The four values are mutually exclusive per file.
HEADER_PRESENT_CANONICAL: Final[str] = "present-canonical"
HEADER_PRESENT_MALFORMED: Final[str] = "present-malformed"
HEADER_ABSENT: Final[str] = "absent"
HEADER_NOT_APPLICABLE: Final[str] = "not-applicable"

ALL_HEADER_STATUSES: Final[tuple[str, ...]] = (
    HEADER_PRESENT_CANONICAL,
    HEADER_PRESENT_MALFORMED,
    HEADER_ABSENT,
    HEADER_NOT_APPLICABLE,
)

# Path-prefix to class mapping. The ordering is irrelevant — every key is
# matched against the file's relative-path top-level segment. Files outside
# any registered prefix fall through to extension-based classification.
PATH_PREFIX_CLASSES: Final[dict[str, str]] = {
    "memory": CLASS_MEMORY,
    "projects": CLASS_MEMORY,
    "agents": CLASS_AGENT,
    "commands": CLASS_COMMAND,
    "skills": CLASS_SKILL,
    "hooks": CLASS_HOOK,
    "output-styles": CLASS_OUTPUT_STYLE,
    "statusline": CLASS_STATUSLINE,
    "statuslines": CLASS_STATUSLINE,
    "settings": CLASS_SETTINGS,
    "mcp": CLASS_MCP,
    "docs": CLASS_DOCS,
    "rules": CLASS_DOCS,
    "examples": CLASS_DOCS,
    "schemas": CLASS_SCAFFOLDING,
    "scripts": CLASS_SCAFFOLDING,
    "tests": CLASS_SCAFFOLDING,
    "templates": CLASS_SCAFFOLDING,
    "assets": CLASS_SCAFFOLDING,
    ".github": CLASS_SCAFFOLDING,
    "packaging": CLASS_SCAFFOLDING,
    ".plans": CLASS_PLAN_ARTIFACT,
}

# Settings files at the working-tree root carry the settings class regardless
# of the absent ``settings/`` directory. The Claude-Code installable example
# (``settings.json``) lives under
# ``examples/harnesses/claude-code/native-install/`` and is classified via the
# ``examples`` path-prefix entry, not by root-filename.
ROOT_SETTINGS_FILES: Final[frozenset[str]] = frozenset(
    {
        ".mcp.json",
        ".credentials.json",
    }
)

# Files at the working-tree root that contribute to the scaffolding class.
# Covers the build-runner, lint configs, line-ending policy, install/update/
# uninstall scripts, version pin, secret-scan config, license header policy,
# and contributor mapping that any modern dotfiles repository carries at root.
ROOT_SCAFFOLDING_FILES: Final[frozenset[str]] = frozenset(
    {
        "Makefile",
        "VERSION",
        "pyproject.toml",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        ".gitleaks.toml",
        ".gitmessage",
        ".licenserc.yaml",
        ".mailmap",
        ".markdownlint.json",
        ".markdownlint.jsonc",
        ".markdownlint-cli2.jsonc",
        ".prettierrc",
        ".prettierignore",
        ".shellcheckrc",
        ".pre-commit-config.yaml",
        "scripts/installer/install.sh",
        "scripts/installer/install.ps1",
        "scripts/installer/update.sh",
        "scripts/installer/update.ps1",
        "scripts/installer/uninstall.sh",
        "scripts/installer/uninstall.ps1",
    }
)

# Documentation files at the working-tree root.
ROOT_DOCS_FILES: Final[frozenset[str]] = frozenset(
    {
        "CLAUDE.md",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "AUTHORS",
        ".mcp.json.notes.md",
    }
)

# Directory names skipped during the walk. These are derivative state, not
# source artifacts. The set covers four distinct origins: version-control
# internals (``.git``), language-tooling caches (``__pycache__``,
# ``.pytest_cache``, ``.mypy_cache``, ``.ruff_cache``, ``node_modules``,
# ``.tox``), virtual environments (``.venv``, ``venv``, ``env``,
# ``apothem.egg-info``), and Claude Code harness-managed state
# (``file-history``, ``debug``, ``todos``, ``shell-snapshots``, ``ide``,
# ``sessions``, ``session-env``, ``runtime-data``, ``cache``, ``downloads``,
# ``backups``, ``statsig``, ``telemetry``, ``plugins``). The audit-output
# directory itself (``.audit``) is also skipped to keep self-reference out
# of the inventory.
SKIPPED_DIRS: Final[frozenset[str]] = frozenset(
    {
        # Version-control internals.
        ".git",
        # Language-tooling caches.
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "node_modules",
        # Virtual environments and Python build artifacts.
        ".venv",
        "venv",
        "env",
        "apothem.egg-info",
        # Audit output (self-reference).
        ".audit",
        # IDE workspace state.
        ".vscode",
        ".idea",
        # Claude Code harness-managed state.
        "file-history",
        "debug",
        "todos",
        "shell-snapshots",
        "ide",
        "sessions",
        "session-env",
        "runtime-data",
        "cache",
        "downloads",
        "backups",
        "statsig",
        "telemetry",
        "plugins",
    }
)

# File extensions treated as binary. The header-status check skips these and
# the line-count returns None.
BINARY_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".webp",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".7z",
        ".rar",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".pyc",
        ".pyo",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".mp3",
        ".mp4",
        ".webm",
        ".mov",
        ".avi",
    }
)

# Lockfiles, generated assets, and vendored data are all not-applicable for
# the authorship banner. Adding a banner to JSON / lockfiles would break
# parsing; vendored content carries upstream attribution and must not be
# overwritten.
NOT_APPLICABLE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".json",
        ".lock",
        ".min.js",
        ".min.css",
    }
)

# Filename patterns that mark a file as not-applicable for banner injection.
NOT_APPLICABLE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "LICENSE",
        "VERSION",
        "go.sum",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Pipfile.lock",
        "poetry.lock",
        "uv.lock",
    }
)

# Header-variant family per filetype. The variants enumerate which comment
# syntax the canonical single-line ``SPDX-License-Identifier: MIT`` header uses
# on this filetype. The values are intent labels; the byte-exact header line
# lives in the ``src/apothem/schemas/authorship-header.txt`` fixture.
HEADER_VARIANT_HASH: Final[str] = "hash"  # `# ...` line-comments
HEADER_VARIANT_DOUBLE_SLASH: Final[str] = "double-slash"  # `// ...`
HEADER_VARIANT_HTML: Final[str] = "html"  # `<!-- ... -->`
HEADER_VARIANT_C_BLOCK: Final[str] = "c-block"  # `/* ... */`
HEADER_VARIANT_SEMICOLON: Final[str] = "semicolon"  # `; ...`
HEADER_VARIANT_DOUBLE_DASH: Final[str] = "double-dash"  # `-- ...`
HEADER_VARIANT_NONE: Final[str] = "none"  # not-applicable

EXTENSION_VARIANT: Final[dict[str, str]] = {
    ".py": HEADER_VARIANT_HASH,
    ".sh": HEADER_VARIANT_HASH,
    ".bash": HEADER_VARIANT_HASH,
    ".zsh": HEADER_VARIANT_HASH,
    ".ps1": HEADER_VARIANT_HASH,
    ".psm1": HEADER_VARIANT_HASH,
    ".psd1": HEADER_VARIANT_HASH,
    ".yaml": HEADER_VARIANT_HASH,
    ".yml": HEADER_VARIANT_HASH,
    ".toml": HEADER_VARIANT_HASH,
    ".ini": HEADER_VARIANT_SEMICOLON,
    ".cfg": HEADER_VARIANT_HASH,
    ".conf": HEADER_VARIANT_HASH,
    ".md": HEADER_VARIANT_HTML,
    ".markdown": HEADER_VARIANT_HTML,
    ".html": HEADER_VARIANT_HTML,
    ".htm": HEADER_VARIANT_HTML,
    ".xml": HEADER_VARIANT_HTML,
    ".svg": HEADER_VARIANT_HTML,
    ".js": HEADER_VARIANT_DOUBLE_SLASH,
    ".ts": HEADER_VARIANT_DOUBLE_SLASH,
    ".jsx": HEADER_VARIANT_DOUBLE_SLASH,
    ".tsx": HEADER_VARIANT_DOUBLE_SLASH,
    ".java": HEADER_VARIANT_DOUBLE_SLASH,
    ".go": HEADER_VARIANT_DOUBLE_SLASH,
    ".rs": HEADER_VARIANT_DOUBLE_SLASH,
    ".swift": HEADER_VARIANT_DOUBLE_SLASH,
    ".kt": HEADER_VARIANT_DOUBLE_SLASH,
    ".c": HEADER_VARIANT_C_BLOCK,
    ".cpp": HEADER_VARIANT_C_BLOCK,
    ".h": HEADER_VARIANT_C_BLOCK,
    ".hpp": HEADER_VARIANT_C_BLOCK,
    ".css": HEADER_VARIANT_C_BLOCK,
    ".scss": HEADER_VARIANT_C_BLOCK,
    ".sql": HEADER_VARIANT_DOUBLE_DASH,
    ".lua": HEADER_VARIANT_DOUBLE_DASH,
    ".hs": HEADER_VARIANT_DOUBLE_DASH,
}

# Banner heuristic markers. The narrowed canonical header is the single
# ``SPDX-License-Identifier:`` line; its presence near the file head marks
# ``present-canonical``. The retired branded-banner author mark is retained
# as a legacy signal: a file still carrying it (but not the SPDX line) is a
# not-yet-narrowed header and counts ``present-malformed``. This stays a
# coarse sizing heuristic; the per-file authoritative verdict is recomputed
# downstream by the header-coverage scanner.
SPDX_PREFIX_TEXT: Final[str] = "SPDX-License-Identifier:"
LEGACY_AUTHOR_MARK: Final[str] = "Copyright (c) Ahmed G. Gad"

# Number of leading lines scanned for banner presence. Forty lines covers
# every shebang + interpreter-pragma + copyright-block prelude shape the
# canonical filetype variants emit.
BANNER_SCAN_LINE_BUDGET: Final[int] = 40

# Buffer size for SHA-256 streaming digest. Sized to balance syscall count
# against memory residency for the small-to-medium file sizes typical in
# this ecosystem.
SHA256_BUFFER_BYTES: Final[int] = 65_536

EXIT_OK: Final[int] = 0
EXIT_ERROR: Final[int] = 1


@dataclass(slots=True)
class FileRecord:
    """Per-file inventory row written to ``inventory.json``."""

    path: str
    size: int
    mtime: str
    sha256: str
    line_count: int | None
    file_class: str
    header_status: str
    header_variant: str

    def to_json(self) -> dict[str, object]:
        """Render the record as the JSON-friendly dict the inventory emits."""
        return {
            "path": self.path,
            "size": self.size,
            "mtime": self.mtime,
            "sha256": self.sha256,
            "line-count": self.line_count,
            "class": self.file_class,
            "header-status": self.header_status,
            "header-variant": self.header_variant,
        }


@dataclass(slots=True)
class InventoryStats:
    """Aggregate counts emitted alongside the per-file array."""

    total_files: int = 0
    by_class: dict[str, int] = field(default_factory=dict)
    by_header_status: dict[str, int] = field(default_factory=dict)
    by_header_variant: dict[str, int] = field(default_factory=dict)
    skipped_directories: list[str] = field(default_factory=list)


def classify_file(relative_path: Path) -> str:
    """Resolve the ecosystem-class for a file given its path relative to root.

    Path-prefix lookup is the primary signal; root-level filename matches
    cover the scaffolding / docs / settings cases at the working-tree root
    where no enclosing directory carries a registered prefix.
    """
    parts = relative_path.parts
    if not parts:
        return CLASS_UNKNOWN

    if len(parts) == 1:
        name = parts[0]
        if name in ROOT_SETTINGS_FILES:
            return CLASS_SETTINGS
        if name in ROOT_SCAFFOLDING_FILES:
            return CLASS_SCAFFOLDING
        if name in ROOT_DOCS_FILES:
            return CLASS_DOCS
        return CLASS_UNKNOWN

    top = parts[0]
    if top in PATH_PREFIX_CLASSES:
        return PATH_PREFIX_CLASSES[top]

    return CLASS_UNKNOWN


def header_variant_for(relative_path: Path) -> str:
    """Resolve the comment-syntax variant the canonical banner would use."""
    name = relative_path.name
    if name in NOT_APPLICABLE_NAMES:
        return HEADER_VARIANT_NONE

    suffix = relative_path.suffix.lower()
    if suffix in NOT_APPLICABLE_EXTENSIONS:
        return HEADER_VARIANT_NONE
    if suffix in BINARY_EXTENSIONS:
        return HEADER_VARIANT_NONE

    return EXTENSION_VARIANT.get(suffix, HEADER_VARIANT_NONE)


def is_binary_file(relative_path: Path) -> bool:
    """Treat the file as binary based on its extension.

    Conservative — when the suffix is not a known binary extension and the
    file is otherwise text-shaped (carries a banner-eligible variant or
    falls outside the binary set entirely), the file is read as text.
    """
    return relative_path.suffix.lower() in BINARY_EXTENSIONS


def compute_sha256(absolute_path: Path) -> str:
    """Stream the file through SHA-256 and return the lowercase hex digest."""
    digest = hashlib.sha256()
    with absolute_path.open("rb") as handle:
        while chunk := handle.read(SHA256_BUFFER_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def count_lines(absolute_path: Path) -> int | None:
    """Count newline-terminated lines; return None when the file is binary."""
    try:
        with absolute_path.open("rb") as handle:
            count = 0
            for _ in handle:
                count += 1
            return count
    except OSError:
        return None


def scan_banner(absolute_path: Path, variant: str) -> str:
    """Inspect the file's leading lines for the canonical banner pattern.

    The scan returns one of the four header-status values. Files whose
    variant resolves to ``none`` (binary, lockfile, vendored, generated)
    short-circuit to ``not-applicable``. Otherwise the leading scan-line
    budget is read as text; the count of distinct banner marks observed
    determines the verdict.
    """
    if variant == HEADER_VARIANT_NONE:
        return HEADER_NOT_APPLICABLE

    try:
        with absolute_path.open("r", encoding="utf-8", errors="replace") as handle:
            head_lines: list[str] = []
            for _, line in zip(range(BANNER_SCAN_LINE_BUDGET), handle, strict=False):
                head_lines.append(line)
    except OSError:
        return HEADER_ABSENT

    head_text = "".join(head_lines)

    if SPDX_PREFIX_TEXT in head_text:
        return HEADER_PRESENT_CANONICAL
    if LEGACY_AUTHOR_MARK in head_text:
        return HEADER_PRESENT_MALFORMED
    return HEADER_ABSENT


def walk_root(root: Path) -> tuple[list[FileRecord], list[str]]:
    """Walk the working tree and emit a record per file plus the skipped dirs."""
    records: list[FileRecord] = []
    skipped: list[str] = []

    for current, dirnames, filenames in _ordered_walk(root):
        original = list(dirnames)
        dirnames[:] = [name for name in dirnames if name not in SKIPPED_DIRS]
        for removed in original:
            if removed in SKIPPED_DIRS:
                rel = (current / removed).relative_to(root).as_posix()
                skipped.append(rel)

        for name in sorted(filenames):
            absolute = current / name
            if not absolute.is_file():
                continue
            try:
                relative = absolute.relative_to(root)
            except ValueError:
                continue

            try:
                stat = absolute.stat()
            except OSError:
                continue

            file_class = classify_file(relative)
            variant = header_variant_for(relative)
            try:
                sha256 = compute_sha256(absolute)
            except OSError:
                continue

            line_count = None if is_binary_file(relative) else count_lines(absolute)
            header_status = scan_banner(absolute, variant)
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

            records.append(
                FileRecord(
                    path=relative.as_posix(),
                    size=stat.st_size,
                    mtime=mtime,
                    sha256=sha256,
                    line_count=line_count,
                    file_class=file_class,
                    header_status=header_status,
                    header_variant=variant,
                )
            )

    return records, skipped


def _ordered_walk(
    root: Path,
) -> Iterator[tuple[Path, list[str], list[str]]]:
    """Deterministic os.walk-equivalent — sorts directory names in place."""
    import os

    for current, dirnames, filenames in os.walk(root):
        dirnames.sort()
        yield Path(current), dirnames, filenames


def aggregate_stats(records: list[FileRecord], skipped: list[str]) -> InventoryStats:
    """Build the stats block emitted alongside the per-file array."""
    stats = InventoryStats(skipped_directories=sorted(set(skipped)))
    stats.total_files = len(records)
    for cls in ALL_CLASSES:
        stats.by_class[cls] = 0
    for status in ALL_HEADER_STATUSES:
        stats.by_header_status[status] = 0
    for record in records:
        stats.by_class[record.file_class] = stats.by_class.get(record.file_class, 0) + 1
        stats.by_header_status[record.header_status] = (
            stats.by_header_status.get(record.header_status, 0) + 1
        )
        stats.by_header_variant[record.header_variant] = (
            stats.by_header_variant.get(record.header_variant, 0) + 1
        )
    return stats


def emit_inventory(
    root: Path, records: list[FileRecord], stats: InventoryStats, output: Path
) -> None:
    """Serialise the inventory to ``output`` as pretty-printed JSON."""
    payload = {
        "root": str(root),
        "generated-at": datetime.now(tz=timezone.utc).isoformat(),
        "total-files": stats.total_files,
        "by-class": stats.by_class,
        "by-header-status": stats.by_header_status,
        "by-header-variant": stats.by_header_variant,
        "skipped-directories": stats.skipped_directories,
        "files": [record.to_json() for record in records],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False, ensure_ascii=False)
        handle.write("\n")


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """CLI surface — root and output are required."""
    parser = argparse.ArgumentParser(
        prog="build_inventory",
        description="Walk an ecosystem root and emit inventory.json.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Root directory to inventory (e.g., the working tree).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSON path (e.g., .audit/inventory.json).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Entry point — returns the exit code."""
    args = parse_arguments(argv)
    root = args.root.resolve()
    output = args.output.resolve()

    if not root.is_dir():
        print(f"error: root is not a directory: {root}", file=sys.stderr)
        return EXIT_ERROR

    records, skipped = walk_root(root)
    stats = aggregate_stats(records, skipped)
    emit_inventory(root, records, stats, output)

    unknown_count = stats.by_class.get(CLASS_UNKNOWN, 0)
    unknown_pct = (unknown_count / stats.total_files * 100) if stats.total_files else 0
    print(
        f"inventory: {stats.total_files} files; "
        f"unknown={unknown_count} ({unknown_pct:.1f}%); "
        f"output={output}"
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
