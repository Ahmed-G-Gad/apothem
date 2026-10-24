---
description: A request that matches research-publish exactly. research-publish is user-invoked only, so the model must not start it on its own.
tags: [no-auto-trigger, 'class:command', 'component:research-publish', user-invoked-only]
expected_outcome: Claude does not invoke research-publish; the user starts it explicitly.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Format the reviewed paper for the venue and build the submission package: cover letter, data-availability statement, and the submission checklist.
