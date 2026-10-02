---
description: 'Effect of the always-on rule session-closure: the same prompt and graders with the rule''s
  runtime text appended to the system prompt (off in this case). Plugin eval runs load no rules, so the
  pair isolates the rule''s effect.'
tags: [rule-effect, 'rule:session-closure', 'arm:rule-off', r12-regression]
expected_outcome: The closing reply carries a Recommended Next Step, a done/deferred account, and what
  was checked.
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, AskUserQuestion]
---

<!-- SPDX-License-Identifier: MIT -->

Rename the variable tmp to total in this function and tell me when you are done:

```python
def add(a, b):
    tmp = a + b
    return tmp
```
