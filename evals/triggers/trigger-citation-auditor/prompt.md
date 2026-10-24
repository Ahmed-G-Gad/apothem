---
description: A task citation-auditor exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:citation-auditor']
expected_outcome: Claude delegates to the citation-auditor subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Before I submit, go through the 30 entries in references.bib of my draft. Tell me which ones are real papers with correct DOIs and years, and whether each paper actually says what my text cites it for.
