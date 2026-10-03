---
description: 'Effect of the always-on rule option-annotation: the same prompt and graders with the rule''s
  runtime text appended to the system prompt (off in this case). Plugin eval runs load no rules, so the
  pair isolates the rule''s effect.'
tags: [rule-effect, 'rule:option-annotation', 'arm:rule-off', rule-scoping-regression]
expected_outcome: One option carries a (Recommended) marker with a reason.
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, AskUserQuestion]
---

<!-- SPDX-License-Identifier: MIT -->

List three options for storing session data in a small Flask app, with the trade-offs of each.
