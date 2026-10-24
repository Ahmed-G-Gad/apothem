---
description: A request in ux-review's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:ux-review']
expected_outcome: Claude invokes the ux-review command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Review this command-line tool from a first-time user's view: the help output, error messages, install flow and how easy the docs are to find. Give me severity-ranked findings and change nothing.
