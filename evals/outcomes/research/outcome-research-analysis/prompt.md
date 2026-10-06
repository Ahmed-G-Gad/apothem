---
description: Run the preregistered analysis with effect sizes and intervals.
tags: [outcome, 'pipeline:research', 'component:research-analysis']
expected_outcome: _outputs/analysis.md reporting an effect size with a confidence interval.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:research-analysis --suite-name typed-python

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
