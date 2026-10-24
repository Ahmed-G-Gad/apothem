---
description: A near-miss request that incident-runbook must not pick up.
tags: [no-trigger, 'class:skill', 'component:incident-runbook']
expected_outcome: Claude does not invoke incident-runbook.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What should a blameless post-mortem contain? A short list.
