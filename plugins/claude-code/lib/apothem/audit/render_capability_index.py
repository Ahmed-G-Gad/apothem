# SPDX-License-Identifier: MIT

"""Render the Markdown capability-index table for the project README's instruction-surface summary.

Why this renderer exists. The canonical project voice carries a top-level
``Capability Index`` section that enumerates every runtime entity the
ecosystem exposes — agents, skills, commands, hook messages, output
styles, MCP servers, and CLI bin helpers. The enumeration is mechanical: walk each
artifact directory, parse the YAML frontmatter, derive a triggers
column from the artifact's class and frontmatter signals, and emit a
Markdown table sorted by kind then by id. Manually-curated capability
inventories rot the moment the next entity lands; this renderer keeps
the table coherent with the on-disk truth.

Output. By default, the renderer writes the table to stdout — the
canonical project voice file pastes the output between two HTML comment markers
(``<!-- capability-index:begin -->`` and ``<!-- capability-index:end -->``)
that delimit the regenerable region. The ``--write CLAUDE.md`` flag
writes the table back into a target file by replacing the content
between those markers in place.

Frontmatter parsing. Every artifact uses YAML frontmatter delimited by
two ``---`` lines. The parser handles the simple ``key: "value"`` and
``key: value`` forms used by every artifact in the ecosystem; nested
mappings and block-style values are not required by any artifact under
inspection and are deliberately not supported.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scan_lib import CONTENT_ROOT

# The repository root — three directories up (``audit/`` → ``apothem/`` →
# ``src/`` → repo root) — anchors relative ``--write`` targets such as the
# README's instruction-surface summary.
REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]

# The seven capability classes the index enumerates. The order in this
# tuple is the order rows appear in the rendered table.
CAPABILITY_CLASSES: Final[tuple[str, ...]] = (
    "agent",
    "skill",
    "command",
    "hook-message",
    "output-style",
    "mcp-server",
    "bin",
)

# Hook-message filename stems that carry no frontmatter. Their
# triggers column derives from the filename pattern alone.
HOOK_EVENT_PATTERNS: Final[dict[str, str]] = {
    "sessionstart": "SessionStart",
    "stop": "Stop",
    "precompact": "PreCompact",
    "postcompact": "PostCompact",
    "pretooluse-bash": "PreToolUse(Bash)",
    "pretooluse-write": "PreToolUse(Write)",
    "pretooluse-edit": "PreToolUse(Edit)",
    "pretooluse-notebookedit": "PreToolUse(NotebookEdit)",
    "pretooluse-conformity": "PreToolUse(*)",
    "pretooluse-write-header-guard": "PreToolUse(Write)",
    "pretooluse-edit-header-guard": "PreToolUse(Edit)",
}

# Region markers the ``--write`` mode replaces in place.
BEGIN_MARKER: Final[str] = "<!-- capability-index:begin -->"
END_MARKER: Final[str] = "<!-- capability-index:end -->"


@dataclass(frozen=True)
class CapabilityRow:
    """One row of the capability-index table."""

    id_: str
    kind: str
    description: str
    triggers: str


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Return the YAML frontmatter as a flat ``key → value`` mapping.

    The parser handles the ``---``-delimited block at the top of the
    file. Quoted and unquoted scalar values are both supported; nested
    mappings, sequences, and block-scalar styles are not. It is deliberately
    minimal rather than a full YAML load: the capability-index frontmatter this
    renderer consumes is flat ``key → scalar``, so a dependency-free line parser
    covers every shape it ever sees.
    """
    lines = text.splitlines()
    # Skip leading HTML-comment banner if present.
    cursor = 0
    while cursor < len(lines) and not lines[cursor].strip().startswith("---"):
        cursor += 1
    if cursor >= len(lines) or lines[cursor].strip() != "---":
        return {}
    cursor += 1
    end = cursor
    while end < len(lines) and lines[end].strip() != "---":
        end += 1
    block = lines[cursor:end]
    out: dict[str, str] = {}
    pattern = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")
    for raw in block:
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        match = pattern.match(raw)
        if match is None:
            continue
        key, value = match.group(1), match.group(2).strip()
        # Strip matched surrounding quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        out[key] = value
    return out


def _truncate(text: str, limit: int = 110) -> str:
    """Trim ``text`` to a single line of at most ``limit`` characters."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def _collect_agents() -> list[CapabilityRow]:
    folder = CONTENT_ROOT / "agents"
    rows: list[CapabilityRow] = []
    if not folder.is_dir():
        return rows
    for path in sorted(folder.glob("*.md")):
        meta = _parse_frontmatter(path.read_text(encoding="utf-8"))
        rows.append(
            CapabilityRow(
                id_=meta.get("name", path.stem),
                kind="agent",
                description=_truncate(meta.get("description", "")),
                triggers="dispatched by orchestrator (Agent tool)",
            )
        )
    return rows


def _collect_skills() -> list[CapabilityRow]:
    folder = CONTENT_ROOT / "skills"
    rows: list[CapabilityRow] = []
    if not folder.is_dir():
        return rows
    for skill_dir in sorted(p for p in folder.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        meta = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        invocable = meta.get("userInvocable", "false").lower() == "true"
        rows.append(
            CapabilityRow(
                id_=meta.get("name", skill_dir.name),
                kind="skill",
                description=_truncate(meta.get("description", "")),
                triggers=f"`/{meta.get('name', skill_dir.name)}`"
                if invocable
                else "auto-detected",
            )
        )
    return rows


def _collect_commands() -> list[CapabilityRow]:
    folder = CONTENT_ROOT / "commands"
    rows: list[CapabilityRow] = []
    if not folder.is_dir():
        return rows
    for path in sorted(folder.glob("*.md")):
        meta = _parse_frontmatter(path.read_text(encoding="utf-8"))
        name = meta.get("name", path.stem)
        rows.append(
            CapabilityRow(
                id_=name,
                kind="command",
                description=_truncate(meta.get("description", "")),
                triggers=f"`/{name}`",
            )
        )
    return rows


def _collect_hook_messages() -> list[CapabilityRow]:
    folder = CONTENT_ROOT / "hooks" / "messages"
    rows: list[CapabilityRow] = []
    if not folder.is_dir():
        return rows
    for path in sorted(folder.glob("*.md")):
        stem = path.stem
        # Hook-message files carry banner + prose, no YAML frontmatter.
        # Description is the first non-empty, non-banner paragraph.
        text = path.read_text(encoding="utf-8")
        description = _first_prose_paragraph(text)
        rows.append(
            CapabilityRow(
                id_=stem,
                kind="hook-message",
                description=_truncate(description),
                triggers=HOOK_EVENT_PATTERNS.get(stem, "hook event"),
            )
        )
    return rows


def _collect_output_styles() -> list[CapabilityRow]:
    folder = CONTENT_ROOT / "output-styles"
    rows: list[CapabilityRow] = []
    if not folder.is_dir():
        return rows
    for path in sorted(folder.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        meta = _parse_frontmatter(path.read_text(encoding="utf-8"))
        rows.append(
            CapabilityRow(
                id_=meta.get("name", path.stem),
                kind="output-style",
                description=_truncate(meta.get("description", "")),
                triggers="operator-selected",
            )
        )
    return rows


def _collect_mcp_servers() -> list[CapabilityRow]:
    """Return MCP server rows from `.mcp.json` if present, else empty."""
    import json

    rows: list[CapabilityRow] = []
    mcp_json = CONTENT_ROOT / ".mcp.json"
    if not mcp_json.is_file():
        return rows
    try:
        data = json.loads(mcp_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return rows
    servers = data.get("mcpServers", {})
    for server_id in sorted(servers):
        config = servers[server_id]
        description = ""
        if isinstance(config, dict):
            description = str(config.get("description", config.get("command", "")))
        rows.append(
            CapabilityRow(
                id_=server_id,
                kind="mcp-server",
                description=_truncate(description),
                triggers="MCP namespace",
            )
        )
    return rows


def _extract_purpose(source_path: Path) -> str:
    """Return the multi-line ``Purpose:`` comment block from a shell-style script.

    Continuation lines are captured until the next labeled section
    (``Contract:``, ``Sibling:``, etc.) or a blank / non-comment line.
    """
    try:
        text = source_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    in_purpose = False
    parts: list[str] = []
    label_pattern = re.compile(r"^[A-Z][A-Za-z]+:")
    for raw in text.splitlines():
        if not raw.lstrip().startswith("#"):
            if in_purpose:
                break
            continue
        stripped = raw.lstrip("# ").rstrip()
        if stripped.startswith("Purpose:"):
            in_purpose = True
            parts.append(stripped[len("Purpose:") :].strip())
            continue
        if not in_purpose:
            continue
        if not stripped or label_pattern.match(stripped):
            break
        parts.append(stripped)
    return " ".join(parts)


def _bin_triggers(
    stem: str, sh_exists: bool, posix_exists: bool, ps_exists: bool
) -> str:
    """Return the triggers cell for a bin/ helper based on which scripts exist."""
    has_posix = sh_exists or posix_exists
    if has_posix and ps_exists:
        return f"`{stem}` (POSIX + PowerShell paired)"
    if posix_exists and not sh_exists:
        return f"`{stem}` (POSIX)"
    if sh_exists:
        return f"`{stem}.sh` (POSIX)"
    return f"`{stem}.ps1` (PowerShell)"


def _collect_bin_helpers() -> list[CapabilityRow]:
    """Return bin/ helper rows. CLI helpers ship as paired POSIX + PowerShell scripts.

    Each pair collapses to a single row whose id is the basename and whose
    description derives from the leading purpose comment of the POSIX
    script. Three POSIX-side filename shapes are recognized: ``<name>.sh``
    (suffixed POSIX wrapper), ``<name>`` (suffix-less executable per
    Filesystem Hierarchy Standard for CLI binaries on PATH), and the
    PowerShell sibling at ``<name>.ps1``.
    """
    folder = CONTENT_ROOT / "bin"
    rows: list[CapabilityRow] = []
    if not folder.is_dir():
        return rows
    seen: set[str] = set()
    candidates: list[Path] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        if path.suffix in {".sh", ".ps1"} or path.suffix == "":
            candidates.append(path)
    for path in candidates:
        stem = path.stem if path.suffix else path.name
        if stem in seen:
            continue
        seen.add(stem)
        sh_path = folder / f"{stem}.sh"
        posix_path = folder / stem
        ps_path = folder / f"{stem}.ps1"
        posix_exists = posix_path.is_file() and posix_path.suffix == ""
        if sh_path.is_file():
            purpose_source = sh_path
        elif posix_exists:
            purpose_source = posix_path
        else:
            purpose_source = path
        description = _extract_purpose(purpose_source)
        triggers = _bin_triggers(
            stem, sh_path.is_file(), posix_exists, ps_path.is_file()
        )
        rows.append(
            CapabilityRow(
                id_=stem,
                kind="bin",
                description=_truncate(description),
                triggers=triggers,
            )
        )
    return rows


def _first_prose_paragraph(text: str) -> str:
    """Return the first prose paragraph after the banner, ignoring blank lines."""
    in_banner = False
    paragraph: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("<!--"):
            in_banner = True
            continue
        if in_banner:
            if "-->" in line:
                in_banner = False
            continue
        if not line.strip():
            if paragraph:
                break
            continue
        paragraph.append(line.strip())
    return " ".join(paragraph)


def _render_markdown_table(rows: list[CapabilityRow]) -> str:
    """Return the Markdown table body for the canonical capability index."""
    lines = [
        "| ID | Kind | Description | Triggers |",
        "|----|------|-------------|----------|",
    ]
    for row in rows:
        # Pipe and backtick are the two characters that need escaping in
        # Markdown table cells.
        cells = (
            row.id_.replace("|", r"\|"),
            row.kind,
            row.description.replace("|", r"\|"),
            row.triggers.replace("|", r"\|"),
        )
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _collect_all() -> list[CapabilityRow]:
    """Return every capability row in canonical sort order."""
    collectors = {
        "agent": _collect_agents,
        "skill": _collect_skills,
        "command": _collect_commands,
        "hook-message": _collect_hook_messages,
        "output-style": _collect_output_styles,
        "mcp-server": _collect_mcp_servers,
        "bin": _collect_bin_helpers,
    }
    rows: list[CapabilityRow] = []
    for kind in CAPABILITY_CLASSES:
        rows.extend(sorted(collectors[kind](), key=lambda r: r.id_))
    return rows


def _replace_marked_region(text: str, payload: str) -> str:
    """Replace the content between BEGIN_MARKER and END_MARKER with ``payload``."""
    if BEGIN_MARKER not in text or END_MARKER not in text:
        raise SystemExit(
            f"target file is missing the capability-index region markers "
            f"({BEGIN_MARKER!r} / {END_MARKER!r}); add an empty marked region "
            "before re-running with --write"
        )
    pattern = re.compile(
        re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER),
        flags=re.DOTALL,
    )
    return pattern.sub(BEGIN_MARKER + "\n\n" + payload + "\n\n" + END_MARKER, text)


def main(argv: list[str] | None = None) -> int:
    """Collect every capability row and render the index table to stdout or into a marked region.

    Walks each capability class into sorted rows and renders the Markdown
    table; with ``--write`` it replaces the marked region in the target file,
    otherwise it prints the table to stdout.
    """
    parser = argparse.ArgumentParser(
        prog="render_capability_index",
        description="Render the Markdown capability-index table.",
    )
    parser.add_argument(
        "--write",
        type=Path,
        default=None,
        help="Write the table back into TARGET, replacing the marked region.",
    )
    args = parser.parse_args(argv)

    rows = _collect_all()
    table = _render_markdown_table(rows)

    if args.write is None:
        # Reconfigure stdout to UTF-8 so em-dashes and other non-ASCII
        # characters in descriptions survive the pipe on hosts whose
        # default code page is not UTF-8 (notably Windows).
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stdout.write(table + "\n")
        return 0

    target: Path = args.write
    if not target.is_absolute():
        target = REPO_ROOT / target
    text = target.read_text(encoding="utf-8")
    target.write_text(_replace_marked_region(text, table), encoding="utf-8")
    sys.stderr.write(f"capability-index region updated in {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
