---
description: A near-miss request that github-deploy-fresh must not pick up.
tags: [no-trigger, 'class:command', 'component:github-deploy-fresh', d12-user-invoked]
expected_outcome: Claude does not invoke github-deploy-fresh.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

How do I create a GitHub release from the command line?
