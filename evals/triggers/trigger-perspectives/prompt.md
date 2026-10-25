---
description: A task perspectives exists for, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:perspectives']
expected_outcome: Claude invokes the perspectives skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Our team is split on whether to open-source our internal build tooling. One camp expects outside contributors and goodwill; the other expects a leak of how we work and a support burden we cannot staff. I cannot tell who is right. Argue it out from the different sides, tell me where they really disagree, and say what you would do.
