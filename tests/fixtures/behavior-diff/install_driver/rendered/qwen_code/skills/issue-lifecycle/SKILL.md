---
name: "issue-lifecycle"
version: "0.1.0"
updated: "2026-10-24"
description: "Takes a reported defect from issue to fix, one stage per run. Use for 'create an issue', 'size this issue', 'reproduce this bug', 'fix issue 123', 'ask the reporter for details' or 'open a draft PR'. Manual only; posts nothing unasked. Debug loops go to dev-toolkit, advisories to vuln-triage."
archetype: "engineering-template"
userInvocable: true
argument-hint: "[create|size|reproduce|fix|publish] [issue number or description]"
disable-model-invocation: true
allowedTools:
  - "Read"
  - "Glob"
  - "Grep"
  - "Bash(git status *)"
  - "Bash(git log *)"
  - "Bash(git diff *)"
  - "Bash(git show *)"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Take a reported problem from issue to fix, leaving evidence at every step: a reviewed issue text, a sizing note with reasons, a failing test that proves the defect, and a fix that turns that test green. The skill runs one stage per invocation so the operator can inspect the result before the next stage starts. Two additions close the loop without leaving the operator's control: a drafted request to the reporter when the defect cannot be reproduced, and an opt-in `publish` stage that opens a draft pull request after confirmation of each external step.

## Detection Signal

The operator asks to `create an issue`, `size this issue`, `reproduce this bug`, `write a repro test`, `fix issue <n>`, `ask the reporter for details`, or `open a draft PR for #<n>`, or hands over a defect report and asks for it to be worked through.

**Falsifiable counter-signal.** A one-line change the operator has already located, a repository-wide bug hunt, or a request to triage a security advisory is NOT a match; those go to a direct edit, a scanner, and `skills/vuln-triage/SKILL.md`. Marking a pull request ready for review, merging it, or closing the issue is not a match either; the skill stops at a draft.

## Non-Goals

- **Not a debugger.** Root-cause isolation and red-green mechanics belong to `skills/dev-toolkit/SKILL.md`; this skill calls that loop and records its outcome.
- **Not an issue publisher.** It drafts text. The operator files it, or says in this conversation to file it. The reporter request is always handed over for the operator to post; the skill never posts it.
- **Not a release step.** It never merges, marks a pull request ready for review, or closes an issue. It pushes and opens a draft pull request only in the opt-in `publish` stage, after the operator confirms each external step.

## Workflow

Pick the stage from the first argument, or from the request. When the stage is unclear, ask. Discover the issue tracker, reference syntax, and test runner per `rules/host-discovery.md`; never assume them. Branches are `repro/<n>` and `fix/<n>` unless the host documents another scheme. Stage detail and message formats are in `references/stage-details.md`. `publish` runs only when named; no other stage continues into it. When `reproduce` cannot observe the reported failure, or the report lacks what a reproduction needs, use the reporter-request side path after stage 5.

### Stage 1: create

1. Read the repository's issue templates and contribution guide; pick the template that fits the report.
2. Search open and closed issues for the same symptom with at least two phrasings. Show the closest matches. When one matches, stop and offer to add evidence to it instead.
3. Draft the issue in the chosen template: observed behaviour, expected behaviour, minimal steps, environment, and the evidence the operator supplied. Mark anything not known as `unknown`; invent no versions, logs, or steps.
4. Present the draft. Nothing is filed until the operator approves the exact text.

### Stage 2: size

Read-only. Read the issue, then the code it touches, and classify:

| Class | Meaning |
|-------|---------|
| `small` | One module, no interface change, test locality obvious |
| `medium` | Several modules or one interface change; migration or doc updates follow |
| `large` | Cross-cutting, schema or protocol change, or needs a design decision first |
| `dependency-rooted` | The defect originates in a third-party package or the platform |

Report the class, the files that would change, the reasoning in two to four sentences, and the largest unknown. Change nothing.

### Stage 3: reproduce

1. Check `git status`. When unrelated uncommitted changes exist, stop and ask the operator how to proceed. Otherwise create `repro/<n>` from the default branch, where `<n>` is the issue number.
2. Delegate to `skills/dev-toolkit/SKILL.md` (`--mode tdd`) to write the smallest test that fails for the reported reason.
3. Run it and observe the failure. Check that the failure message matches the reported symptom and not a typo, import error, or fixture problem.
4. Commit only the test, as its own commit. The subject states that the test is expected to fail, for example `test(<scope>): reproduce #<n>, expected to fail`. Leave it unpushed.

### Stage 4: fix

1. Require the `repro/<n>` checkpoint. When it is missing, run `reproduce` first, or record the operator's decision to proceed without one. Then decide ownership with evidence: does the defect live in this repository's code, or in a dependency or the platform? Cite the file, version, or upstream behaviour that shows it.
2. Offer two or three options, each with its trade-offs (risk, size, reversibility, who maintains it afterwards). For a dependency-rooted defect the options normally span a local workaround, a version change (see `skills/dependency-upgrade/SKILL.md`), and an upstream report; draft the report for the operator and do not file it. Mark one option as recommended and ask the operator to choose.
3. Create `fix/<n>` from the reproducing commit, implement the chosen option, and rerun the reproducing test until it passes, then the wider suite.
4. Reference the issue as related (`Refs #<n>`, or the host's equivalent). Use a closing keyword only when the operator asks for auto-close.

### Stage 5: publish (opt-in)

Runs only when the operator names it, or asks by name to push the fix or open a pull request. `fix` never continues into it; it only offers. Every external step has its own structured-inquiry gate (question shapes in the reference). An answer to one gate never covers another, and an answer from an earlier invocation never carries over.

1. Pre-flight, read-only. Confirm the fix is on `fix/<n>`; when that branch is absent, plan to create it from the current state with the fix intact, and never commit on the default branch. Rerun the reproducing test and the wider suite now and keep the output. Confirm `git diff --stat` shows only the fix and its tests, the remote and base branch are discovered, no open pull request already covers the issue, and the tracker CLI is signed in. On any failure stop and report. With no CLI or sign-in, hand over the exact commands and text, and handle no credentials.
2. Prepare the text: commit message, pull request title, and body (template in the reference). The body references the issue as related with `Refs #<n>` and carries no closing keyword. Scan title, body, and commit messages for closing keywords, plan-internal references, and tool attribution, and rewrite before showing anything.
3. **Gate 1, plan.** Show the branch, files, commit message, remote, base, and the title and body in full. On approval, create the branch if the plan says so and commit only those files, never a blanket add. Both steps are local.
4. **Gate 2, push.** Name the remote and branch. Push without force and set the upstream. When the remote branch exists with other history, stop and ask.
5. **Gate 3, open.** Show the final title, base, and body. Open the pull request as a draft, with the body read from a file or standard input and never placed inside a quoted argument. Report the URL and the draft state.

The pull request stays a draft. The skill never marks it ready, requests reviewers, enables auto-merge, merges, or closes the issue; those are the operator's actions. A declined, silent, or unclear answer ends the stage; report what is already done locally.

### Side path: reporter request

Use it when, after an honest attempt, `reproduce` cannot see the reported failure (the test passes, or the symptom depends on facts the report omits), or the report lacks something a reproduction needs. Stop the stage and:

1. Record what was tried and what was observed (commands, versions, results). That belongs in the stage record, not in the request.
2. List exactly what is missing under four headings: version, steps, expected versus actual, and logs. Include a heading only when the report lacks it, and never ask for what the report already gives.
3. Draft a short, polite request from the template in the reference: thanks, one sentence on what was tried, the numbered missing items, and a reminder to remove secrets and personal data. Set no deadline and give no warning that the issue will be closed.
4. Show it to the operator, who posts it. The skill never posts it, comments, labels, or changes the issue. Commit no test that passes or flakes while waiting.

## Return Contract

Each stage ends with a record naming the stage, the issue, and what the next stage needs:

| Stage | Record |
|-------|--------|
| `create` | The draft text, the template used, the duplicates checked and their verdicts |
| `size` | Class, files, reasoning, largest unknown |
| `reproduce` | Branch, commit hash, the test path, the observed failure output |
| `fix` | Ownership verdict with evidence, options offered, option chosen, branch, passing-test output, wider-suite result |
| `publish` | The answer to each gate, branch, commit hash, push result, pull request URL and draft state, the closing-keyword scan result |
| reporter request | What was tried and observed, the missing items by heading, the draft text, and the line `not posted` |

A record claiming a failure or a pass without the observed output is non-conformant.

## Foundational Stanzas

### Refusal & Escalation

REFUSE to file, edit, label, comment on, or close an issue, to post the reporter request, to push a branch, or to open a pull request without the operator's explicit request. In `publish`, REFUSE any external step whose own gate was not answered yes, a force push, a pull request that is not a draft, a closing keyword, and any handling of credentials. REFUSE to call a test a reproduction when it was not observed failing for the reported reason. Name the boundary crossed and escalate through the structured-inquiry channel per `rules/interactive-questions.md`.

### Output Surface

Records write to STDOUT. Issue drafts are shown in the conversation. Code and tests land at their domain-natural host locations per `rules/host-discovery.md`, with natural domain language and no plan-internal references per `rules/operational-mandates.md` CM-7.

### File-Authoring Contract

Every new source or test file routes through `scripts/inject-header.py`; exempt classes are listed in `src/apothem/schemas/header-exceptions.txt`. Commits follow Conventional Commits, and the change-set meets `rules/production-ready-prs.md`, including its human-only authorship clause for commit and pull request text.

### Structured Inquiry on Ambiguity

Route the question through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` when the report lacks reproduction steps, the expected behaviour, the affected version, or the ownership evidence, when the options in stage 4 are close, and at each `publish` gate. Never invent steps, versions, or logs.

## Recommended Next Step

**Run the next stage on the same issue** — `size` after `create`, `reproduce` after `size`, `fix` after `reproduce`; after `fix`, review the diff, and run `publish` only if you want the branch pushed and a draft pull request opened.

## Bindings (§0.j five-direction)

- **Drives →** ● Every issue draft, sizing note, repro checkpoint, fix branch, reporter request draft, and publish plan the stages emit.
- **Satisfies →** ● `CLAUDE.md` Source Layout row for the skills/ class. ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication).
- **Established by ↑** ● `skills/README.md` (this skill's index entry). ● `rules/operational-mandates.md` (CM-8, root cause over symptom).
- **Gated by ←** ● The operator's approval before any issue is filed or any branch leaves the machine. ● The observed failing run that stage 3 requires. ● The operator's separate confirmation of each external step in stage 5.
- **Cross-bound with ↔** ↔ `skills/dev-toolkit/SKILL.md` (debugging and test-first mechanics). ↔ `skills/dependency-upgrade/SKILL.md` (the version-change option). ↔ `rules/host-discovery.md` (tracker, branches, and test runner discovered). ↔ `rules/interactive-questions.md` (the inquiry channel). ↔ `rules/production-ready-prs.md` (the fix change-set).
