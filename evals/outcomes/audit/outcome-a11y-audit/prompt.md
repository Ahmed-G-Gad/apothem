---
description: 'Run the a11y-audit dimension on a small repository with one planted defect: An image without
  alt text, an unlabelled input, a clickable div.'
tags: [outcome, 'pipeline:audit', 'component:a11y-audit']
expected_outcome: A a11y-audit-findings.md artifact, a reply that names the planted defect, and no source
  edits (the audit is report-only).
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:a11y-audit .

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
