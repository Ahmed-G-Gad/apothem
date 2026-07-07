# SPDX-License-Identifier: MIT

"""Session-start bootstrap hook for the apothem ecosystem.

Gathers ecosystem context at SessionStart and emits a single-line JSON
envelope: ``{"hookSpecificOutput":{"hookEventName":"SessionStart",...}}``.

The bootstrap produces a plaintext `additionalContext` payload composed
of up to three sections:

* **Session bootstrap** — source, model, and agent-type echoed back from
  the hook's stdin JSON (optional).
* **Memory summary** — first lines of ``## Project Overview``,
  ``**Latest:**`` value, topic file names, and top bullets from
  ``## Key Conventions`` in the project's ``MEMORY.md`` index.
* **Plan summary** — the most recently modified plan suite (if any) and
  key fields pulled from its ``PROGRESS.md``.

Any unexpected exception is caught at the outermost boundary; a valid
failure envelope is emitted and the process exits 0.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

_HOOKS_DIR: Final[Path] = Path(__file__).resolve().parent
_LIB_DIR: Final[Path] = _HOOKS_DIR / "lib"

# Cap on how many bulleted items (topic files, key conventions) the
# bootstrap surfaces. Both the display slices in the summary
# dataclasses and the parser-function defaults below pull from this
# constant, so the slice acts as a safety belt: if a parser is later
# called with a wider limit elsewhere, the bootstrap output still
# stays bounded at this width.
_BULLET_PREVIEW_LIMIT: Final[int] = 3

# Cap on how many numbered items (critical files for the next phase)
# the bootstrap surfaces. Larger than the bullet cap because the
# critical-files list is the manifest a fresh session reads first to
# pick up where the prior session left off; five items keeps that
# surface useful without bloating the SessionStart envelope.
_NUMBERED_PREVIEW_LIMIT: Final[int] = 5
# Insert both paths so ``from emit_hook_context import …`` works whether
# this script is invoked directly or via ``dispatch.py`` (which adds
# ``_HOOKS_DIR`` itself). Without the hooks-dir entry, direct invocation
# raises ``ModuleNotFoundError`` because ``emit_hook_context`` lives in
# ``hooks/``, not ``hooks/lib/``.
for _path in (_HOOKS_DIR, _LIB_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from emit_hook_context import (
    emit_failure_envelope,
    emit_hook_envelope,
    normalize_ascii,
    read_hook_stdin,
)
from log import get_logger
from resolve_root import Mode, resolve_project_root

_logger = get_logger(__name__)

_H2 = re.compile(r"^##\s+(.+?)\s*$")
_BOLD_FIELD = re.compile(r"^\*\*([^:*]+):\*\*\s*(.*?)\s*$")
_BULLET = re.compile(r"^\s*-\s+(.+?)\s*$")
_NUMBERED = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")
_MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+\.md)\)")


@dataclass(frozen=True)
class SessionMeta:
    """Metadata echoed from the hook's stdin payload."""

    source: str = ""
    model: str = ""
    agent_type: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, object] | None) -> SessionMeta:
        """Extract session-bootstrap fields from a stdin payload."""
        if not payload:
            return cls()
        return cls(
            source=_as_str(payload.get("source")),
            model=_as_str(payload.get("model")),
            agent_type=_as_str(payload.get("agent_type")),
        )

    def lines(self) -> list[str]:
        """Return the bullet-list lines for this metadata block."""
        rows: list[str] = []
        if self.source:
            rows.append(f"- Session source: {self.source}")
        if self.model:
            rows.append(f"- Model: {self.model}")
        if self.agent_type:
            rows.append(f"- Agent: {self.agent_type}")
        return rows


@dataclass
class MemorySummary:
    """Structured view of a ``MEMORY.md`` index file."""

    overview: str = ""
    latest: str = ""
    topic_files: list[str] = field(default_factory=list)
    key_conventions: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        """Return the bullet-list lines for this memory block."""
        rows: list[str] = []
        if self.overview:
            rows.append(f"- Project overview: {self.overview}")
        if self.latest:
            rows.append(f"- Latest memory entry: {self.latest}")
        if self.topic_files:
            preview = ", ".join(self.topic_files[:_BULLET_PREVIEW_LIMIT])
            rows.append(f"- Topic files: {preview}")
        for convention in self.key_conventions[:_BULLET_PREVIEW_LIMIT]:
            rows.append(f"- Convention: {convention}")
        return rows


@dataclass
class PlanSummary:
    """Structured view of an active plan suite."""

    suite_name: str = ""
    status: str = ""
    phase_in_progress: str = ""
    task_in_progress: str = ""
    next_action: str = ""
    blockers: str = ""
    critical_files: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        """Return the bullet-list lines for this plan block."""
        rows: list[str] = []
        if self.suite_name:
            rows.append(f"- Active suite: {self.suite_name}")
        if self.status:
            rows.append(f"- Suite status: {self.status}")
        if self.phase_in_progress:
            rows.append(f"- Phase in progress: {self.phase_in_progress}")
        if self.task_in_progress:
            rows.append(f"- Task in progress: {self.task_in_progress}")
        if self.next_action:
            rows.append(f"- Next action: {self.next_action}")
        if self.blockers:
            rows.append(f"- Blockers: {self.blockers}")
        for path in self.critical_files[:_NUMBERED_PREVIEW_LIMIT]:
            rows.append(f"- Critical file: {path}")
        return rows


def _as_str(value: object) -> str:
    """Return `value` as a string, or empty when not a string."""
    return value if isinstance(value, str) else ""


def _iter_lines(path: Path) -> Iterator[str]:
    """Yield stripped lines from `path`, or nothing if unreadable."""
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                yield raw.rstrip("\r\n")
    except OSError as exc:
        _logger.debug("Unable to read %s: %s", path, exc)


def _section_lines(path: Path, heading: str) -> Iterator[str]:
    """Yield lines that appear under `heading` until the next H2."""
    in_section = False
    for line in _iter_lines(path):
        if not in_section:
            if line.strip() == heading:
                in_section = True
            continue
        if _H2.match(line):
            return
        yield line


def first_nonblank(path: Path, heading: str) -> str:
    """Return the first non-blank line under `heading`."""
    for line in _section_lines(path, heading):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def bold_field(path: Path, key: str) -> str:
    """Return the value of ``**Key:** value`` (first occurrence)."""
    for line in _iter_lines(path):
        match = _BOLD_FIELD.match(line)
        if match and match.group(1).strip() == key:
            return match.group(2).strip()
    return ""


def heading_value(path: Path, prefix: str) -> str:
    """Return the tail of the first line starting with `prefix`."""
    for line in _iter_lines(path):
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def topic_file_names(
    path: Path, heading: str, limit: int = _BULLET_PREVIEW_LIMIT
) -> list[str]:
    """Return up to `limit` linked ``.md`` filenames found under `heading`."""
    names: list[str] = []
    for line in _section_lines(path, heading):
        for match in _MARKDOWN_LINK.finditer(line):
            names.append(match.group(1))
            if len(names) >= limit:
                return names
    return names


def bullets_under(
    path: Path, heading: str, limit: int = _BULLET_PREVIEW_LIMIT
) -> list[str]:
    """Return up to `limit` bullet items under `heading`."""
    out: list[str] = []
    for line in _section_lines(path, heading):
        match = _BULLET.match(line)
        if match:
            out.append(match.group(1).strip())
            if len(out) >= limit:
                break
    return out


def numbered_under(
    path: Path, heading: str, limit: int = _NUMBERED_PREVIEW_LIMIT
) -> list[str]:
    """Return up to `limit` numbered-list items under `heading`."""
    out: list[str] = []
    for line in _section_lines(path, heading):
        match = _NUMBERED.match(line)
        if match:
            out.append(match.group(1).strip())
            if len(out) >= limit:
                break
    return out


def project_slug(root: Path) -> str:
    """Convert an absolute path to the canonical project-directory slug.

    The slug deliberately preserves consecutive ``-`` runs that arise from
    adjacent separators (e.g., ``\\.`` becomes ``--``). This matches the
    on-disk folder names already created by Claude Code under
    ``<root>/projects/`` — collapsing runs would break lookup of existing
    memory directories. The ``find_memory_index`` boundary-anchored
    leaf-suffix fallback (below) covers any residual slug drift.
    """
    text = str(root).rstrip("/\\").lower()
    for ch in (":", "\\", "/", "."):
        text = text.replace(ch, "-")
    return text


def find_memory_index(root: Path) -> Path | None:
    """Locate ``MEMORY.md`` for this project under ``<root>/projects``."""
    projects_root = root / "projects"
    if not projects_root.is_dir():
        return None

    direct = projects_root / project_slug(root) / "memory" / "MEMORY.md"
    if direct.is_file():
        return direct

    # Fallback for a project whose on-disk slug does not match ``project_slug``
    # byte-for-byte (path-separator or drive-letter drift). The project's leaf
    # directory name is the trailing kebab segment of the slug, so match it as a
    # boundary-anchored suffix — NEVER a bare substring. A substring test lets a
    # short leaf ('app') resolve another project's memory dir ('my-app-fork'),
    # crossing into an unrelated project's memory. Exact first, then a
    # separator-delimited suffix ('…-<leaf>'), so only a true leaf match wins.
    leaf = root.name.lower().lstrip(".")
    if not leaf:
        return None
    candidates = sorted(projects_root.glob("*/memory/MEMORY.md"), reverse=True)
    for candidate in candidates:
        parent_name = candidate.parent.parent.name.lower()
        if parent_name == leaf or parent_name.endswith(f"-{leaf}"):
            return candidate
    return None


def read_memory_summary(memory_path: Path) -> MemorySummary:
    """Parse a ``MEMORY.md`` index into a `MemorySummary`."""
    return MemorySummary(
        overview=first_nonblank(memory_path, "## Project Overview"),
        latest=bold_field(memory_path, "Latest"),
        topic_files=topic_file_names(memory_path, "## Topic Files"),
        key_conventions=bullets_under(memory_path, "## Key Conventions"),
    )


def _resolve_plan_suites_root(project_root: Path) -> Path:
    """Resolve the plans-suite root for the session-start Plan summary.

    Mirrors the statusline resolver in :mod:`apothem.statuslines.render`: the
    ``LLM_PLAN_SUITES_DIR`` override wins when set, else the canonical
    ``.apothem/plans`` tree, else the legacy ``.plans`` tree — the dual-read
    compatibility window for a workspace not yet upgraded with
    ``apothem migrate-workspace``. Defaulting to the legacy name alone would
    blind this summary to a migrated workspace's suite that the statusline
    already resolves correctly.
    """
    override = os.environ.get("LLM_PLAN_SUITES_DIR")
    if override:
        return project_root / override
    canonical = project_root / ".apothem" / "plans"
    if canonical.is_dir():
        return canonical
    return project_root / ".plans"


def find_active_suite(plans_root: Path) -> Path | None:
    """Return the most recently updated plan suite, or None."""
    if not plans_root.is_dir():
        return None
    best: tuple[float, Path] | None = None
    for entry in plans_root.iterdir():
        if not entry.is_dir():
            continue
        progress = entry / "PROGRESS.md"
        notes = entry / "PLAN-NOTES.md"
        if not (progress.is_file() and notes.is_file()):
            continue
        mtime = progress.stat().st_mtime
        if best is None or mtime > best[0]:
            best = (mtime, entry)
    return best[1] if best else None


def read_plan_summary(suite_dir: Path) -> PlanSummary:
    """Parse a plan suite's ``PROGRESS.md`` into a `PlanSummary`."""
    progress = suite_dir / "PROGRESS.md"
    return PlanSummary(
        suite_name=suite_dir.name,
        status=heading_value(progress, "## Status:"),
        phase_in_progress=bold_field(progress, "Phase in progress"),
        task_in_progress=bold_field(progress, "Task in progress"),
        next_action=bold_field(progress, "Next action"),
        blockers=bold_field(progress, "Blockers"),
        critical_files=numbered_under(progress, "### Critical Files for Next Phase"),
    )


def read_conformity_posture(root: Path) -> list[str]:
    """Read the conformity-posture context message, returning its lines.

    The conformity posture lives at ``hooks/messages/sessionstart.md``
    and surfaces a standing reminder block (working-trace pickup point,
    unresolved-inquiry enumeration, host-discovery freshness, gate
    awareness, trivial threshold). The bootstrap degrades gracefully
    into a three-block envelope when the file is absent or unreadable;
    a missing posture file does not break SessionStart.
    """

    path = root / "hooks" / "messages" / "sessionstart.md"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return text.splitlines()


def plugin_alone_pointer() -> list[str]:
    """Return a lean rules-pointer block when running plugin-alone, else [].

    When the SessionStart hook fires from the Claude Code plugin installed
    *alone* (via the marketplace, with no separate apothem engine install),
    Claude Code exports ``CLAUDE_PLUGIN_ROOT`` to the spawned hook process and
    the bundled behavioral rules sit under that root but cannot load as
    always-on plugin context. The engine install, by contrast, projects the
    rules through the harness root and leaves ``CLAUDE_PLUGIN_ROOT`` unset — so
    this block is emitted only for the plugin-alone posture and never regresses
    the engine-install session-start summary.

    The block is a short POINTER, never the full rule bodies (which are large):
    it names where the bundled rules live and states that the mechanical
    conformity hooks remain active. It locates the bundled ``rules/`` directory
    under the plugin root (``rules/`` in the assembled bundle, or
    ``src/apothem/rules/`` when the repository root is the plugin root) and
    cites whichever exists, falling back to the assembled location.

    Returns:
        The pointer block's lines, or an empty list when not plugin-alone.
    """
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not plugin_root:
        return []
    base = Path(plugin_root)
    for rel in ("rules", "src/apothem/rules"):
        if (base / rel).is_dir():
            rules_ref = f"${{CLAUDE_PLUGIN_ROOT}}/{rel}/"
            break
    else:
        rules_ref = "${CLAUDE_PLUGIN_ROOT}/rules/"
    return [
        "Apothem plugin posture:",
        (
            "- Apothem is installed as a Claude Code plugin alone (no engine "
            "install). Its behavioral rules are bundled at "
            f"{rules_ref} — consult them as governing guidance for this "
            "session; they are not auto-loaded as always-on context plugin-alone."
        ),
        (
            "- The mechanical conformity hooks (write/edit/bash guards, "
            "authorship-header and plans-locality checks, session and "
            "compaction handlers) remain active and fire on tool use."
        ),
    ]


def build_context(root: Path, payload: dict[str, object] | None) -> str:
    """Assemble the full additionalContext string."""
    blocks: list[list[str]] = []

    pointer = plugin_alone_pointer()
    if pointer:
        blocks.append(pointer)

    meta = SessionMeta.from_payload(payload)
    meta_lines = meta.lines()
    if meta_lines:
        blocks.append(["Session bootstrap:", *meta_lines])

    memory_index = find_memory_index(root)
    if memory_index is not None:
        summary = read_memory_summary(memory_index)
        memory_lines = summary.lines()
        if memory_lines:
            blocks.append(["Memory summary:", *memory_lines])

    active_suite = find_active_suite(_resolve_plan_suites_root(root))
    if active_suite is not None:
        plan_lines = read_plan_summary(active_suite).lines()
        blocks.append(["Plan summary:", *plan_lines])
    else:
        blocks.append(
            [
                "Plan summary:",
                "- No active plan suite detected. Ready for ad-hoc work.",
            ]
        )

    posture_lines = read_conformity_posture(root)
    if posture_lines:
        blocks.append(["Conformity posture:", *posture_lines])

    flat = [line for block in blocks for line in block]
    return normalize_ascii("\n".join(flat))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(prog="session_start_bootstrap")
    parser.add_argument("--quiet", "-q", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point. Emits a hook envelope (success or failure) and returns."""
    args = parse_args(argv)
    try:
        root = resolve_project_root(Mode.HOOKS, script_path=Path(__file__))
        if root is None:
            root = Path(__file__).resolve().parent.parent
        payload = read_hook_stdin()
        context = build_context(root, payload)
        emit_hook_envelope("SessionStart", context, args.quiet)
    except Exception as exc:
        # Outermost boundary. Emit a failure envelope so the harness
        # always sees a structurally valid SessionStart response, never
        # a traceback.
        emit_failure_envelope("SessionStart", str(exc))


if __name__ == "__main__":
    main()
