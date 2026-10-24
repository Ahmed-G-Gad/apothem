---
description: A request in a11y-audit's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:a11y-audit']
expected_outcome: Claude invokes the a11y-audit command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Check the pages of our staging site for WCAG 2.2 AA problems: keyboard traps, missing form labels and low contrast. Rank what you find per page, and do not fix anything.
