---
description: Build the submission package and the publication record.
tags: [outcome, 'pipeline:research', 'component:research-publish']
expected_outcome: _outputs/publication-record.md with the submission checklist outcome.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:research-publish --suite-name typed-python --venue workshop

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
