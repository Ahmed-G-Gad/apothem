<!-- SPDX-License-Identifier: MIT -->

# Issue Lifecycle: Stage Details

Supporting detail for `SKILL.md`. Read the section for the stage being run; the last five sections serve `publish` and the reporter request.

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
- Leave pushing, the pull request, and the issue comment to the operator unless asked. The opt-in `publish` stage below is the path for pushing and the draft pull request.

## Reporter request

Draft one only after an honest attempt: the reproducing test was written and run, and either it passed, or the symptom depends on facts the report omits. The same request serves a defect recorded as `not reproducible in tests` when the missing facts are what would let someone else reproduce it.

| Heading | Ask for | Skip when |
|---------|---------|-----------|
| Version | Release or commit, platform, and the configuration that touches the failing path | The report names all three |
| Steps | The shortest numbered sequence that triggers it, from a clean start | The report has numbered steps that were run and behaved differently |
| Expected versus actual | What they expected and what happened instead | The report states both |
| Logs | The full message or output, with the command that produced it | The report quotes the complete output |

Template. Address the reporter by handle only when the thread shows it.

```text
Thanks for the report.

We tried to reproduce this on <version and platform> by <one line on what was run>, and saw <result>, so we cannot yet see the problem you describe.

Could you add the following?

1. <heading>: <the specific missing item>
2. <heading>: <the specific missing item>

A small example that fails on your side is the most useful thing you can share. Please remove tokens, passwords, and personal data before posting.
```

Keep it under about twelve lines. Ask for nothing the report already gives, and never ask for credentials or private data. The stage record keeps the draft with the line `not posted`.

## Publish pre-flight

- The fix is on `fix/<n>`, or the plan creates that branch with the fix intact. It is never committed on the default branch or a shared branch.
- The reproducing test and the wider suite were run in this stage and the output is kept. A pass from an earlier stage is context, not evidence.
- `git status` and `git diff --stat` show only the fix and its tests: no editor files, build output, local configuration, or secrets.
- The remote and base branch come from discovery (`git remote -v`, the tracker's default branch). In a fork workflow, ask which remote receives the push and which repository the pull request targets.
- A search of open pull requests by branch and by `#<n>` finds none already covering the issue. When one exists, report it and stop.
- The tracker CLI answers and is signed in. When it does not, fall back to the host's tracker connector if the session has one, found by capability and not by name. Otherwise print the commands and the pull request text for the operator and stop. Never sign in, create tokens, or read stored credentials.

## Pull request title and body

Title: the host's commit style, discovered per `rules/host-discovery.md`; the default is `fix(<scope>): <subject>`, imperative, under 72 characters. Body:

```text
## Summary
<The defect as users see it, then what this change does, in two sentences.>

## Cause
<The root cause, with the file or behaviour that shows it.>

## Change
- <What changed, by area.>

## Tests
- <command>: <observed result>
- <test path> fails without this change and passes with it.

Refs #<n>
```

The body states what happened and what was run. It carries no plan paths, no phase or ticket codes from planning, and no statement of which tool wrote it; authorship is the operator's own per `rules/production-ready-prs.md`.

## Closing-keyword scan

Scan the title, the body, and every commit message in the range before showing them. A closing keyword attached to an issue reference closes the issue when the pull request merges. Look for `close`, `closes`, `closed`, `fix`, `fixes`, `fixed`, `resolve`, `resolves`, `resolved` (any case, with or without a colon) followed by `#<n>`, an `owner/repo#<n>` reference, or an issue URL, and for the host's own keyword list when it documents a longer one. Rewrite a hit as `Refs #<n>`. The word `fix` in a Conventional Commits type, as in `fix(<scope>): ...`, is not a hit because no issue reference follows it. Report the scan result in the stage record even when it found nothing. An operator who wants auto-close adds the keyword by hand after the pull request exists.

## Shell-safe text

Issue text, logs, and titles come from other people and may contain `$(...)`, backticks, quotes, or newlines. Never splice them into a command line.

- Write the pull request body to a temporary file or pipe it on standard input, and pass `--body-file <path>` (or `--body-file -`). Use a quoted here-document (`<<'EOF'`) in a POSIX shell, or a single-quoted here-string in PowerShell, so nothing expands.
- Commit with `git commit -F <file>`, not `-m "<text>"`, when the message holds anything beyond one plain line.
- Pass the title as a single quoted argument only after checking it holds no quote characters or expansion syntax; otherwise use the file form the CLI offers.
- Delete the temporary file after the step. It is not part of the change-set.

## Publish gates

One structured question per external step, each with its own answer. The plan gate covers local steps only; the push and open gates leave the machine. The `Other` option is implicit. These shapes follow `rules/interactive-questions-canonical-shapes.md` §2.

```yaml
question:     Create the branch and commit these files as planned?
header:       Publish plan
multiSelect:  false
options:
  - label:    Commit as planned
    description:
      rationale:         Commits only the listed files on `fix/<n>`; nothing leaves the machine.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required.
  - label:    Revise the plan
    description:
      rationale:         Returns to the plan to change the files, message, title, or body before any commit.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required.
  - label:    Stop here
    description:
      rationale:         Ends the stage with no branch created and nothing committed.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required.
```

```yaml
question:     Push `fix/<n>` to `<remote>` now?
header:       Push
multiSelect:  false
options:
  - label:    Push
    description:
      rationale:         Publishes `fix/<n>` to `<remote>` without force and sets the upstream.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required.
  - label:    Not yet
    description:
      rationale:         Leaves the commits local; the push can be run later with `publish`.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required.
```

```yaml
question:     Open this draft pull request against `<base>`?
header:       Open draft
multiSelect:  false
options:
  - label:    Open draft
    description:
      rationale:         Creates a draft pull request with the title and body shown, referencing the issue without closing it.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required.
  - label:    Edit text
    description:
      rationale:         Returns to the title and body for changes before anything is created.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required.
  - label:    Not yet
    description:
      rationale:         Leaves the pushed branch as it is; no pull request exists.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required.
```

A silent or unclear answer is a no. After a no, report which local steps are already done.
