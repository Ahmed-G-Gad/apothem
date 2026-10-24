---
description: A request in perf-audit's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:perf-audit']
expected_outcome: Claude invokes the perf-audit command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Audit this Apothem checkout's performance against its per-class budgets using the benchmark drivers, and tell me which paths exceed their budget, ranked high, medium or low. Measure only; do not optimize anything.
