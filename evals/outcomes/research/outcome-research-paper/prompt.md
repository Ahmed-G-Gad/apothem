---
description: Assemble the manuscript and the reference record.
tags: [outcome, 'pipeline:research', 'component:research-paper']
expected_outcome: A manuscript under paper/ and the suite's paper attestation.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:research-paper --suite-name typed-python

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
