---
description: A request in docs-review's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:docs-review']
expected_outcome: Claude invokes the docs-review command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Review the documentation pages under docs for unclear prose, broken links, code blocks without a language tag and public functions that have no documentation. Report per page and do not rewrite them.
