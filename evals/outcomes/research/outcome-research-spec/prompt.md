---
description: Frame the question into falsifiable hypotheses with null forms.
tags: [outcome, 'pipeline:research', 'component:research-spec']
expected_outcome: _spec/research-spec.md with hypotheses and a null hypothesis.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:research-spec question.md --suite-name typed-python

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
