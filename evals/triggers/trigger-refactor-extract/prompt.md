---
description: A request in refactor-extract's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:refactor-extract']
expected_outcome: Claude invokes the refactor-extract skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Pull parse_header out of src/net/http.py into its own module: first write down what it observably does, then re-derive it clean from that description, then check that nothing regressed.
