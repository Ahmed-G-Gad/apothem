---
description: A request in plan's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:plan']
expected_outcome: Claude invokes the plan command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Take this idea through the whole planning pipeline in one go, verifying each hand-off between stages: a command-line tool that syncs dotfiles across machines, encrypts secrets and has a dry-run mode.
