---
description: A request in eval's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:eval']
expected_outcome: Claude invokes the eval command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Run an evaluation campaign for our summarization prompt: load the labeled dataset in data/summaries.jsonl, score every output, and report the metrics per category plus any regressions against last week's baseline.
