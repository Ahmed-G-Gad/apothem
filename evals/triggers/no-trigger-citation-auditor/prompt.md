---
description: A near-miss request that should not be delegated to citation-auditor.
tags: [no-trigger, 'class:agent', 'component:citation-auditor']
expected_outcome: Claude does not delegate to citation-auditor.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Convert these three references from APA to IEEE style and keep the order as it is.
