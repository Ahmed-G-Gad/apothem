---
description: A near-miss request that plan-spec must not pick up.
tags: [no-trigger, 'class:command', 'component:plan-spec']
expected_outcome: Claude does not invoke plan-spec.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What does the spec field mean in a Kubernetes Deployment manifest?
