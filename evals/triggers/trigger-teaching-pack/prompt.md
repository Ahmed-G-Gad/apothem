---
description: A task teaching-pack exists for, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:teaching-pack']
expected_outcome: Claude invokes the teaching-pack skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

I run a reading group for second-year students and next week's paper is saved at papers/consensus-under-failures.md. Please turn it into something I can teach from: learning goals, a lesson plan that goes section by section, a plain-steps walk-through of its main formulas, a few worked examples, a quiz with an answer key, and a glossary.
