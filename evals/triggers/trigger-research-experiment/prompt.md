---
description: A request in research-experiment's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:research-experiment']
expected_outcome: Claude invokes the research-experiment command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Run the study exactly as preregistered and log every run with full provenance so someone else can reproduce it.
