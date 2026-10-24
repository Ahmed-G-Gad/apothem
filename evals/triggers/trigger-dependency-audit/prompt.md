---
description: A request in dependency-audit's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:dependency-audit']
expected_outcome: Claude invokes the dependency-audit command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Go through every direct and transitive dependency of this repository and report known CVEs, license conflicts with our MIT license, deprecated packages and loose version pins, ranked per dependency.
