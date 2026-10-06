---
description: Produce the architectural design artifact for a suite.
tags: [outcome, 'pipeline:plan', 'component:plan-design']
expected_outcome: _inputs/design.md naming the components and their interfaces.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:plan-design .apothem/plans/notes-app/

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
