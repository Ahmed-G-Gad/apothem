---
description: A near-miss request that a11y-audit must not pick up.
tags: [no-trigger, 'class:command', 'component:a11y-audit']
expected_outcome: Claude does not invoke a11y-audit.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What contrast ratio does WCAG 2.2 AA require for normal body text?
