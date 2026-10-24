---
description: A near-miss request that ui-design must not pick up.
tags: [no-trigger, 'class:skill', 'component:ui-design']
expected_outcome: Claude does not invoke ui-design.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

The signup form sends two requests when a user double-clicks the submit button, and the server creates duplicate accounts. Find where the second request comes from in the submit handler and explain the fix.
