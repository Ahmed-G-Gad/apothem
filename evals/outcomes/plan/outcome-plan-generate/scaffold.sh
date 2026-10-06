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
