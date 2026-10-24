---
description: A request in research-ideate's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:research-ideate']
expected_outcome: Claude invokes the research-ideate command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

I work on automated program repair but I have no research question yet. Scan the gaps and the hypotheses that were already refuted, and give me a ranked list of falsifiable questions worth studying.
