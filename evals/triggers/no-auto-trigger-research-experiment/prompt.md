---
description: A request that matches research-experiment exactly. research-experiment is user-invoked only, so the model must not start it on its own.
tags: [no-auto-trigger, 'class:command', 'component:research-experiment', user-invoked-only]
expected_outcome: Claude does not invoke research-experiment; the user starts it explicitly.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Run the study exactly as preregistered and log every run with full provenance so someone else can reproduce it.
