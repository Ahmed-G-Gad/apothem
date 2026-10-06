---
description: A near-miss request that research-review must not pick up.
tags: [no-trigger, 'class:command', 'component:research-review']
expected_outcome: Claude does not invoke research-review.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Check this pull request description for typos: 'Adds retry logic to the uplaoder.'
