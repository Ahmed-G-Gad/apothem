---
description: A request in knowledge-wiki's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:knowledge-wiki']
expected_outcome: Claude invokes the knowledge-wiki skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Our team keeps a Markdown wiki under docs/kb with an index page and a change log. Add the paper at docs/papers/retrieval-small-models.pdf to it for the question 'does retrieval help small code models', and record which claims were actually read.
