<!-- SPDX-License-Identifier: MIT -->

# Issue Lifecycle: Stage Details

Supporting detail for `SKILL.md`. Read the section for the stage being run.

## Issue draft layout

Use the repository's own template when one fits. When none exists, use this order:

1. **Summary** - one sentence naming the symptom.
2. **Observed** - what happens, with the exact message or output.
3. **Expected** - what should happen and why.
4. **Steps** - the shortest sequence that triggers it, numbered.
5. **Environment** - versions, platform, configuration. Write `unknown` for anything not confirmed.
6. **Evidence** - logs, stack traces, links supplied by the operator.

## Duplicate search

Search by the error text, by the affected command or module, and by the user-visible symptom. Include closed issues: a closed match may show a regression or a rejected request. For each near match record the number, its state, and one line on why it is or is not the same problem.

## Sizing signals

| Signal | Pushes toward |
|--------|---------------|
| Fix fits in one function and one test | `small` |
| Public flag, field, or output format changes | `medium` or `large` |
| Docs or generated reference pages must change | at least `medium` |
| Stored data or a schema needs migrating | `large` |
| Stack trace ends inside installed third-party code | `dependency-rooted` |
| The behaviour differs across platforms or runtime versions | check `dependency-rooted` first |
| Two plausible designs exist and neither is documented | `large` |

State the largest unknown even when the class looks clear; it is the part most likely to move the class.

## Repro checkpoint

- Branch: `repro/<n>`. The branch holds the test commit and nothing else.
- Commit subject: `test(<scope>): reproduce #<n>, expected to fail`. The body gives the command that runs the test and the failure line observed.
- A valid reproduction fails on the assertion that states the defect. An import error, a missing fixture, or a timeout caused by the test itself is not a reproduction; fix the test first.
- A defect that needs a platform, network, or timing condition the test cannot control is recorded as `not reproducible in tests` with the manual steps; do not commit a test that passes or flakes.

## Ownership evidence

Ours: the faulty line is in this repository, or the repository calls a dependency against its documented contract. Theirs: the same input fails against the dependency alone, outside this repository's code. Cite the minimal call that shows it and the version tested. When a newer release is available, check whether it already contains the fix before offering a workaround.

## Option table

Present options in this shape and mark one recommended:

| Option | What changes | Risk | Reversible | Upkeep |
|--------|--------------|------|------------|--------|
| A | Short description | Low, medium, or high with a reason | Yes or no | Who owns it afterwards |

For a dependency-rooted defect, cover at least: a local workaround that can be removed later, a version change, and an upstream report. The upstream report is drafted using the same layout as the issue draft and handed to the operator.

## Fix branch and references

- Branch `fix/<n>` starts from the `repro/<n>` tip so the failing test is part of the history.
- The fix commit message uses `fix(<scope>): <subject>` and, in the body, `Refs #<n>`.
- Closing keywords (those that close an issue on merge) are used only on the operator's instruction.
- Leave pushing, the pull request, and the issue comment to the operator unless asked.
