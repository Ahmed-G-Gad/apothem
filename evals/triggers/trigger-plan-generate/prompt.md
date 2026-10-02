---
description: A request in plan-generate's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:plan-generate']
expected_outcome: Claude invokes the plan-generate command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Turn these requirements into a full phased implementation plan: a CLI that syncs dotfiles across machines, encrypts secrets, and has a dry-run mode.
