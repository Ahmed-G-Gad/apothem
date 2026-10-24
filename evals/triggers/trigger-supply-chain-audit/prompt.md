---
description: A request in supply-chain-audit's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:supply-chain-audit']
expected_outcome: Claude invokes the supply-chain-audit command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Audit our release pipeline: is build provenance recorded, are artifacts signed, is the SBOM complete, and are CI actions pinned to commit hashes and run with minimal permissions? Report only.
