---
name: "issue-lifecycle"
version: "0.1.0"
updated: "2026-10-24"
description: "Takes a reported defect from issue to fix, one stage per run: create an issue, size it, reproduce it with a failing test, or fix it on a branch. Use for 'create an issue', 'size this issue', 'reproduce this bug' or 'fix issue 123'. Runs only when the user invokes it; never files or closes an issue unasked."
archetype: "engineering-template"
userInvocable: true
argument-hint: "[create|size|reproduce|fix] [issue number or description]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep, Bash(git status *), Bash(git log *), Bash(git diff *), Bash(git show *)"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Take a reported problem from issue to fix, leaving evidence at every step: a reviewed issue text, a sizing note with reasons, a failing test that proves the defect, and a fix that turns that test green. The skill runs one stage per invocation so the operator can inspect the result before the next stage starts.

## Detection Signal

The operator asks to `create an issue`, `size this issue`, `reproduce this bug`, `write a repro test`, or `fix issue <n>`, or hands over a defect report and asks for it to be worked through.

**Falsifiable counter-signal.** A one-line change the operator has already located, a repository-wide bug hunt, or a request to triage a security advisory is NOT a match; those go to a direct edit, a scanner, and `skills/vuln-triage/SKILL.md`.

## Non-Goals

- **Not a debugger.** Root-cause isolation and red-green mechanics belong to `skills/dev-toolkit/SKILL.md`; this skill calls that loop and records its outcome.
- **Not an issue publisher.** It drafts text. The operator files it, or says in this conversation to file it.
- **Not a release step.** It never pushes, opens a pull request, merges, or closes an issue unless the operator asks for that action by name.

## Workflow

Pick the stage from the first argument, or from the request. When the stage is unclear, ask. Discover the issue tracker, reference syntax, and test runner per `rules/host-discovery.md`; never assume them. Branches are `repro/<n>` and `fix/<n>` unless the host documents another scheme. Stage detail and message formats are in `references/stage-details.md`.

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

## Return Contract

Each stage ends with a record naming the stage, the issue, and what the next stage needs:

| Stage | Record |
|-------|--------|
| `create` | The draft text, the template used, the duplicates checked and their verdicts |
| `size` | Class, files, reasoning, largest unknown |
| `reproduce` | Branch, commit hash, the test path, the observed failure output |
| `fix` | Ownership verdict with evidence, options offered, option chosen, branch, passing-test output, wider-suite result |

A record claiming a failure or a pass without the observed output is non-conformant.

## Foundational Stanzas

### Refusal & Escalation

REFUSE to file, edit, label, or close an issue, to push a branch, or to open a pull request without the operator's explicit request. REFUSE to call a test a reproduction when it was not observed failing for the reported reason. Name the boundary crossed and escalate through the structured-inquiry channel per `rules/interactive-questions.md`.

### Output Surface

Records write to STDOUT. Issue drafts are shown in the conversation. Code and tests land at their domain-natural host locations per `rules/host-discovery.md`, with natural domain language and no plan-internal references per `rules/operational-mandates.md` CM-7.

### File-Authoring Contract

Every new source or test file routes through `scripts/inject-header.py`; exempt classes are listed in `src/apothem/schemas/header-exceptions.txt`. Commits follow Conventional Commits, and the change-set meets `rules/production-ready-prs.md`.

### Structured Inquiry on Ambiguity

When the report lacks reproduction steps, the expected behaviour, the affected version, or the ownership evidence, or when the options in stage 4 are close, route the question through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md`. Never invent steps, versions, or logs.

## Recommended Next Step

**Run the next stage on the same issue** — `size` after `create`, `reproduce` after `size`, `fix` after `reproduce`; after `fix`, review the diff and ask whether to push and open a pull request.

## Bindings (§0.j five-direction)

- **Drives →** ● Every issue draft, sizing note, repro checkpoint, and fix branch the stages emit.
- **Satisfies →** ● `CLAUDE.md` Source Layout row for the skills/ class. ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication).
- **Established by ↑** ● `skills/README.md` (this skill's index entry). ● `rules/operational-mandates.md` (CM-8, root cause over symptom).
- **Gated by ←** ● The operator's approval before any issue is filed or any branch leaves the machine. ● The observed failing run that stage 3 requires.
- **Cross-bound with ↔** ↔ `skills/dev-toolkit/SKILL.md` (debugging and test-first mechanics). ↔ `skills/dependency-upgrade/SKILL.md` (the version-change option). ↔ `rules/host-discovery.md` (tracker, branches, and test runner discovered). ↔ `rules/interactive-questions.md` (the inquiry channel). ↔ `rules/production-ready-prs.md` (the fix change-set).
