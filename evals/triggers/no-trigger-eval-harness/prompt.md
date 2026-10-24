---
description: A near-miss request that eval-harness must not pick up.
tags: [no-trigger, 'class:skill', 'component:eval-harness']
expected_outcome: Claude does not invoke eval-harness.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Why does fixing a random seed make an experiment repeatable? Two sentences.
