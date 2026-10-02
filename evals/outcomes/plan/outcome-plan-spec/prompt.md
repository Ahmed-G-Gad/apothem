---
description: Refine raw requirements into a spec-grade _spec/spec.md for a named suite.
tags: [outcome, 'pipeline:plan', 'component:plan-spec']
expected_outcome: A spec at .apothem/plans/notes-app/_spec/spec.md that keeps every requirement, search
  included.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:plan-spec requirements.md --suite-name notes-app

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
