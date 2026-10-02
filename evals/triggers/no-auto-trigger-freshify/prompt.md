---
description: A request that matches freshify exactly. freshify is user-invoked only (decision D-12), so
  the model must not start it on its own.
tags: [no-auto-trigger, 'class:command', 'component:freshify', d12-user-invoked]
expected_outcome: Claude does not invoke freshify; the user starts it explicitly.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Clean this repository up for release: purge the caches and stale artifacts, strip the legacy notes from the docs, and normalize the file names.
