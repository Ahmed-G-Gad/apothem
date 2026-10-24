---
description: A request in eval-harness's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:eval-harness']
expected_outcome: Claude invokes the eval-harness skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Set up a repeatable way to compare two candidate models on our labeled ticket-routing task: a versioned labeled dataset, a scorer, a runner, and a report with pass rate, confidence interval and regressions, so anyone re-running it gets the same number.
