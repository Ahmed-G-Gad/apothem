---
description: Generate a Master Plan Suite from an authored spec.
tags: [outcome, 'pipeline:plan', 'component:plan-generate']
expected_outcome: MASTER-PLAN.md and at least one phases/*/PHASE.md in the suite folder.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:plan-generate .apothem/plans/notes-app/_spec/spec.md

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
