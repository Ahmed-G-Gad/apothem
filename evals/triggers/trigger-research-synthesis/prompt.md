---
description: A request in research-synthesis's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:research-synthesis']
expected_outcome: Claude invokes the research-synthesis command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Synthesize the sources we collected into a state-of-the-art map and tell me where the research gap is.
