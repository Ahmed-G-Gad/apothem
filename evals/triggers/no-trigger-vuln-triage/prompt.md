---
description: A near-miss request that vuln-triage must not pick up.
tags: [no-trigger, 'class:skill', 'component:vuln-triage']
expected_outcome: Claude does not invoke vuln-triage.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What does a CVSS base score of 9.8 mean? Two sentences.
