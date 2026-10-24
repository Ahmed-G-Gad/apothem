---
description: A request that matches plan-execute exactly. plan-execute is user-invoked only, so the model must not start it on its own.
tags: [no-auto-trigger, 'class:command', 'component:plan-execute', user-invoked-only]
expected_outcome: Claude does not invoke plan-execute; the user starts it explicitly.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Carry out phase 02 of the plan suite in .apothem/plans/search-revamp: implement its tasks, run the gates, and write the phase report.
