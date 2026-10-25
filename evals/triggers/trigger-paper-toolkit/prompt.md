---
description: A suite-free paper-comparison request in paper-toolkit's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:paper-toolkit']
expected_outcome: Claude invokes the paper-toolkit skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

I have three papers on retrieval for small code models in papers/ (rag-code.pdf, small-lm-retrieval.pdf, repo-context.pdf). Two of them report exact-match scores on what looks like the same benchmark, but I suspect the numbers are not measured the same way. Tell me whether the scores can be put side by side, and which paper I should cite for the claim that retrieval helps small models.
