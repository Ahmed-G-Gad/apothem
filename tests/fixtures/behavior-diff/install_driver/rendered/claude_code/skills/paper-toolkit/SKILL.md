---
name: "paper-toolkit"
description: "Papers with no research suite: 'write a reading note', 'compare these papers', 'draft related work from these sources', 'what would reviewers ask about my draft', 'dedupe my references'. Suite or referee review: research-* commands. Reference checks: citation-auditor. Loose files: source-synthesis."
user-invocable: true
argument-hint: "[--mode note|compare|related|critique|style] [PAPER_OR_DRAFT_PATHS...] [--focus QUESTION]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep, WebSearch"
metadata:
  version: "0.1.0"
  updated: "2026-10-25"
  archetype: "research-template"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Do five jobs on papers and drafts for a user who has no research suite: write a reading note on one paper, compare two to five papers, draft a related-work section from supplied sources, critique any draft, and run a style pass over a reference list. Each job reads only what the user hands over, states how much of every paper was actually read, and ends in a result the user can check line by line. Each mode has its template under `references/`, linked from the mode's heading.

## Detection Signal

The user supplies one or more papers, or a draft, and asks for a note on a paper, a side-by-side of results, a related-work section built from named sources, a critique of a draft, or a tidy of a bibliography.

**Falsifiable counter-signal.** A request to find new papers, to verify that references exist or say what the text claims, to combine loose documents that are not papers, or to referee a manuscript with scores and a verdict is NOT a match; the Non-Goals name where each goes.

## Non-Goals

- **Not a pipeline stage.** When the request concerns a research suite's own material, point to the stage that owns it: sources and per-source extraction to `commands/research-sources.md`, the literature matrix to `commands/research-synthesis.md`, the manuscript and its related-work section to `commands/research-paper.md`, review of the manuscript to `commands/research-review.md`. Files outside the suite stay here.
- **Not a reference verifier.** Whether a reference exists, and whether the opened source says what the text attributes to it, belongs to `agents/citation-auditor.md`. The style pass makes no existence or support claim.
- **Not source discovery.** Finding papers belongs to `skills/multi-source-research/SKILL.md` or `agents/research-scout.md`; `related` mode never searches.
- **Not a synthesis of loose documents.** Notes, reports, and pages with no paper focus belong to `skills/source-synthesis/SKILL.md`.
- **Not a knowledge base.** Filing a paper into a project wiki is `skills/knowledge-wiki/SKILL.md`; picking one approach among several is `skills/decision-matrix/SKILL.md`.
- **Not a referee review.** A scored review with a verdict, a venue profile, or a recommendation on a scale is `commands/research-review.md`, which also takes a paper outside any suite through its `--paper` mode. The critique here is the author's own pre-submission reading: it gives no verdict and no score, and is labelled a model-assisted reading.

## Workflow

### 0. Settle mode, inputs, and surroundings (every mode)

1. Take the mode from `--mode`, else from the request wording; if two modes fit, ask.
2. Read every named input. A long PDF is read in page ranges until the end. Record for each paper its citation as printed, the version read (preprint, accepted manuscript, published, unknown), and its basis: `read in full`, `excerpt` with the portion named, or `abstract only`. A paper given only as an identifier or link is opened with the host's fetch capability. One that cannot be opened is `unread`: it appears in the output, supports no claim, and the user is asked for the file or its text. Reachability follows `rules/source-accessibility.md`.
3. Glob `.apothem/plans/*/_spec/research-spec.md`. When a suite exists and the inputs are its artifacts, or the request is one of its stages, name the owning command from the first Non-Goal and ask whether to hand off or stay standalone. Files outside the suite stay here.
4. Three rules hold in every mode. Numbers, quotations, and years are copied from the opened source, never recalled. A page, section, figure, or table locator is written only when it was seen. Anything from memory is marked `from memory: unverified`.

### Mode `note` ([template](references/reading-note.md))

1. Take the focus from `--focus`, else ask what question is being put to the paper; with none, write a general note and say so.
2. Fill the template: citation and version, basis, claim, method, evidence, limits, what the paper is citable for, and what it is not citable for.
3. List what was not read or not clear, so a later reader knows where the note stops.

### Mode `compare` ([guide](references/paper-comparison.md))

1. Count the papers. One goes to `note`; more than five, ask whether to split by claim or hand the set to `skills/source-synthesis/SKILL.md`. Fix the claim or question the comparison serves, from `--focus` or the request; without one, ask.
2. Write a short note per paper, then set the papers side by side on the axes in the guide.
3. Give each pair that bears on one claim a verdict: comparable, comparable with a named caveat, not directly comparable with the differing axis named and what would align them, or undetermined where the text read does not say. Never produce an adjusted number to force a match.
4. Finish with the cite-for table: for each claim, which paper to cite, why that one, and what no paper in the set should be cited for.

### Mode `related` ([template](references/related-section.md))

1. Get the position the section must support, in the user's words: what the draft contributes and to what. Without it, ask.
2. Build the source set from the supplied files only. Do not search, and do not add a paper from memory.
3. Group the sources into two to five themes and order them from background, through closest work, to the gap.
4. Draft the prose to the rules in the template, and word each "first", "novel", or "no prior work" sentence per `rules/authoritative-referencing-assurance.md` §4: it names the closest supplied work and what differs. Where the argument needs support the set lacks, write a visible `[citation needed: what the support must show]` marker; never a guessed reference.
5. Close with the coverage report: themes against sources used, the basis mix, every marker, and the supplied sources left unused with the reason.

### Mode `critique` ([template](references/critique-template.md))

1. Read the whole draft before judging any part. Note what is missing from the input (appendices, data, supplements).
2. Produce the three parts in the template: what is strong, the five questions a reviewer would ask, and the three changes that matter most. Anchor each point in the draft's own words and location. Test the claims the draft stands on against `rules/authoritative-referencing-assurance.md` §1 to §4 (a proof's assumptions and weakest step, a number's run record, the closest prior work behind each novelty sentence) and `rules/authoritative-referencing-provenance.md` §1 to §3 (access labels and the search record). A claim that fails one is a question or a change, with its location.
3. State what was not judged. A draft that holds up is reported as holding up; no weakness is invented to fill a slot.

### Mode `style` ([checks](references/reference-style-pass.md))

1. Take the reference list from the named `.bib` file or bibliography section; add the draft if given, so cited and uncited keys can be compared.
2. Run checks S1 to S6 with Grep and Read. A check that cannot run is reported as skipped with the reason, never as passed.
3. Look up a published version only for preprint entries, sending an identifier or a title with the first author and nothing from the draft. With no lookup tool, mark those entries `unchecked`.
4. Report findings; change no file. A corrected file is produced on request, one finding class at a time.

## Return Contract

| Mode | Output |
|------|--------|
| `note` | The note with its basis line first, the citable-for and not-citable-for lists, and the unread parts |
| `compare` | Short notes, the side-by-side table, a verdict per relevant pair with the axis named, the cite-for table, and the undetermined axes |
| `related` | The section with its markers, the coverage report, and lists of unread, abstract-only, and unused sources |
| `critique` | The model-assisted label, strengths, five tagged questions, up to three ranked changes, and what was not judged |
| `style` | Findings by check ID with the entries involved, checks skipped and why, lookups made and what each sent, and counts |

Every output names each paper it relies on with its basis. An output that leaves out a basis, a skipped check, or an unread paper is non-conformant.

## Foundational Stanzas

### Refusal & Escalation

REFUSE to cite a paper that was not supplied or opened, to fill a missing reference field from memory, to put text from an unpublished draft into a search, to present a critique as peer review or give it a verdict, and to adjust a number so two results look comparable. Name the boundary crossed and offer the compliant route through the structured-inquiry channel per `rules/interactive-questions.md`.

### Output Surface

Results print to STDOUT. A file is written only when the user names a path or asks to save. Planning artifacts go to `<project-root>/.apothem/plans/`.

### File-Authoring Contract

A NEW saved note, draft, or report routes through `scripts/inject-header.py` where the host project requires authorship headers; exempt classes are listed in `src/apothem/schemas/header-exceptions.txt`. A corrected bibliography edits entries in the existing file and leaves its header alone.

### Structured Inquiry on Ambiguity

The mode, the focus question, the contribution statement, which papers a comparison covers, and whether to hand off to a suite stage are the user's decisions. Route them through the structured-inquiry channel per `rules/interactive-questions.md` with a recommended default; discover per `rules/host-discovery.md`, never invent.

## Recommended Next Step

**Send the result to the check that fits it** — run `agents/citation-auditor.md` over the references a related-work draft or a cleaned bibliography relies on, and re-run `critique` on the draft after the three changes land.

## Bindings (§0.j five-direction)

- **Drives →** ● Every reading note, comparison, related-work draft with its coverage report, critique, and style-pass report this skill emits.
- **Satisfies →** ● `CLAUDE.md` Source Layout row for the skills/ class. ● The research cohort's suite-free paper surface. ● `rules/authoritative-referencing-assurance.md` §1 to §4 and `rules/authoritative-referencing-provenance.md` §1 to §3, which load by path only when a research file is open; the `critique` and `related` modes carry them into a plain chat about a draft.
- **Established by ↑** ● `CLAUDE.md` Source Layout (folder-with-`SKILL.md` convention). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication).
- **Gated by ←** ● The harness's Read / Glob / Grep / WebSearch surface. ● Supplied papers or drafts, and the user's answer on mode and focus.
- **Cross-bound with ↔** ↔ `rules/authoritative-referencing-provenance.md` (access labels and the model-reading limit). ↔ `rules/authoritative-referencing-assurance.md` (proof, number, and novelty checks). ↔ `rules/source-accessibility.md` (unreachable sources). ↔ `rules/interactive-questions.md` (the inquiry channel). ↔ `rules/host-discovery.md` (the suite is discovered). ↔ `agents/citation-auditor.md` + `agents/research-scout.md` (verification and discovery). ↔ `skills/source-synthesis/SKILL.md` + `skills/multi-source-research/SKILL.md` + `skills/knowledge-wiki/SKILL.md` + `skills/decision-matrix/SKILL.md` (sibling research skills). ↔ `commands/research-sources.md` + `commands/research-synthesis.md` + `commands/research-paper.md` + `commands/research-review.md` (the suite stages this skill defers to).
