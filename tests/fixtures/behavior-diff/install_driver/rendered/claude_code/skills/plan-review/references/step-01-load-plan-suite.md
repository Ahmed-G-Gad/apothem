<!-- SPDX-License-Identifier: MIT -->

### Step 1: Load Plan Suite

Deploy a Research Team (CM-25A) for parallel file extraction (structured summaries, not raw content — CM-25C return contract: max 500 tokens per agent; required fields: `status`, `summary`, `evidence`; on failure: `status=failed` with explicit reason and scope covered). If resuming: Session Start Protocol (CM-14) — including rules from `rules/*.md`.

Verify all mandatory files exist (including the `phases/` directory with phase folders). If missing → STOP, recommend `/plan-generate`. Load rules (`rules/*.md`) and relevant skills. If PROGRESS.md carries a Resumption Contract, use its convention anchors and critical-files manifest for efficient loading. Read ALL files — every phase file (`phases/**/PHASE.md`, recursing into sub-phase folders), every infrastructure file, every report (`phases/**/REPORT.md`). Locate the original prose (ask the user if not found; if unavailable, proceed consistency-only — skip Step 2).

**Pre-Audit Baseline.** Externalize declared counts, dependencies, decisions, artifacts (CM-24B). Build a complete registry of every element that must be verified (scoped to `--focus` dimensions when not `all`):

- Total phase count and file list
- Total task count per phase
- Total decision count and decision IDs
- All dependency edges (Phase X depends on Phase Y)
- All named outputs and their declared consumers
- All named inputs and their declared sources
- All naming conventions declared in the preamble
- All interface contracts between phases
- All verification assertions

This registry is the verification checklist. Every in-scope item is individually checked off during the applicable audit steps. Any in-scope item not checked off by Step 6 is an automatic finding.
