#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p '.'
cat > 'question.md' <<'FIXTURE'
Question: does adopting type hints in a Python project change how many bug reports it gets?
Context: we can mine public issue trackers and commit histories.
FIXTURE

mkdir -p '.apothem/plans/typed-python/_inputs'
cat > '.apothem/plans/typed-python/_inputs/ideation.md' <<'FIXTURE'
# Ideation
Problem space: static typing in dynamically typed codebases. Anchor: defect-prevention theory.
Ranked slate: 1) type hints and bug-report rates (chosen); 2) type hints and onboarding time.
FIXTURE
