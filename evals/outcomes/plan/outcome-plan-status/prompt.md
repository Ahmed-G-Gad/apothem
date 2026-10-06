---
description: Report suite progress without writing anything.
tags: [outcome, 'pipeline:plan', 'component:plan-status']
expected_outcome: The reply names phase 02 (search) as next; no file is written or edited.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:plan-status .apothem/plans/notes-app/

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
