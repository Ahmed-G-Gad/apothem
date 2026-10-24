---
description: A request in source-synthesis's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:source-synthesis']
expected_outcome: Claude invokes the source-synthesis skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Here are three reports on remote work and productivity: reports/a.md, reports/b.md and reports/c.md. Combine them into one cited synthesis that separates what they agree on from what they contest.
