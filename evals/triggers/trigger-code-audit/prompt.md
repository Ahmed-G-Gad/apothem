---
description: A request in code-audit's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:code-audit']
expected_outcome: Claude invokes the code-audit command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Audit this codebase as a whole for cross-file problems: hidden coupling between modules, dead code, duplicated logic and missing type hints. Report only, no edits.
