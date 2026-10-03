---
description: 'Effect of the always-on rule interactive-questions: the same prompt and graders with the
  rule''s runtime text appended to the system prompt (off in this case). Plugin eval runs load no rules,
  so the pair isolates the rule''s effect.'
tags: [rule-effect, 'rule:interactive-questions', 'arm:rule-off', rule-scoping-regression]
expected_outcome: The ambiguity (which database, where, which schema) is routed through the AskUserQuestion
  tool.
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, AskUserQuestion]
---

<!-- SPDX-License-Identifier: MIT -->

Set up the database for this service.
