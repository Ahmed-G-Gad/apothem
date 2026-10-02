---
description: 'Execute one phase: implement its tasks and write the phase report.'
tags: [outcome, 'pipeline:plan', 'component:plan-execute']
expected_outcome: notes_app/search.py exists and phases/02-search/REPORT.md records the phase.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:plan-execute .apothem/plans/notes-app/ 02

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
