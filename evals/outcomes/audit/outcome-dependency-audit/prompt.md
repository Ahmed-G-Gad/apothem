---
description: 'Run the dependency-audit dimension on a small repository with one planted defect: An unpinned
  requests, a vulnerable pyyaml==5.3, an open-ended flask range.'
tags: [outcome, 'pipeline:audit', 'component:dependency-audit']
expected_outcome: A dependency-audit-findings.md artifact, a reply that names the planted defect, and
  no source edits (the audit is report-only).
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:dependency-audit .

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
