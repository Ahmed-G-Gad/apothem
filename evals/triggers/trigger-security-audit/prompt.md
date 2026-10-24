---
description: A request in security-audit's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:security-audit']
expected_outcome: Claude invokes the security-audit command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Run a full security audit of this repository: committed secrets, injection, unsafe deserialization, path traversal and vulnerable dependencies. Write severity-ranked findings with a remediation recommendation for each, and fix nothing.
