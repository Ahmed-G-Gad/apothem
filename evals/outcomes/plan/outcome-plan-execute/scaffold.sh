#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p '.apothem/plans/notes-app/_spec'
cat > '.apothem/plans/notes-app/_spec/spec.md' <<'FIXTURE'
# Notes App — Spec

## Goal
A command-line notes app that stores notes as Markdown files under ~/.notes, with tags and full-text search.

## Requirements
- R1 `notes add <title>` creates a note file with the title and its creation date.
- R2 `notes tag <id> <tag>` adds a tag; tags are stored in the note's frontmatter.
- R3 `notes search <text>` prints matching note titles, case-insensitive, over title and body.
- R4 `notes export --csv` writes all notes to one CSV file.

## Constraints
- Python 3.11, standard library only.
- Tests with pytest; every requirement has a test.

## Out of scope
- Sync between machines.
FIXTURE

mkdir -p '.apothem/plans/notes-app'
cat > '.apothem/plans/notes-app/PREAMBLE.md' <<'FIXTURE'
# Notes App — Preamble
Mission: ship the notes CLI described in _spec/spec.md. Seriousness: PERSONAL_USE.
Inputs: _spec/spec.md. Phases: 01 storage, 02 search, 03 export.
FIXTURE

mkdir -p '.apothem/plans/notes-app'
cat > '.apothem/plans/notes-app/MASTER-PLAN.md' <<'FIXTURE'
# Notes App — Master Plan

| Phase | Topic | Depends on | Covers |
| --- | --- | --- | --- |
| 01 | storage: add and tag notes | — | R1, R2 |
| 02 | search | 01 | R3 |
| 03 | export | 01 | R4 |
FIXTURE

mkdir -p '.apothem/plans/notes-app'
cat > '.apothem/plans/notes-app/PROGRESS.md' <<'FIXTURE'
# Notes App — Progress

| Phase | Status | Report |
| --- | --- | --- |
| 01 storage | done | phases/01-storage/REPORT.md |
| 02 search | pending | — |
| 03 export | pending | — |

Next: phase 02 (search).
FIXTURE

mkdir -p '.apothem/plans/notes-app'
cat > '.apothem/plans/notes-app/PLAN-NOTES.md' <<'FIXTURE'
# Notes App — Plan Notes (decision ledger, append-only)

- D1 Notes are stored one Markdown file per note under ~/.notes; the file name is a zero-padded id.
- D2 Tags live in each note's YAML frontmatter as a list.
- D3 Standard library only; argparse for the CLI.
FIXTURE

mkdir -p '.apothem/plans/notes-app/phases/01-storage'
cat > '.apothem/plans/notes-app/phases/01-storage/PHASE.md' <<'FIXTURE'
# Phase 01 — Storage

Tasks:
- T1 Create notes_app/store.py with add_note(title) -> int and tag_note(note_id, tag) -> None.
- T2 Add tests/test_store.py covering R1 and R2.

Acceptance: pytest passes; a note file carries its title, creation date and tags.
FIXTURE

mkdir -p '.apothem/plans/notes-app/phases/01-storage'
cat > '.apothem/plans/notes-app/phases/01-storage/REPORT.md' <<'FIXTURE'
# Phase 01 — Report
Status: done. T1 and T2 landed; tests/test_store.py passes (4 tests).
FIXTURE

mkdir -p '.apothem/plans/notes-app/phases/02-search'
cat > '.apothem/plans/notes-app/phases/02-search/PHASE.md' <<'FIXTURE'
# Phase 02 — Search

Tasks:
- T1 Create notes_app/search.py with search(notes_dir: pathlib.Path, text: str) -> list[str] that returns
  the titles of notes whose title or body contains text, case-insensitive, sorted by note id.
- T2 Add tests/test_search.py covering R3: a match in the title, a match in the body, no match, and case.

Acceptance: pytest passes; search("TODO") and search("todo") return the same titles.
FIXTURE

mkdir -p '.apothem/plans/notes-app/phases/03-export'
cat > '.apothem/plans/notes-app/phases/03-export/PHASE.md' <<'FIXTURE'
# Phase 03 — Export

Tasks:
- T1 Create notes_app/export.py with export_csv(notes_dir, out_path) writing id, title, created, tags.
FIXTURE

mkdir -p 'notes_app'
cat > 'notes_app/__init__.py' <<'FIXTURE'
"""Notes app."""
FIXTURE

mkdir -p 'notes_app'
cat > 'notes_app/store.py' <<'FIXTURE'
"""Note storage: one Markdown file per note."""

from __future__ import annotations

import datetime
from pathlib import Path

NOTES_DIR = Path.home() / ".notes"


def add_note(title: str, notes_dir: Path = NOTES_DIR) -> int:
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_id = len(list(notes_dir.glob("*.md"))) + 1
    created = datetime.date.today().isoformat()
    text = f"---\ntitle: {title}\ncreated: {created}\ntags: []\n---\n"
    (notes_dir / f"{note_id:04d}.md").write_text(text, encoding="utf-8")
    return note_id
FIXTURE
