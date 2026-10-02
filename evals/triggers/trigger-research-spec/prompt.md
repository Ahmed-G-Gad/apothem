---
description: A request in research-spec's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:research-spec']
expected_outcome: Claude invokes the research-spec command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Frame this research question properly: does adding type hints to a Python codebase reduce bug reports? I need falsifiable hypotheses, the scope, and inclusion and exclusion criteria.
