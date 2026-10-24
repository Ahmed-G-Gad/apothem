---
description: A request in test-suite's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:test-suite']
expected_outcome: Claude invokes the test-suite command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Cover this repository with behavior-first tests: write them, run them, triage every failure, and show me the coverage gaps on the critical paths.
