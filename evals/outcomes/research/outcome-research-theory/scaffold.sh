#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Seeds the workspace for this case (runs only with --scaffold).
set -euo pipefail

mkdir -p '.apothem/plans/typed-python/_inputs'
cat > '.apothem/plans/typed-python/_inputs/ideation.md' <<'FIXTURE'
# Ideation
Problem space: static typing in dynamically typed codebases. Anchor: defect-prevention theory.
Ranked slate: 1) type hints and bug-report rates (chosen); 2) type hints and onboarding time.
FIXTURE

mkdir -p '.apothem/plans/typed-python/_spec'
cat > '.apothem/plans/typed-python/_spec/research-spec.md' <<'FIXTURE'
# Research Spec
Question: does adopting type hints in a Python project change the rate of bug reports?
H1: projects reduce bug reports per 1,000 commits after adopting type hints. H0: no change.
Scope: open-source Python projects with at least 500 commits before and after adoption.
Inclusion: public issue tracker with a bug label. Exclusion: projects that changed tracker during the window.
Success metric: bug reports per 1,000 commits. Glossary: adoption = mypy in CI plus 50% annotated functions.
FIXTURE
