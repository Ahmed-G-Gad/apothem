#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p '.'
cat > 'requirements.md' <<'FIXTURE'
Notes app, rough requirements from the kickoff call:

- A command-line notes app. Notes are Markdown files under ~/.notes, one file per note.
- `notes add <title>` creates a note with the title and the creation date.
- `notes tag <id> <tag>` adds a tag; tags live in the note's frontmatter.
- `notes search <text>` prints the titles of matching notes, case-insensitive, over title and body.
- `notes export --csv` writes every note to one CSV file.
- Python 3.11, standard library only, tests with pytest. No sync between machines.
FIXTURE
