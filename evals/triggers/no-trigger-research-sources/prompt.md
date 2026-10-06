---
description: A near-miss request that research-sources must not pick up.
tags: [no-trigger, 'class:command', 'component:research-sources']
expected_outcome: Claude does not invoke research-sources.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Where is the source code of the requests library hosted?
