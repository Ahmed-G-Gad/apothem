---
description: A request in surgical-guard's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:surgical-guard']
expected_outcome: Claude invokes the surgical-guard skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Make a minimal, anchor-bounded change in config/settings.py: raise the default timeout from 30 to 60 seconds and touch nothing else. Then review only your own diff for swallowed errors, hollow tests and docs drift.
