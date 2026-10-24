---
description: A near-miss request that perf-audit must not pick up.
tags: [no-trigger, 'class:command', 'component:perf-audit']
expected_outcome: Claude does not invoke perf-audit.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is the difference between latency and throughput? Two sentences.
