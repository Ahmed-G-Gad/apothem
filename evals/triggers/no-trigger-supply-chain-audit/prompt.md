---
description: A near-miss request that supply-chain-audit must not pick up.
tags: [no-trigger, 'class:command', 'component:supply-chain-audit']
expected_outcome: Claude does not invoke supply-chain-audit.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is an SBOM and what does it contain? Two sentences.
