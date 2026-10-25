---
name: "authoritative-referencing-assurance"
description: "Assurance companion to authoritative-referencing for research claims that need more than a source — a proof lists its assumptions and names its weakest step, a reported number is bound to the run that made it, a novelty claim names its closest prior work, tool and model use is stated, and a pass/fail gate is fixed before results are seen. Path-filtered to research artifacts."
pathFilter: "**/research/**, **/manuscript/**, **/paper/**, **/*.bib, **/*.tex, **/literature/**"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Authoritative Referencing — Assurance Beyond Sourcing (Companion Sub-Rule)

## Purpose

A citation shows where a claim came from. It does not show that a proof holds, that a number can be rebuilt, that a result is new, which tools wrote the text, or that a pass/fail test was set before the results were known. The parent rule `rules/authoritative-referencing.md` binds the source; the sibling `rules/authoritative-referencing-provenance.md` binds how far the source was examined and the labels a claim carries. This companion binds six further checks a research claim passes before it is stated as settled. Path-filtered: it loads when a research artifact is edited.

## Obligations

### 1. A proof lists its assumptions and names its weakest step

- Open with the statement proved and the assumptions it uses, in the claim's own words. A hypothesis that first appears mid-argument is added to the list.
- Give every step a justification: an earlier line, a computation that can be rerun, or a cited result used no more strongly than its source states it. A stronger form or wider conditions needs its own argument, and a source seen only as an abstract leaves the step unchecked. "Clearly" or "by standard arguments", with no pointer, marks an unchecked step.
- Close with one line naming the weakest step and why. If none can be named, write "weakest step not examined".
- Call the text a `proof` only when every step carries a justification; otherwise it is a `proof sketch`, and the steps that lack one are listed. A claim resting on a sketch keeps the status `conjectured`.

### 2. Each status label names a specific thing

Provenance §1 lists the status labels; this section fixes what each requires.

- `proved`: a complete argument in the sense of obligation 1, weakest step named.
- `computer-checked`: a proof checker accepted the statement. Record the checker, its version, the file, and in words any gap between the formal statement and the text's. A file that admits a step unproved, or adds an axiom the text does not state, is not `computer-checked` for that statement.
- `numerical`: supported by computation at the cases run, which are listed. Floating-point output never closes a proof step; it may motivate a claim, test a special case, or locate a counterexample that is then verified by an exact route.
- An exact computation (integers, rationals, rigorously rounded bounds) may serve as a proof step when its code and input are named and a second implementation, written without reading the first, returns the same result.

### 3. A reported number is bound to the run that made it

- Give every number its unit, and no more digits than the spread across repeats or the stated error bound supports.
- Record, beside the number or in a linked run record: the command, the code commit, the data version or checksum, the seeds, the library versions that can change the result, and the hardware where results depend on it. Name the output field the value came from (for example, the `loss` field of `run-3/metrics.json`), not only the file.
- When code, data, seed, or settings change, the number is stale until the run is repeated, and the new value replaces the old one everywhere it appears.
- For a stochastic result, report the number of repeats and the spread. A best single run is labelled as best and is not the headline.
- Repeat the run once from a clean state before reporting. Report the number only if the repeat agrees within a stated tolerance; otherwise give both values and mark the result `not reproduced`. Copying text from output is covered in provenance §5.

### 4. A novelty claim names its closest neighbour

- Before "first", "novel", "new", "no prior work" or "to our knowledge" is written, the search record of provenance §2 exists and the wording follows provenance §3. The sentence also names the one to three closest prior works found and says in one line what differs: the assumption, method, scope, or result. A search that surfaced nothing adjacent is a search to widen, not a claim to make.
- List each distinct contribution once. Two statements that follow from one argument or one experiment are a single contribution unless each is stated and checked on its own.
- Do not name a result, method or constant of your own after a person, the author included; use a descriptive name. Names the literature already uses for others' work stay as the source uses them.
- When a priority claim is withdrawn or a prior work turns up, remove or rewrite the claim on every surface that carries it: abstract, introduction, contribution list, conclusion, cover letter, slides, release text. Search the artifact for its key words to find survivors, and note the removal in the change record.

### 5. Tool and model use is stated

- A research output that leaves the operator (manuscript, report, dataset description, poster, release note) carries a statement of the automated tools and models used: name and version or date, the task each did (searching, summarising, drafting, code, analysis, proof checking, editing), the parts of the output it touched, and what a person checked afterwards.
- Draft it from the session record and project files, not memory. A use that happened is stated, and "none were used" is written only when true.
- Place it where the venue asks. When the venue's policy is unknown, record the open question in the working notes and ask the operator rather than guess a form.
- A tool or model is not listed as an author, co-author or reviewer; responsibility for the content stays with the named people.
- A claim's status does not exceed what a person or checker verified. A proof step or computation a model suggested stays `conjectured` until obligations 1 to 3 are met for it.

### 6. A gate is fixed before results are seen

A gate is any pass/fail test that decides whether a result counts: a metric and threshold, a baseline, the data included or excluded, a stopping rule, or the checks a release must pass.

- Write the definition down before the run or before results are opened: metric, threshold, comparison, inclusions and exclusions, stopping rule, handling of ties and missing values. Date it and tie it to a commit or a checksum of the file that holds it.
- A change after results have been seen is an amendment: dated, reasoned, kept beside the original, with the outcome reported under both. A result under an amended gate is labelled post hoc. One that passes only under the amendment is reported as not passing the original gate.
- When no definition was set ahead of the run, say so where the result is reported and label the result exploratory.

## Enforcement

Path-filtered: the globs in this rule's `pathFilter` field load it when a research artifact is touched. The checks run when a proof, number, novelty sentence, use statement, or gate outcome is written; a missing item is a finding to fix before the claim is stated as settled. Depth follows the four-level table in `rules/authoritative-referencing-homes.md` §2. At EXPLORING and PERSONAL_USE, apply obligations 1 to 4 to the claims the work stands on and label an unfixed gate exploratory. At SHARED, apply them to every claim of meaningful scope in the draft. At PUBLIC_LAUNCH, apply all six to the submitted or published artifact.

## Failure tells

A proof with no stated assumptions, or a sketch called a proof. A theorem resting on a floating-point run. A formal file that admits a step, labelled `computer-checked`. A figure with no unit, or with more digits than the repeats support. A number whose code or data changed after it was recorded. The best seed shown as the result. "First" with no closest prior work named. One result listed as three contributions. A withdrawn priority claim still in the abstract or cover letter. A model-assisted output that says nothing about it. A threshold chosen after the results were opened and presented as planned.

## Bindings (§0.j five-direction)

- **Drives →** Every proof, reported number, novelty sentence, tool-and-model use statement, and gate outcome emitted on a research artifact under the path-filter; the assumption list, run binding, closest-neighbour sentence, use statement, and frozen gate each carries before it is stated as settled.
- **Satisfies →** `rules/authoritative-referencing.md` — the assurance half of the referencing discipline: the parent binds which source supports a claim and the provenance companion binds how far it was examined, while this companion binds whether the claim itself was checked, reproduced, placed against prior work, disclosed, and tested against a gate set in advance.
- **Established by ↑** `rules/authoritative-referencing.md` (parent rule — the citable-source requirement and the evidence-provenance anchor this companion extends); the meaningful-scope threshold the parent inherits.
- **Gated by ←** The path-filter (research, manuscript, paper, literature directories and bibliography or TeX files); the parent's baseline, which must be live for this companion to bound coherently.
- **Cross-bound with ↔** `rules/authoritative-referencing.md` (parent rule — the parent binds which source and when; this companion binds the proof, number, novelty, disclosure, and gate checks beyond the source).
