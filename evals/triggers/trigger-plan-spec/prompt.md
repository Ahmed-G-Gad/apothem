---
description: A request in plan-spec's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:plan-spec']
expected_outcome: Claude invokes the plan-spec command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Here are my rough notes for a feature. Turn them into a proper spec before we plan it: users want saved searches, an email alert when new results match, and a link to share a search.
