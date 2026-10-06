---
description: 'Effect of the always-on rule definitiveness: the same prompt and graders with the rule''s
  runtime text appended to the system prompt (off in this case). Plugin eval runs load no rules, so the
  pair isolates the rule''s effect.'
tags: [rule-effect, 'rule:definitiveness', 'arm:rule-off', rule-scoping-regression]
expected_outcome: A definitive answer with no hedging vocabulary.
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, AskUserQuestion]
---

<!-- SPDX-License-Identifier: MIT -->

In three sentences, is this function thread-safe?

```python
counter = 0


def bump():
    global counter
    counter += 1
```
