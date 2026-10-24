---
description: A request in architecture-review's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:architecture-review']
expected_outcome: Claude invokes the architecture-review command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Compare this repository with its design document in docs/design.md. Does the code respect the layer rules, and where do boundaries leak or components wire to each other wrongly? Give me ranked findings and change nothing.
