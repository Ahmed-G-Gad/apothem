---
description: A request in multi-source-research's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:multi-source-research']
expected_outcome: Claude invokes the multi-source-research skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Research how much energy it takes to train a large language model. Find the sources, cross-verify each claim against at least two independent ones, and give me a cited report with a confidence level per claim.
