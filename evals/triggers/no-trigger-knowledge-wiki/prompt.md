---
description: A near-miss request that knowledge-wiki must not pick up.
tags: [no-trigger, 'class:skill', 'component:knowledge-wiki']
expected_outcome: Claude does not invoke knowledge-wiki.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Summarise this abstract in two sentences, nothing needs to be saved: 'We compare retrieval-augmented and plain completion for code models under 3B parameters and find retrieval narrows the gap on repository-specific APIs.'
