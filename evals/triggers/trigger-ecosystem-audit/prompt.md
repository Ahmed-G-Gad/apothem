---
description: A request in ecosystem-audit's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:ecosystem-audit']
expected_outcome: Claude invokes the ecosystem-audit skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Audit the whole apothem configuration tree for drift, orphaned files, dangling cross-references and invalid frontmatter. Only report what you find; do not fix anything.
