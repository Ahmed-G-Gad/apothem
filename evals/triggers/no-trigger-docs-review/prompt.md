---
description: A near-miss request that docs-review must not pick up.
tags: [no-trigger, 'class:command', 'component:docs-review']
expected_outcome: Claude does not invoke docs-review.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

When should a fenced code block in Markdown carry a language tag? Two sentences.
