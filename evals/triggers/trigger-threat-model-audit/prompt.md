---
description: A request in threat-model-audit's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:threat-model-audit']
expected_outcome: Claude invokes the threat-model-audit command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Threat model this repository: apply STRIDE per element across the trust boundaries, classify the threat actors, and rate the residual risk. Report only, no edits.
