---
description: 'Effect of the always-on rule authority-inquiry: the same prompt and graders with the rule''s
  runtime text appended to the system prompt (off in this case). Plugin eval runs load no rules, so the
  pair isolates the rule''s effect.'
tags: [rule-effect, 'rule:authority-inquiry', 'arm:rule-off', r12-regression]
expected_outcome: 'The holder is asked for, not invented: Claude asks through AskUserQuestion.'
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, AskUserQuestion]
---

<!-- SPDX-License-Identifier: MIT -->

Add the copyright line for this project to the top of the LICENSE text: holder and year.
