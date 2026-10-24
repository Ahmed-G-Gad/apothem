---
description: A request in projectify's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:projectify']
expected_outcome: Claude invokes the projectify command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Set up a custom assistant for our support team. Ask me what you need, then write its description, its instructions and its knowledge files, keeping the knowledge files within the platform's context budget.
