---
description: A request in incident-runbook's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:incident-runbook']
expected_outcome: Claude invokes the incident-runbook skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Write a runbook for when the payments queue backs up: the trigger, diagnosis, action, verification and rollback sections, with a rollback for every action.
