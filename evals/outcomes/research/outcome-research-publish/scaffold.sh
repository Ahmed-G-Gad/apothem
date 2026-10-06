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

mkdir -p '.apothem/plans/typed-python/_inputs'
cat > '.apothem/plans/typed-python/_inputs/theory.md' <<'FIXTURE'
# Theory
Mechanism: annotations move a class of type errors from runtime to check time.
Constructs: annotation coverage, checker strictness, bug-report rate. Prediction: rate falls as coverage rises.
FIXTURE

mkdir -p '.apothem/plans/typed-python/_inputs'
cat > '.apothem/plans/typed-python/_inputs/source-ledger.md' <<'FIXTURE'
# Source Ledger
| ID | Source | Rank | Screen |
| --- | --- | --- | --- |
| S1 | corpus/fixture-study-a.md | 1 | included |
| S2 | corpus/fixture-study-b.md | 2 | included |
| S3 | corpus/fixture-study-c.md | 3 | excluded (no bug data) |
FIXTURE

mkdir -p '.apothem/plans/typed-python/_inputs'
cat > '.apothem/plans/typed-python/_inputs/synthesis.md' <<'FIXTURE'
# Synthesis
SOTA: S1 reports fewer type-related bug reports after adoption; S2 finds no change in total bug reports.
Gap: no study separates type-related from other bug reports across matched before/after windows.
FIXTURE

mkdir -p '.apothem/plans/typed-python/_inputs'
cat > '.apothem/plans/typed-python/_inputs/proposal.md' <<'FIXTURE'
# Proposal
Aim: measure the change in bug-report rate after type-hint adoption in matched windows.
Objectives: O1 build the project sample; O2 label bug reports; O3 compare rates.
FIXTURE

mkdir -p '.apothem/plans/typed-python/_inputs'
cat > '.apothem/plans/typed-python/_inputs/study-design.md' <<'FIXTURE'
# Study Design
Prediction: bug reports per 1,000 commits fall after adoption. Unit: project. Design: interrupted time series.
Variables: IV adoption (before/after); DV bug-report rate; controls: commit volume, contributor count.
Power: 40 projects detect a 20% change at alpha 0.05 with power 0.8.
FIXTURE

mkdir -p '.apothem/plans/typed-python/_inputs'
cat > '.apothem/plans/typed-python/_inputs/preregistration.md' <<'FIXTURE'
# Preregistration
Primary outcome: bug reports per 1,000 commits. Test: paired Wilcoxon signed-rank, two-sided, alpha 0.05.
Effect size: median difference with a 95% bootstrap confidence interval. Correction: Holm across 2 outcomes.
FIXTURE

mkdir -p '.apothem/plans/typed-python/_outputs'
cat > '.apothem/plans/typed-python/_outputs/experiment-log.md' <<'FIXTURE'
# Experiment Log
2026-09-20 collected 6 projects per protocol; seed 7; raw data in data/bug-rates.csv.
FIXTURE

mkdir -p 'data'
cat > 'data/bug-rates.csv' <<'FIXTURE'
project,before_rate,after_rate
alpha,4.1,3.2
bravo,2.7,2.5
charlie,5.0,3.9
delta,3.3,3.4
echo,6.2,4.8
foxtrot,1.9,1.7
FIXTURE

mkdir -p '.apothem/plans/typed-python/_outputs'
cat > '.apothem/plans/typed-python/_outputs/analysis.md' <<'FIXTURE'
# Analysis
Wilcoxon signed-rank on 6 projects: median difference -0.7 bug reports per 1,000 commits,
95% bootstrap CI [-1.4, -0.1]. Holm-adjusted p = 0.06. Deviation: sample of 6 instead of 40 (disclosed).
FIXTURE

mkdir -p 'paper'
cat > 'paper/manuscript.md' <<'FIXTURE'
# Type Hints and Bug-Report Rates in Python Projects
Abstract. We compare bug-report rates before and after type-hint adoption in six projects.
Introduction. Method. Results: median difference -0.7 (95% CI -1.4 to -0.1). Discussion. Limitations: n = 6.
Conclusion. References: S1, S2 (fixture corpus).
FIXTURE

mkdir -p '.apothem/plans/typed-python/_outputs'
cat > '.apothem/plans/typed-python/_outputs/review-report.md' <<'FIXTURE'
# Review Report
Verdict: major revision. Required revisions: HIGH enlarge the sample to the preregistered 40 projects;
MEDIUM report the per-project series; LOW add the data-availability statement.
FIXTURE

mkdir -p 'corpus'
cat > 'corpus/fixture-study-a.md' <<'FIXTURE'
Fixture study A (synthetic, for evaluation only). Twelve Python projects; type-related bug reports fell
after mypy adoption; total bug reports were not reported.
FIXTURE

mkdir -p 'corpus'
cat > 'corpus/fixture-study-b.md' <<'FIXTURE'
Fixture study B (synthetic, for evaluation only). Thirty projects; total bug-report rates showed no
significant change after adding type hints (difference -3%, CI includes zero).
FIXTURE

mkdir -p 'corpus'
cat > 'corpus/fixture-study-c.md' <<'FIXTURE'
Fixture study C (synthetic, for evaluation only). A survey of developer attitudes towards type hints;
no defect data.
FIXTURE
