---
description: A near-miss request that ux-review must not pick up.
tags: [no-trigger, 'class:command', 'component:ux-review']
expected_outcome: Claude does not invoke ux-review.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is the usual convention for a command-line tool's exit status on success versus failure? Two sentences.
