---
description: A request that matches freshify exactly. freshify is user-invoked only (a maintainer decision), so
  the model must not start it on its own.
tags: [no-auto-trigger, 'class:command', 'component:freshify', user-invoked-only]
expected_outcome: Claude does not invoke freshify; the user starts it explicitly.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Clean this repository up for release: purge the caches and stale artifacts, strip the legacy notes from the docs, and normalize the file names.
