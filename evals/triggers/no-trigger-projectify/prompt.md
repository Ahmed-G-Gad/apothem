---
description: A near-miss request that projectify must not pick up.
tags: [no-trigger, 'class:command', 'component:projectify']
expected_outcome: Claude does not invoke projectify.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is a system prompt, and how does it differ from a user message? Two sentences.
