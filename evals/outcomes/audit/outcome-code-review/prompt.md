---
description: 'Run the code-review dimension on a small repository with one planted defect: A function
  that divides by len(values) without handling an empty list.'
tags: [outcome, 'pipeline:audit', 'component:code-review']
expected_outcome: A code-review-findings.md artifact, a reply that names the planted defect, and no source
  edits (the audit is report-only).
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:code-review .

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
