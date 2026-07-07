# SPDX-License-Identifier: MIT

"""Render the conformity operating-posture statusline.

The statusline surfaces three values from the operating agent's working
trace: the active sprint goal, the unresolved inquiry count, and the
current phase / sub-phase pointer. It is agnostic — every value is
read from the most-recently-touched plan suite's PROGRESS.md, never
hardcoded.

This is the single statusline renderer. The harness wires it through the
``conformity.json`` statusline-config snippet (a ``type: command`` entry
whose command invokes this module). The harness pipes its statusline
JSON payload on stdin; the renderer consumes only ``workspace.project_dir``
to locate the project-local plans tree, and ignores the session-context
fields (model / cost / duration) that the harness surfaces natively.

Output shape — single line on stdout:

    [<phase-pointer> | <sprint-goal-truncated> | <inquiry-count> inquir(y|ies)]

Separators are ASCII pipes so the statusline renders identically across
PowerShell, bash, and IDE harness terminals regardless of code-page.

Plans-root resolution (harness-agnostic, no harness path hardcoded):

1. ``$LLM_PLAN_SUITES_DIR`` when set — the operator override.
2. ``<workspace.project_dir>/.apothem/plans/`` from the stdin payload — the
   canonical project-local plans tree per the plans-locality discipline,
   falling back to the legacy ``<workspace.project_dir>/.plans/`` when the
   canonical tree is absent (dual-read compatibility window).
3. ``<cwd>/.apothem/plans/`` when no payload is supplied — the interactive
   fallback, with the same legacy ``<cwd>/.plans/`` fallback.

Degradation modes:

* No plan suite under the resolved plans root → ``[no active suite]``.
* Suite present but PROGRESS.md unparseable → goal / pointer segments omitted.
* Sprint Goal absent in active phase's PHASE.md → goal segment omitted.

The renderer never raises to stdout. Any unexpected exception is caught
at the outermost boundary and a degraded one-line marker is emitted so
the harness's statusline rendering never breaks.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# The Apothem-owned working-directory name and its plans child. The plans root
# is ``<base>/.apothem/plans`` — computed inline here (mirroring
# ``apothem.lib.data_home.plans_root``) rather than imported, so this renderer
# stays a self-contained stdlib script: a plugin-alone install ships
# ``render.py`` without the ``apothem`` package on the path, and a module-level
# ``apothem.lib`` import would raise ``ModuleNotFoundError`` at import time,
# before ``main``'s never-fail catch-all could convert it to a degraded marker.
_APOTHEM_SUBTREE: Final[str] = ".apothem"
_PLANS_CHILD: Final[str] = "plans"

# Cap on the rendered sprint-goal substring so the statusline stays
# bounded across narrow terminal widths. PHASE.md Sprint Goal sentences
# regularly exceed 200 characters; the truncation preserves enough
# context for the operator to recognize the goal without dominating the
# statusline.
_SPRINT_GOAL_CHARLIMIT: Final[int] = 80

# Cap on the active-phase pointer substring. Phase headings include
# zero-padded numbers and kebab-case topics; 60 characters is the
# observed upper bound across active plan suites without truncation.
_PHASE_POINTER_CHARLIMIT: Final[int] = 60

# Environment override for the plans root. When set, it wins over the
# stdin payload's project-local resolution — the operator escape hatch.
_PLANS_DIR_ENV: Final[str] = "LLM_PLAN_SUITES_DIR"

_ACTIVE_PHASE_FIELD = re.compile(
    r"^-\s+\*\*Active phase:\*\*\s+(.+?)(?=\s+—|\s+-\s|$)",
    re.MULTILINE,
)
_PHASE_IN_PROGRESS_FIELD = re.compile(
    r"^-\s+\*\*Phase in progress:\*\*\s+(.+?)(?=\s+—|\s+-\s|$)",
    re.MULTILINE,
)
_SPRINT_GOAL_LINE = re.compile(
    r"^>\s+\*\*Sprint Goal\.\*\*\s+(.+)$",
    re.MULTILINE,
)
# Match concrete placeholders only. Payload contains no nested brackets
# AND no ellipsis (Unicode `…` or ASCII `..`+). The negative lookaheads
# exclude template citations such as `<USER-CONFIRM:id=<id>>`,
# `<USER-CONFIRM:…>`, and `<USER-CONFIRM:kind=...; ...>` that appear in
# design-source and rule prose discussing the placeholder syntax itself.
_USER_CONFIRM_PLACEHOLDER = re.compile(r"<USER-CONFIRM:(?![^>]*(?:\.\.|…))[^<>]+>")

# The ellipsis marker appended to a truncated segment. It is the single-char
# ``…``, which ``_ascii_safe`` later transliterates to the three-char ``...`` —
# so a truncated segment reserves three characters for the marker to keep the
# FINAL rendered width within the character limit. Truncating naively to
# ``limit - 1`` + ``…`` overshot to ``limit + 2`` after transliteration.
_ELLIPSIS: Final[str] = "…"
_ELLIPSIS_ASCII_WIDTH: Final[int] = 3


def _truncate(text: str, limit: int) -> str:
    """Return *text* bounded so its ASCII-safe render stays within *limit* chars.

    A segment at or under *limit* is returned unchanged. A longer segment is cut
    to ``limit - _ELLIPSIS_ASCII_WIDTH`` characters and the ``…`` marker
    appended; since ``_ascii_safe`` expands ``…`` to ``...`` (three chars), the
    final rendered width is exactly *limit*, never over it.
    """
    if len(text) <= limit:
        return text
    return text[: limit - _ELLIPSIS_ASCII_WIDTH] + _ELLIPSIS


@dataclass(frozen=True)
class StatuslineParts:
    """The three values rendered on the statusline.

    Attributes:
        phase_pointer: Active phase / sub-phase identifier, or ``None``
            when absent.
        sprint_goal: The active phase's Sprint Goal sentence,
            truncated to ``_SPRINT_GOAL_CHARLIMIT``, or ``None`` when
            absent.
        inquiry_count: Total `<USER-CONFIRM:…>` placeholders detected
            across the active suite's ecosystem-emitted artifacts.
    """

    phase_pointer: str | None
    sprint_goal: str | None
    inquiry_count: int


def _most_recent_suite(plans_dir: Path) -> Path | None:
    """Return the most-recently-modified suite folder under ``plans_dir``."""

    if not plans_dir.is_dir():
        return None
    candidates = [p for p in plans_dir.iterdir() if p.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _extract_phase_pointer(progress_text: str) -> str | None:
    """Extract the active-phase pointer from PROGRESS.md text."""

    for pattern in (_ACTIVE_PHASE_FIELD, _PHASE_IN_PROGRESS_FIELD):
        match = pattern.search(progress_text)
        if match:
            pointer = match.group(1).strip()
            return _truncate(pointer, _PHASE_POINTER_CHARLIMIT)
    return None


def _extract_sprint_goal(suite_root: Path, phase_pointer: str | None) -> str | None:
    """Read the active phase's PHASE.md and return its Sprint Goal."""

    if phase_pointer is None:
        return None
    phase_id_match = re.match(r"Phase\s+(\d+[A-Z]?)", phase_pointer)
    if not phase_id_match:
        return None
    phase_id = phase_id_match.group(1).lower()
    phases_dir = suite_root / "phases"
    if not phases_dir.is_dir():
        return None
    matches = [
        p
        for p in phases_dir.iterdir()
        if p.is_dir() and p.name.startswith(f"{phase_id}-")
    ]
    if not matches:
        return None
    phase_md = matches[0] / "PHASE.md"
    if not phase_md.is_file():
        return None
    try:
        text = phase_md.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _SPRINT_GOAL_LINE.search(text)
    if not match:
        return None
    goal = match.group(1).strip()
    return _truncate(goal, _SPRINT_GOAL_CHARLIMIT)


def _count_unresolved_inquiries(suite_root: Path) -> int:
    """Return the count of `<USER-CONFIRM:…>` placeholders in the suite."""

    total = 0
    for path in suite_root.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        total += len(_USER_CONFIRM_PLACEHOLDER.findall(text))
    return total


def _parse_payload(raw: str) -> dict[str, object]:
    """Parse the harness statusline JSON payload, tolerating malformed input."""

    if not raw.strip():
        return {}
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


def _read_payload() -> dict[str, object]:
    """Read and parse the harness statusline JSON payload from stdin.

    Returns an empty mapping when stdin is a terminal (interactive run with
    no piped payload) or when the read / parse fails. The renderer then
    falls back to the working-directory plans tree.
    """

    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    return _parse_payload(raw)


def _payload_project_dir(payload: dict[str, object]) -> str | None:
    """Extract ``workspace.project_dir`` from the harness payload, or None."""

    workspace = payload.get("workspace")
    if isinstance(workspace, dict):
        project_dir = workspace.get("project_dir")
        if isinstance(project_dir, str) and project_dir:
            return project_dir
    return None


def _resolve_plans_dir(payload: dict[str, object]) -> Path:
    """Resolve the plans root, harness-agnostic and project-local.

    Resolution order: the ``LLM_PLAN_SUITES_DIR`` operator override, then the
    payload's ``workspace.project_dir`` resolved to the canonical
    ``.apothem/plans`` tree, then the current working directory resolved the
    same way as the interactive fallback. The canonical project-local plans
    home is ``<project-root>/.apothem/plans``; an operator with a legacy
    ``.plans`` tree upgrades it via ``apothem migrate-workspace``. No harness
    config path is ever hardcoded.
    """

    override = os.environ.get(_PLANS_DIR_ENV)
    if override:
        return Path(override)
    project_dir = _payload_project_dir(payload)
    base = Path(project_dir) if project_dir else Path.cwd()
    return base / _APOTHEM_SUBTREE / _PLANS_CHILD


def gather(plans_dir: Path) -> StatuslineParts | None:
    """Walk the plans tree at ``plans_dir`` and assemble the statusline values."""

    suite = _most_recent_suite(plans_dir)
    if suite is None:
        return None
    progress_md = suite / "PROGRESS.md"
    if not progress_md.is_file():
        return StatuslineParts(phase_pointer=None, sprint_goal=None, inquiry_count=0)
    try:
        progress_text = progress_md.read_text(encoding="utf-8")
    except OSError:
        return StatuslineParts(phase_pointer=None, sprint_goal=None, inquiry_count=0)
    phase_pointer = _extract_phase_pointer(progress_text)
    sprint_goal = _extract_sprint_goal(suite, phase_pointer)
    inquiry_count = _count_unresolved_inquiries(suite)
    return StatuslineParts(
        phase_pointer=phase_pointer,
        sprint_goal=sprint_goal,
        inquiry_count=inquiry_count,
    )


# Transliterations applied during ASCII normalization. Each mapping
# preserves the surrounding sentence's intent while staying within the
# 7-bit ASCII intersection so the statusline renders the same bytes on
# Windows console, POSIX terminals, and IDE harnesses. Keys use
# Unicode escape sequences so the source itself is ASCII-clean.
_ASCII_TRANSLIT: Final[dict[str, str]] = {
    chr(0x00A7): "S",  # U+00A7 SECTION SIGN
    chr(0x2014): "-",  # U+2014 EM DASH
    chr(0x2013): "-",  # U+2013 EN DASH
    chr(0x00B7): "*",  # U+00B7 MIDDLE DOT
    chr(0x2026): "...",  # U+2026 HORIZONTAL ELLIPSIS
    chr(0x2018): "'",  # U+2018 LEFT SINGLE QUOTATION MARK
    chr(0x2019): "'",  # U+2019 RIGHT SINGLE QUOTATION MARK
    chr(0x201C): '"',  # U+201C LEFT DOUBLE QUOTATION MARK
    chr(0x201D): '"',  # U+201D RIGHT DOUBLE QUOTATION MARK
}


def _ascii_safe(text: str) -> str:
    """Return an ASCII-only rendering of ``text``.

    Common typographic characters get transliterated; any remaining
    non-ASCII character is dropped. The output is safe for any
    terminal code-page without depending on stdout reconfiguration.
    """

    for src, dst in _ASCII_TRANSLIT.items():
        text = text.replace(src, dst)
    return text.encode("ascii", errors="ignore").decode("ascii")


def render(parts: StatuslineParts | None) -> str:
    """Compose the single-line statusline string."""

    if parts is None:
        return "[no active suite]"
    segments: list[str] = []
    if parts.phase_pointer:
        segments.append(_ascii_safe(parts.phase_pointer))
    if parts.sprint_goal:
        segments.append(_ascii_safe(parts.sprint_goal))
    inquiry_word = "inquiry" if parts.inquiry_count == 1 else "inquiries"
    # The inquiry-count segment is always appended, so ``segments`` is never
    # empty here — the count renders even when phase / goal are absent (that is
    # the ``[N inquiries]`` degradation mode). No "[no readable state]" fallback
    # is reachable.
    segments.append(f"{parts.inquiry_count} {inquiry_word}")
    return "[" + " | ".join(segments) + "]"


def main() -> int:
    """Print the rendered statusline to stdout. Always exits 0."""

    try:
        payload = _read_payload()
        plans_dir = _resolve_plans_dir(payload)
        parts = gather(plans_dir)
        sys.stdout.write(render(parts) + "\n")
    except Exception as exc:
        # Outermost boundary. The harness reads stdout as the rendered
        # statusline; never leak a traceback or non-zero exit. Emit a
        # degraded marker naming the failure class so the operator can
        # diagnose without losing the statusline surface.
        sys.stdout.write(f"[statusline error: {type(exc).__name__}]\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
