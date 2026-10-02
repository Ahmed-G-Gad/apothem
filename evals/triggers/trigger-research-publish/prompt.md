---
description: A request in research-publish's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:research-publish']
expected_outcome: Claude invokes the research-publish command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Format the reviewed paper for the venue and build the submission package: cover letter, data-availability statement, and the submission checklist.
