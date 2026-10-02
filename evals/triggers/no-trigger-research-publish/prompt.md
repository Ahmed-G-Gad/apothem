---
description: A near-miss request that research-publish must not pick up.
tags: [no-trigger, 'class:command', 'component:research-publish']
expected_outcome: Claude does not invoke research-publish.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

How do I publish a Python package to PyPI with twine?
