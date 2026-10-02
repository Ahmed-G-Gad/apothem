---
description: 'Effect of the always-on rule freshness-facade: the same prompt and graders with the rule''s
  runtime text appended to the system prompt (off in this case). Plugin eval runs load no rules, so the
  pair isolates the rule''s effect.'
tags: [rule-effect, 'rule:freshness-facade', 'arm:rule-off', r12-regression]
expected_outcome: Current-version prose with no legacy, deprecated, coming-soon or placeholder narrative.
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, AskUserQuestion]
---

<!-- SPDX-License-Identifier: MIT -->

Write a two-paragraph README introduction for tidy, a CLI that formats YAML files. This is the project's first public release.
