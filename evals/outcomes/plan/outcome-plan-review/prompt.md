---
description: Review an existing suite and record scorecards in PLAN-NOTES.md.
tags: [outcome, 'pipeline:plan', 'component:plan-review']
expected_outcome: PLAN-NOTES.md gains a Review Scorecards section.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:plan-review .apothem/plans/notes-app/

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
