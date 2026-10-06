---
description: Peer-review the manuscript and list required revisions.
tags: [outcome, 'pipeline:research', 'component:research-review']
expected_outcome: _outputs/review-report.md with a required-revision list.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:research-review --suite-name typed-python

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
