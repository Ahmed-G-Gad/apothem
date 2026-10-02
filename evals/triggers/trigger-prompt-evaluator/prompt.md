---
description: A task prompt-evaluator exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:prompt-evaluator']
expected_outcome: Claude delegates to the prompt-evaluator subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Score these three model outputs against my rubric (accurate, cites a source, under 50 words) and give me the pass rate per criterion: 1) 'Paris is the capital of France.' 2) 'Paris, per the CIA World Factbook.' 3) 'It is Lyon.'
