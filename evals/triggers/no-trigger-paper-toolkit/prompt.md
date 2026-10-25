---
description: A near-miss request that paper-toolkit must not pick up.
tags: [no-trigger, 'class:skill', 'component:paper-toolkit']
expected_outcome: Claude does not invoke paper-toolkit.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

The file docs/refs.bib lists 40 references for my draft. Check that every DOI points to a real paper, and that each cited paper actually says what my sentence attributes to it.
