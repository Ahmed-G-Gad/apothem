---
description: A near-miss request that should not invoke perspectives.
tags: [no-trigger, 'class:skill', 'component:perspectives']
expected_outcome: Claude does not invoke perspectives.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

We need a database for the new inventory service: Postgres, MongoDB, or DynamoDB. Our weights are cost 40, query flexibility 35, and operational burden 25. Score each option against those weights and tell me which one wins.
