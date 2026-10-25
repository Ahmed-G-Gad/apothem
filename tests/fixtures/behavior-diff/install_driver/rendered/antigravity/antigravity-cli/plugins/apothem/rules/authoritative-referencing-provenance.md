---
trigger: glob
description: "Evidence-provenance companion to authoritative-referencing — label how each load-bearing claim's evidence was reached and what status it holds, keep a literature search record, never infer novelty from an empty search, check a cited result's conditions, count only checks that could fail, and never label a model-written reading as peer review. Path-filtered to research artifacts."
globs: "**/research/**, **/manuscript/**, **/paper/**, **/*.bib, **/*.tex, **/literature/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Authoritative Referencing — Evidence Provenance (Companion Sub-Rule)

## Purpose

Record how far each claim's evidence was actually examined. The parent rule `rules/authoritative-referencing.md` requires a citable source for each claim; this companion requires that the reader can see what was done with that source: whether it was read or only skimmed, whether the claim is established or only proposed, and where the search for it ended. Path-filtered: it loads when a research artifact (notes, manuscript, bibliography, literature record) is edited.

## Obligations

### 1. Label access and status on every load-bearing claim

A load-bearing claim carries two labels, placed beside the claim or in the table that lists it.

- **Access** states how the evidence was reached: `read in full`, `abstract only`, `search-result summary`, `repository or code inspected`, or `reasoning alone`.
- **Status** states what has been established: `proved`, `computer-checked`, `cited`, `numerical`, or `conjectured`.

Use the weakest label that is true. A source seen only as an abstract or a search snippet is never described as read, and a claim that rests on one numerical run is never described as proved. A claim with no label is treated as `reasoning alone` and `conjectured`.

### 2. Keep a search record for literature claims

Any claim about what the literature contains (a gap, a first, a consensus, a count) is backed by a record with four parts:

1. the queries run, with the index or tool each ran against;
2. the items opened, and how far each was read (per obligation 1);
3. the items that were blocked, paywalled, or unreachable, listed by name; a lookup tool or connector that was never loaded, was not authorised, or returned nothing for lack of a session is listed here as blocked, with its name, and is never reported as "searched, nothing found";
4. the point where the search stopped and why.

The record sits next to the claim or in a linked file. A literature claim with no record is reported as unverified.

### 3. An empty search does not establish novelty

Never infer novelty, a gap, or "no prior work" from a search that returned nothing. State the limits instead: which indexes, terms, and years were covered, and what was not reachable. Write "not found in the searches recorded" rather than "does not exist". A novelty statement is only as strong as the record behind it.

### 4. Check a cited result against the case at hand

Before a cited result is applied, compare its hypotheses, conditions, and scope with the present case. Record the comparison in one line: which conditions hold, which were verified, which were assumed. A result whose conditions do not match, or were not checked, is cited as background only and is not used as support.

### 5. A check counts only if it could have failed

A test, script, or statistic is evidence only when it can return a negative result.

- Include a control that is expected to fail, and confirm that it does.
- Copy every reported number from the run's actual output; never from memory, from an earlier run, or from an expectation.
- State the command or script and the input it ran on, so the check can be repeated.
- Show that the check reacts to a fault in what it guards. Change that target in one small way (flip a comparison, drop a branch, shift an index by one, corrupt one input value) and confirm the check turns red. List each change the check let through; a check that stays green through every change tried guards nothing.
- Match success on the whole expected token, anchored to a line, a field, or the exit status. A pass test that searches output for a substring (`ok`, `0 failed`) can match inside a failure line; run the failing case once to confirm it is not read as a pass.
- Keep the assertions the claim rests on. Where assertions can be compiled out or skipped (an optimised interpreter run, a release build), write a load-bearing check as an explicit error or a test-framework assertion, and run the suite once with assertions removed to see that no claim rested on one alone.

A check that has only ever passed is labelled `not yet shown to discriminate`.

### 6. A model-written reading is not peer review

An automated or model-written reading of a manuscript or source is an aid, not peer review. It is never labelled, cited, or counted as review, referee input, or independent verification. Name it for what it is (for example, "model-assisted reading") and keep it out of any list of reviewers or reviews.

## Enforcement

Path-filtered: the globs in this rule's `pathFilter` field demand-load it on research artifacts. The label, record, and comparison are checked when a claim is emitted; a missing label or record is a finding to fix before the claim is stated as settled. Strictness follows the four-level table at `rules/authoritative-referencing-homes.md` §2: at EXPLORING and PERSONAL_USE, label the load-bearing claims; at SHARED, label every claim of meaningful scope; at PUBLIC_LAUNCH, label every claim in a public or submitted artifact. The `citation-auditor` subagent checks that cited references exist and say what the text attributes to them; it does not replace the labels and records required here.

## Failure tells

An abstract-only source described as read. A conjecture stated without a status. A novelty claim backed by one empty query. A search summary with no list of what was unreachable. A theorem applied with its conditions unchecked. A passing test with no control that fails. A check that no small fault in its target turns red. A pass test that matches a substring of a failure line. A claim resting on an assertion that an optimised run deletes. A lookup connector that never loaded, reported as "nothing found". A number in the text that differs from the run output. A model-written reading listed as a review.

## Bindings (§0.j five-direction)

- **Drives →** Every load-bearing claim emitted on a research artifact under the path-filter; the access label, status label, search record, conditions check, and discriminating-check bar each claim meets before it is stated as settled.
- **Satisfies →** `rules/authoritative-referencing.md` — the evidence-provenance half of the referencing discipline (the parent binds which source supports a claim; this companion binds how far that source was examined and what status the claim holds).
- **Established by ↑** `rules/authoritative-referencing.md` (parent rule — the citable-source requirement this companion makes inspectable); the meaningful-scope threshold the parent inherits.
- **Gated by ←** The path-filter (research, manuscript, paper, literature directories and bibliography or TeX files); the parent's baseline, which must be live for this companion to bound coherently.
- **Cross-bound with ↔** `rules/authoritative-referencing.md` (parent rule — the parent binds which source and when; this companion binds the provenance labels, search record, and check discipline).
