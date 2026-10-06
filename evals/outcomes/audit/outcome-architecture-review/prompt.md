---
description: 'Run the architecture-review dimension on a small repository with one planted defect: The
  data layer imports the UI layer and the UI imports the data layer (a cycle).'
tags: [outcome, 'pipeline:audit', 'component:architecture-review']
expected_outcome: A architecture-review-findings.md artifact, a reply that names the planted defect, and
  no source edits (the audit is report-only).
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:architecture-review .

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
