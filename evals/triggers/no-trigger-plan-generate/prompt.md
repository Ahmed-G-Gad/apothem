---
description: A near-miss request that plan-generate must not pick up.
tags: [no-trigger, 'class:command', 'component:plan-generate']
expected_outcome: Claude does not invoke plan-generate.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Give me three name ideas for a dotfiles sync CLI.
