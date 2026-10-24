---
description: A near-miss request that audit must not pick up.
tags: [no-trigger, 'class:command', 'component:audit']
expected_outcome: Claude does not invoke audit.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Which kinds of review does a typical pre-release checklist cover? A short bulleted list from general knowledge is enough.
