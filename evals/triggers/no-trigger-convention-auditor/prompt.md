---
description: A near-miss request that should not be delegated to convention-auditor.
tags: [no-trigger, 'class:agent', 'component:convention-auditor']
expected_outcome: Claude does not delegate to convention-auditor.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Which naming style does PEP 8 recommend for module-level constants?
