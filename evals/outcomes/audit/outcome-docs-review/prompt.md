---
description: 'Run the docs-review dimension on a small repository with one planted defect: The README
  documents a --verbose flag the CLI does not have.'
tags: [outcome, 'pipeline:audit', 'component:docs-review']
expected_outcome: A docs-review-findings.md artifact, a reply that names the planted defect, and no source
  edits (the audit is report-only).
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:docs-review .

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
