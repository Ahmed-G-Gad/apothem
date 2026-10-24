# SPDX-License-Identifier: MIT

"""Measure the Claude Code emission of every command against the skill cap.

Claude Code re-attaches only the first 5,000 tokens of an invoked skill after a
context compaction, so the Claude Code emission splits each command into a slim
``SKILL.md`` plus ``references/`` files (``apothem.lib.claude_skill_split``).
This script reports, per command, the source size, the emitted ``SKILL.md`` in
the plugin tree and in the engine install, the reference files, the headroom
to the split budget and whether the engine file fits the cap. The default
install root is the fixed path ``/home/user/.claude``, so the numbers are the
same on every machine.

Usage::

    python scripts/dev/measure_claude_skills.py                 # table
    python scripts/dev/measure_claude_skills.py --json          # machine-readable
    python scripts/dev/measure_claude_skills.py --check         # exit 1 on a breach
    python scripts/dev/measure_claude_skills.py --cap 18000     # what-if cap

``--check`` exits 1 when a command-derived skill exceeds the cap even under a
120-character install root, a split exceeds its budget, a ``SKILL.md`` runs
past 500 lines, a split does not restore to its source, a folded frontmatter
does not unfold to its source, or a native skill breaks its cap or its pinned
ceiling.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Vendored dependencies first, then the engine: the order bin/apothem.mjs and
# assemble_plugin_tree.py use, so the script runs from a bare checkout.
for _path in (_REPO_ROOT / "src" / "apothem" / "_vendor", _REPO_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import yaml  # noqa: E402

from apothem.harnesses._shared.install_driver_converters import (  # noqa: E402
    _installed_reference_note,
    claude_code_skill_text,
)
from apothem.lib.claude_skill_frontmatter import METADATA_KEYS  # noqa: E402
from apothem.lib.claude_skill_split import (  # noqa: E402
    BYTES_PER_TOKEN,
    NATIVE_SKILL_CEILINGS,
    NOTE_RESERVE_BYTES,
    SKILL_MD_CAP_BYTES,
    SKILL_MD_MAX_LINES,
    WINDOW_TOKENS,
    restore_command_skill,
    split_command_skill,
    without_bindings,
)
from apothem.lib.frontmatter import split_frontmatter  # noqa: E402

#: Source package the commands and skills are read from.
SRC_ROOT = _REPO_ROOT / "src" / "apothem"
#: Fixed install root: the note's size depends on it, so the report must not.
DEFAULT_ROOT = Path("/home/user/.claude")
#: Install-root length the cap must hold at (the note reserve covers up to 140).
CHECK_ROOT_LENGTH = 120
#: Headroom under this many bytes is reported as a warning.
HEADROOM_WARN_BYTES = 300

_DOC_FILES = frozenset({"README.md", "AGENTS.md"})


@dataclass(frozen=True)
class Row:
    """The measurements of one command."""

    name: str
    shadowed: bool  # a native skill of the same name is what ships
    source_bytes: int
    plugin_bytes: int  # SKILL.md in the plugin tree (no note)
    engine_bytes: int  # SKILL.md in the engine install (with the note)
    reference_bytes: int
    reference_count: int
    step_files: int
    moved_sections: tuple[str, ...]
    budget_bytes: int
    headroom_bytes: int  # budget minus plugin_bytes; negative is a breach
    headroom_warning: bool
    fits_cap: bool  # engine_bytes within the cap
    fits_cap_long_root: bool  # the same under a 120-character install root
    est_tokens: int
    fits_window: bool
    lines: int
    restore_ok: bool
    unfold_ok: bool


@dataclass(frozen=True)
class NativeRow:
    """A native skill, listed for information."""

    name: str
    bytes: int
    lines: int
    ceiling: int | None  # the pinned over-cap ceiling, when there is one
    over_cap: bool
    ok: bool  # within the cap, or over it within its pinned ceiling


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


def _fields(text: str) -> dict[str, object]:
    parts = split_frontmatter(text)
    if parts is None:
        return {}
    loaded = yaml.safe_load(parts[0].split("\n", 1)[1].rsplit("---", 1)[0])
    return loaded if isinstance(loaded, dict) else {}


def _unfolds(source: str, emitted: str) -> bool:
    """Return True when undoing the fold and the rename restores the source keys."""
    fields = _fields(emitted)
    metadata = fields.pop("metadata", {})
    if not isinstance(metadata, dict) or not set(metadata) <= set(METADATA_KEYS):
        return False
    if "user-invocable" in fields:
        fields["userInvocable"] = fields.pop("user-invocable")
    fields.update(metadata)
    return fields == _fields(source)


def _budget(cap: int) -> int:
    return cap - NOTE_RESERVE_BYTES


def measure(*, install_root: Path = DEFAULT_ROOT, cap: int | None = None) -> list[Row]:
    """Return one :class:`Row` per command, sorted by name.

    Args:
        install_root: Root whose ``## Installed Reference Paths`` note is
            appended for the engine figures.
        cap: Re-split at a budget of ``cap`` minus the note reserve and judge
            against ``cap``. ``None`` uses the production budget and cap.
    """
    limit = SKILL_MD_CAP_BYTES if cap is None else cap
    note = _installed_reference_note("claude_code", install_root)
    long_note = _installed_reference_note(
        "claude_code", Path("/" + "r" * (CHECK_ROOT_LENGTH - 1))
    )
    native = {p.parent.name for p in (SRC_ROOT / "skills").glob("*/SKILL.md")}
    rows: list[Row] = []
    for command in sorted((SRC_ROOT / "commands").glob("*.md")):
        if command.name in _DOC_FILES:
            continue
        source = command.read_text(encoding="utf-8")
        folded = claude_code_skill_text(source)
        split = (
            split_command_skill(folded)
            if cap is None
            else split_command_skill(folded, budget=_budget(cap))
        )
        plugin = split.skill.rstrip() + "\n"
        engine_bytes = _size(plugin + note)
        budget = _budget(limit)
        headroom = budget - _size(plugin)
        tokens = round(engine_bytes / BYTES_PER_TOKEN)
        rows.append(
            Row(
                name=command.stem,
                shadowed=command.stem in native,
                source_bytes=_size(source),
                plugin_bytes=_size(plugin),
                engine_bytes=engine_bytes,
                reference_bytes=sum(_size(t) for t in split.references.values()),
                reference_count=len(split.references),
                step_files=len(split.moved_steps),
                moved_sections=split.moved_sections,
                budget_bytes=budget,
                headroom_bytes=headroom,
                headroom_warning=headroom < HEADROOM_WARN_BYTES,
                fits_cap=engine_bytes <= limit,
                fits_cap_long_root=_size(plugin + long_note) <= limit,
                est_tokens=tokens,
                fits_window=tokens <= WINDOW_TOKENS,
                lines=len(plugin.split("\n")) - 1,
                restore_ok=restore_command_skill(split.skill, split.references)
                == without_bindings(folded),
                unfold_ok=_unfolds(source, folded),
            )
        )
    return sorted(rows, key=lambda row: row.name)


def native_skills(*, cap: int | None = None) -> list[NativeRow]:
    """Return one :class:`NativeRow` per native skill, sorted by name."""
    limit = SKILL_MD_CAP_BYTES if cap is None else cap
    rows: list[NativeRow] = []
    for skill in sorted((SRC_ROOT / "skills").glob("*/SKILL.md")):
        text = claude_code_skill_text(skill.read_text(encoding="utf-8"))
        size = _size(text)
        ceiling = NATIVE_SKILL_CEILINGS.get(skill.parent.name)
        over = size > limit
        ok = (not over) if ceiling is None else (over and size <= ceiling)
        rows.append(
            NativeRow(skill.parent.name, size, text.count("\n"), ceiling, over, ok)
        )
    return rows


def problems(
    rows: Sequence[Row], natives: Sequence[NativeRow], *, cap: int | None = None
) -> list[str]:
    """Return the ``--check`` failures, one line each."""
    limit = SKILL_MD_CAP_BYTES if cap is None else cap
    found: list[str] = []
    for row in rows:
        if not row.restore_ok:
            found.append(f"{row.name}: split does not restore to the source")
        if not row.unfold_ok:
            found.append(f"{row.name}: folded frontmatter does not unfold")
        if row.shadowed:
            continue
        if not row.fits_cap_long_root:
            found.append(f"{row.name}: over {limit} B under a 120-character root")
        if row.headroom_bytes < 0:
            found.append(f"{row.name}: {-row.headroom_bytes} B over the split budget")
        if row.lines > SKILL_MD_MAX_LINES:
            found.append(f"{row.name}: {row.lines} lines, over {SKILL_MD_MAX_LINES}")
        if cap is None and not row.fits_window:
            found.append(
                f"{row.name}: about {row.est_tokens} tokens, over the "
                f"{WINDOW_TOKENS}-token post-compaction window"
            )
    for native in natives:
        if not native.ok:
            found.append(f"native skill {native.name}: {native.bytes} B breaks its cap")
    return found


def _table(rows: Sequence[Row], natives: Sequence[NativeRow], limit: int) -> str:
    out = [
        f"{'command':22s} {'source':>7s} {'plugin':>7s} {'engine':>7s} "
        f"{'refs B':>7s} {'refs':>4s} {'steps':>5s} {'room':>6s} {'tok':>5s} "
        f"{'lines':>5s}  notes"
    ]
    for row in sorted(rows, key=lambda r: (-r.engine_bytes, r.name)):
        notes: list[str] = []
        if row.shadowed:
            notes.append("shadowed by native skill")
        if row.headroom_warning:
            notes.append("LOW HEADROOM")
        if not row.fits_cap:
            notes.append("OVER CAP")
        if not row.fits_window:
            notes.append("OVER WINDOW")
        if row.moved_sections:
            notes.append("moved: " + ", ".join(row.moved_sections))
        out.append(
            f"{row.name:22s} {row.source_bytes:7d} {row.plugin_bytes:7d} "
            f"{row.engine_bytes:7d} {row.reference_bytes:7d} {row.reference_count:4d} "
            f"{row.step_files:5d} {row.headroom_bytes:6d} {row.est_tokens:5d} "
            f"{row.lines:5d}  " + "; ".join(notes)
        )
    emitted = [r for r in rows if not r.shadowed]
    out.append("")
    out.append(
        f"{len(rows)} commands, {len(emitted)} emitted; cap {limit} B "
        f"({BYTES_PER_TOKEN} B/token estimate, {WINDOW_TOKENS}-token window)."
    )
    out.append(
        f"max engine SKILL.md {max(r.engine_bytes for r in emitted)} B, "
        f"max plugin SKILL.md {max(r.plugin_bytes for r in emitted)} B, "
        f"{sum(r.reference_count for r in emitted)} reference files "
        f"({sum(r.step_files for r in emitted)} step files)."
    )
    out.append("")
    out.append("Native skills (informational):")
    for native in sorted(natives, key=lambda n: (-n.bytes, n.name)):
        flag = ""
        if native.ceiling is not None:
            flag = f"  PINNED over cap, ceiling {native.ceiling} B"
        elif native.over_cap:
            flag = "  OVER CAP"
        out.append(
            f"  {native.name:22s} {native.bytes:7d} B {native.lines:4d} lines{flag}"
        )
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the report; return 1 under ``--check`` when it finds a problem."""
    parser = argparse.ArgumentParser(
        description="Measure the Claude Code skill emission against its cap."
    )
    parser.add_argument(
        "--json", action="store_true", help="print JSON instead of a table"
    )
    parser.add_argument("--check", action="store_true", help="exit 1 on any problem")
    parser.add_argument(
        "--cap", type=int, help="re-split and judge at this cap in bytes"
    )
    parser.add_argument(
        "--install-root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"install root for the note (default {DEFAULT_ROOT.as_posix()})",
    )
    args = parser.parse_args(argv)
    rows = measure(install_root=args.install_root, cap=args.cap)
    natives = native_skills(cap=args.cap)
    found = problems(rows, natives, cap=args.cap)
    limit = SKILL_MD_CAP_BYTES if args.cap is None else args.cap
    if args.json:
        payload = {
            "cap_bytes": limit,
            "budget_bytes": _budget(limit),
            "note_reserve_bytes": NOTE_RESERVE_BYTES,
            "install_root": args.install_root.as_posix(),
            "bytes_per_token": BYTES_PER_TOKEN,
            "commands": [asdict(row) for row in rows],
            "native_skills": [asdict(native) for native in natives],
            "problems": found,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(_table(rows, natives, limit))
        for line in found:
            print(f"PROBLEM: {line}")
    return 1 if args.check and found else 0


if __name__ == "__main__":
    raise SystemExit(main())
