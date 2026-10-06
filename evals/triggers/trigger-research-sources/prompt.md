---
description: A request in research-sources's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:research-sources']
expected_outcome: Claude invokes the research-sources command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Collect and screen the primary literature for our question on retrieval-augmented code completion and build the source ledger.
