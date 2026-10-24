---
description: A request in dev-toolkit's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:dev-toolkit']
expected_outcome: Claude invokes the dev-toolkit skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Our goal is to add multi-currency support to the billing module. Break it into independently shippable vertical slices, turn each slice into a tracked issue with acceptance criteria, and record the key decision in an ADR.
