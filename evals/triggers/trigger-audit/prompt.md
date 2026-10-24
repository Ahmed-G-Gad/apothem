---
description: A request in audit's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:audit']
expected_outcome: Claude invokes the audit command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Run every kind of review we have over this whole repository in one pass (code quality, security, dependencies, release pipeline, performance, accessibility, docs) and give me one verified, severity-ranked report. Do not fix anything.
