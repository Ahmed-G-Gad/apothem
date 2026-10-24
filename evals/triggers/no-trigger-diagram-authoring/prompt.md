---
description: A near-miss request that diagram-authoring must not pick up.
tags: [no-trigger, 'class:skill', 'component:diagram-authoring']
expected_outcome: Claude does not invoke diagram-authoring.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is the difference between a sequence diagram and a flowchart? Two sentences.
