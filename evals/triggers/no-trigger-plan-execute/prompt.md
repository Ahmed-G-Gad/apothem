---
description: A near-miss request that plan-execute must not pick up.
tags: [no-trigger, 'class:command', 'component:plan-execute']
expected_outcome: Claude does not invoke plan-execute.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Explain what this line does: `xs = sorted(set(xs))`.
