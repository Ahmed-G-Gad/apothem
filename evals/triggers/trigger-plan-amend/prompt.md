---
description: A request in plan-amend's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:plan-amend']
expected_outcome: Claude invokes the plan-amend command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

The plan suite in .apothem/plans/payments-v2 has to change: the team dropped the Stripe migration. Revise the plan so the dependent phases and notes reflect that, without losing the decisions we already made.
