---
description: A request in test-authoring's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:test-authoring']
expected_outcome: Claude invokes the test-authoring skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Write behavior-first tests for normalize_phone in src/util/phone.py in arrange-act-assert form, covering the happy path, edge boundaries and failures. Only write the tests; leave the implementation alone.
