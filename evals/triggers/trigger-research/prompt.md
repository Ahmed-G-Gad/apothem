---
description: A request in research's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:research']
expected_outcome: Claude invokes the research command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Take this idea all the way from nothing to a peer-reviewed paper, checking each hand-off between stages: does spaced repetition improve how well people retain programming syntax?
