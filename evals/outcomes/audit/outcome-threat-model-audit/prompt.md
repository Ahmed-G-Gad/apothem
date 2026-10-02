---
description: 'Run the threat-model-audit dimension on a small repository with one planted defect: A user-supplied
  file name joined to the upload directory (path traversal).'
tags: [outcome, 'pipeline:audit', 'component:threat-model-audit']
expected_outcome: A threat-model-audit-findings.md artifact, a reply that names the planted defect, and
  no source edits (the audit is report-only).
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:threat-model-audit .

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
