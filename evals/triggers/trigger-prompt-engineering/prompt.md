---
description: A request in prompt-engineering's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:prompt-engineering']
expected_outcome: Claude invokes the prompt-engineering skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Design a system prompt for a refund-triage assistant and validate it against happy-path, edge and adversarial test cases. Give me the prompt together with its eval set.
