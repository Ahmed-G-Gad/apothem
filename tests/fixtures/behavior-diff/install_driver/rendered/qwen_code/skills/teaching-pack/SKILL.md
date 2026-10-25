---
name: "teaching-pack"
version: "0.1.0"
updated: "2026-10-25"
description: "Builds a teaching pack from one paper or technical document: goals, curriculum, formula walk-throughs, worked examples, quiz with key, glossary, slides on request. For 'teach me this paper' or 'make a study guide from this spec'. Several sources: source-synthesis; critique: research-review."
archetype: "authoring-template"
userInvocable: true
argument-hint: "[source path] [--audience newcomer|practitioner|specialist] [--parts LIST] [--slides]"
disable-model-invocation: false
allowedTools:
  - "Read"
  - "Glob"
  - "Grep"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Turn one paper or technical document into material that a learner can work through without the source open: learning goals, a curriculum in the order a learner needs, plain-step walk-throughs of the key formulas and algorithms, worked examples, a quiz with an answer key, and a glossary. Each line either comes from the source and says where, is built from a named part of it, or is marked as outside it. A part the source cannot support is reported as thin and left out, never padded. Part shapes are in [`references/pack-templates.md`](references/pack-templates.md), what each part needs from the source in [`references/source-requirements.md`](references/source-requirements.md), the slide outline in [`references/slide-outline.md`](references/slide-outline.md), and the closing checks in [`references/pre-delivery-checks.md`](references/pre-delivery-checks.md).

## Detection Signal

The user supplies one paper, specification, white paper, RFC, or design document (a path or pasted text) and asks to learn it or teach it: 'teach me this paper', 'turn this into a lesson plan with a quiz', 'make a study guide from this spec', 'write a glossary and exercises for this'.

**Falsifiable counter-signal.** A one-paragraph summary, an explanation of one formula or one section, a critique of the document, or a request that names no document is NOT a match: no pack is built.

## Non-Goals

- **Not a summary or a single explanation.** The deliverable is the full set of parts; a short answer about the document is given directly.
- **Not a review.** The pack teaches what the document claims and how it gets there; whether it is right belongs to `research-review`.
- **Not a multi-document synthesis.** Several documents go to `skills/source-synthesis/SKILL.md`; filing a paper into a project knowledge base goes to `skills/knowledge-wiki/SKILL.md`.
- **Not a deck builder.** It writes a slide outline and hands it on; it never describes an outline as a deck.
- **Not teaching from memory.** Nothing about the document is used that was not read in this session.

## Workflow

### 1. Open the source and record the basis

Take the source from the argument or the request and read it with Read, in page ranges when it is a long PDF. Given only a title, link, or identifier, ask for the file or the text (reachability per `rules/source-accessibility.md`); a well-known paper is not rebuilt from recollection. Record the basis as `read in full`, `read in part` with the sections named, or `abstract only`. Then map the source: sections, definitions, formulas, algorithms, figures and tables, stated assumptions, stated limits, each with the locator seen. A locator is recorded only when seen and a page number is never estimated; a document with no numbered sections is located by heading text. On an `abstract only` basis stop and ask for the text; if it is not given, only goals and glossary may be written and each says so.

### 2. Settle the learner and the scope

Make one round of structured inquiry for whatever the request left open: audience (`newcomer`, `practitioner`, `specialist`, recommending `practitioner`), prior knowledge, which parts to write (default: all six; the slide outline only under `--slides`), and where the output goes. Report which settings came from the user and which are defaults.

### 3. Build the claim ledger

Before writing any part, list the source's teachable items and number them: definitions, claims, formulas, algorithms, examples, assumptions, limits. Each entry has a kind, a locator, and a one-line paraphrase. Every part below cites ledger entries and nothing else. The ledger is working material; it is reported only through the coverage row of the Return Contract.

### 4. Write the parts in this order

Use the shapes in `references/pack-templates.md`. Mark every content line with exactly one marker: `[§x]` when the source states it at x, `[built from §x]` when the pack constructs it from what the source states at x, `[not in source]` for outside knowledge, which is allowed only in glossary glosses and prerequisite lines and never in a goal, a key, or a walk-through.

1. **Goals.** Three to six observable outcomes (derive, compute, choose, explain why), each tied to the sections it rests on. 'Understand' is not an outcome.
2. **Curriculum.** One module per source section, or per tight group of sections, in the source's order. Reorder only when a later section is a prerequisite for an earlier one, and record the move and why. Each module has its sections, its prerequisite modules, what the learner can do afterwards, and a check question. A section with too little to teach (a heading with a line under it, an acknowledgements block) is listed as `thin` with what it holds, not expanded. The last module covers the assumptions and limits the source states; when it states none, say so rather than supply some.
3. **Walk-throughs.** One for each key formula or algorithm, meaning one a stated result depends on: what it computes, a symbol table, the steps in plain words each mapped to a term or line, the reason for its form only if the source gives one, and a boundary case. List what was skipped and why. A branching algorithm may be drawn through `skills/diagram-authoring/SKILL.md`.
4. **Worked examples.** At least one per walk-through, with small concrete inputs and every intermediate value shown. Use the source's own numbers where it gives some; otherwise construct them. Label the arithmetic `machine-checked` only when a calculation was run, else `hand-computed`.
5. **Quiz and answer key.** Each item names the goal it tests; every goal has an item and at least one item covers a stated limit. Wrong options come from real near-misses in the source (a neighbouring definition, a dropped condition), not nonsense. A question whose key would need `[not in source]` is not written. The key is kept apart from the questions and cites a locator per line.
6. **Glossary.** Each term the audience does not already know (from the prior knowledge settled in step 2), with a definition of at most two sentences, its first locator, and whether the source defines it or only uses it.

State the document's claims as its claims ('the authors show', 'the paper assumes'), never as settled fact. Paraphrase by default; quote only where the exact wording is the point (a definition, a requirement term), as a short marked excerpt with its locator per `rules/authoritative-referencing-quotation.md`, and for this skill at most one quotation of under fifteen words per section. Cite figures and tables by number and do not reproduce them.

### 5. Slides, only under --slides

Write the outline per `references/slide-outline.md`, then look for a slide or document skill the host exposes, found through `rules/host-discovery.md` and never assumed, and hand it the outline file. With several candidates, ask which. With none, or if the user declines, deliver the outline alone and say that no deck was built.

### 6. Check, then deliver

Run `references/pre-delivery-checks.md`, repair what fails, and report each check as pass, fail, or not checked with the reason.

## Return Contract

| Field | Content |
|-------|---------|
| `source` | Path, title, authors, venue and year as seen or `not seen`, and the access basis |
| `audience` | Level and prior knowledge, each marked user-set or default |
| `parts` | Each of the six parts and the outline: delivered, thin with the reason, or not requested |
| `markers` | Lines per marker kind, and the number of unmarked content lines (must be zero) |
| `coverage` | Each goal with its sections and the quiz items that test it |
| `skipped` | Formulas, algorithms, and sections not taught, with the reason for each |
| `checks` | Each pre-delivery check as pass, fail, or not checked, with how it was checked |
| `hand-off` | The slide skill used and the file passed, `none found`, or `not requested` |

A delivery with a part missing and no thin notice is non-conformant.

## Foundational Stanzas

### Refusal & Escalation

REFUSE to build a pack from a document that was not opened, to present outside knowledge as the document's, to write a key line the document does not support, to call an outline a finished deck, or to copy long passages, figures, or tables from the source. Name the action refused and the boundary it crossed, then offer the compliant route through the structured-inquiry channel per `rules/interactive-questions.md`: supply the text, narrow the parts, or accept a thin notice.

### Output Surface

The pack prints in the conversation as one Markdown document in part order, with the answer key last under a heading that warns of spoilers. When the user names a path, or the document is long, it is written there with the answer key as a second file. The skill holds read and search tools only, so files are written through the host's normal editing path. Planning notes stay under `<project-root>/.apothem/plans/`.

### File-Authoring Contract

Each new file carries the canonical header through `scripts/inject-header.py`; exempt classes are listed in `src/apothem/schemas/header-exceptions.txt`. A pack printed to the conversation is header-exempt, and edits to an existing file keep its header.

### Structured Inquiry on Ambiguity

Audience, prior knowledge, the parts wanted, the output path, which formulas count as key, and the choice among several slide skills belong to the user. Ask each with a rationale, a recommendation, and a default pointer per `rules/interactive-questions.md`. Facts about the host, such as an existing docs folder or the slide skills it has, are discovered per `rules/host-discovery.md` and not asked.

## Recommended Next Step

**Read the goals and the thin-source notices first**, then answer the quiz cold, without the key; any item you cannot answer from the pack names the part to repair.

## Bindings (§0.j five-direction)

- **Drives →** ● Every teaching pack this skill produces. ● The slide outline handed to a slide or document skill.
- **Satisfies →** ● `CLAUDE.md` Source Layout row for the skills/ class. ● `CLAUDE.md` Ambiguity Handling (audience and scope are asked, never assumed).
- **Established by ↑** ● `skills/README.md` (this skill's index entry). ● `CLAUDE.md` Source Layout (folder-with-`SKILL.md` convention).
- **Gated by ←** ● A readable source document. ● The harness's Read / Glob / Grep surface. ● User-confirmed audience and parts before writing starts.
- **Cross-bound with ↔** ↔ `rules/authoritative-referencing.md` (a claim cites its source or is marked). ↔ `rules/authoritative-referencing-provenance.md` (how far the source was read is stated). ↔ `rules/authoritative-referencing-quotation.md` (paraphrase by default, brief marked quotation). ↔ `rules/source-accessibility.md` (an unreachable source is requested, not guessed). ↔ `rules/host-discovery.md` (the slide skill and output location are discovered). ↔ `rules/interactive-questions.md` (the inquiry channel). ↔ `skills/source-synthesis/SKILL.md` + `skills/knowledge-wiki/SKILL.md` + `skills/diagram-authoring/SKILL.md` (neighbouring skills).
