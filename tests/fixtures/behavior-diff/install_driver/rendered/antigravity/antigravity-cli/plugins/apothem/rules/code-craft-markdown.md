---
trigger: glob
description: "Per-language code-craft for Markdown / prose artifacts — purpose-driven structure, sentence-level justification, precision over politeness, active-voice construction, hedge-elimination per the clean-room generation projection. Honors host's ratified Markdown linter (markdownlint, vale, prose-linter) and frontmatter conventions; passes the host's lint clean."
globs: "**/*.md, **/*.markdown"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Code Craft — Markdown

## What this rule enforces

This rule binds **M13 — Code Craft Conventions** at the **Markdown / prose per-language tier**. Every Markdown artifact the agent produces — README, ADR, RFC, design document, runbook, contributing guide, changelog entry, documentation page, response prose, commit-message body — MUST meet a sentence-level craft floor: **purpose-driven structure** (shape derived from communication purpose, not a generic template); **sentence-level justification** (every sentence advances the purpose; removable sentences MUST NOT exist); **precision over politeness** (exact words; pre-landing hedges removed); **active-voice construction** (concrete subjects, specific verbs); **hedge-elimination** in prescriptive contexts. The rule extends `rules/clean-room-generation.md` §5 (Prose and Documentation) into the per-language code-craft surface.

## Pre-conditions

Applies whenever a Markdown artifact (any file matching the `pathFilter` globs — `*.md`, `*.markdown`) is authored, modified, or reviewed. Fenced code blocks remain governed by the per-language code-craft rule for the block's language (`python` → `rules/code-craft-python.md`; `bash` → `rules/code-craft-shell.md`); this rule governs the surrounding prose, document structure, link discipline, and frontmatter.

## Required behavior

### 1. Purpose-Driven Structure

Every Markdown artifact has a communication purpose; structure follows purpose:

| Purpose class | Structure shape | Why |
|---|---|---|
| **Tutorial** | Sequential walkthrough; reader proceeds top-to-bottom | The reader's mental model is built incrementally |
| **How-to guide** | Goal-then-steps; prerequisites, then ordered steps | The reader knows what they want and seeks the recipe |
| **Reference** | Random-access entries; alphabetical or topical index | The reader looks up a specific item, not a sequence |
| **Explanation** | Concept-then-elaboration; progressive disclosure | The reader builds understanding from primitives outward |
| **Architecture document (ADR / RFC / design)** | Context · Decision · Consequences · Alternatives | The reader audits the reasoning behind a structural choice |
| **Runbook** | Trigger · Diagnosis · Action · Verification · Rollback | The reader is on-call and needs the next step under pressure |

The structure is **not** imported from a template "because documents like this usually have them". When a section's content does not advance the purpose, the section is removed. When an unconventional section is required by the purpose, the section is added with a purpose-explanatory header rather than forced into a generic shape.

### 2. Sentence-Level Justification

Every sentence MUST advance the purpose. Three failure classes are eliminated at authoring time:

- **Filler.** "In this section, we will discuss …" / "It is important to note that …" / "As mentioned earlier …" — meta-commentary about the document, not substance. Remove.
- **Throat-clearing.** "Before diving in …" / "Without further ado …" / "Let's begin by …" — openings that delay substance. Remove, or replace with the substantive opening.
- **Restatement.** A sentence re-stating the prior one in different words. Compress to one.

The test: remove the sentence — does the document still advance the purpose? Yes → it was filler; remove it. No → it is load-bearing; keep it.

#### 2.1 Prose-over-lists default; one question per turn

Prose is the default carrier; a list earns its place only when the content is **genuinely enumerable** — a set of parallel items, an ordered sequence of steps, a lookup table — where the list structure makes the parallelism or order legible. A conversational answer, an explanation, or a single recommendation stays prose: a bulleted list of one or two items, or a list that fragments a continuous argument into disconnected stubs, is a list imposed where prose carries the meaning better. The reach for a list is justified by the content's structure, not by the habit of bulleting.

When prose elicits a decision, ask **at most one question per turn**. Batching several questions into one turn forces the reader to track and answer them in parallel and buries the load-bearing one; surface the single most decision-blocking question, resolve it, then surface the next. (Structured-inquiry invocations route through `rules/interactive-questions.md` and carry their own option-set shape; this is the prose-surface floor for the conversational case.)

### 3. Precision Over Politeness

Exact words. Specific claims. Numbers with units. Conditions stated:

- **Right:** "The function returns null when the key is missing."
- **Wrong:** "The function may return null in certain cases."

Hedge words that soften a binding prescription MUST be removed. The hedging-vocabulary discipline at `rules/definitiveness.md` (M8) applies in full: **maybe · might · could · should probably · usually · generally · typically · mostly · often · perhaps · possibly · somewhat · fairly · roughly · broadly**, plus the filler `basically` · `kind of` · `in some sense`, are eliminated where binding prescription is possible. Where the claim genuinely is conditional, the conditions are enumerated explicitly: "The function returns null when the key is missing OR when the value is `None`."

Content-free qualifiers (`very`, `quite`, `somewhat`, `rather`, `fairly`, `kind of`) are noise — remove them; the unqualified claim is stronger and shorter.

### 4. Active-Voice Construction

Active voice. Concrete subjects. Specific verbs.

- **Right:** "The scheduler assigns tasks to workers."
- **Wrong:** "Tasks are assigned to workers by the scheduler."
- **Worse:** "Tasks are assigned to workers." (passive without actor — responsibility undiagnosable.)

Passive voice is permitted in two cases only: (a) the actor is genuinely unknown or irrelevant ("The configuration is loaded from disk at startup"); (b) the patient is the topical focus and inverting would obscure the topic ("The bug was introduced in commit abc123"). Outside these cases, use active voice.

### 5. Frontmatter Discipline

When the host's Markdown corpus uses frontmatter (the artifact's first non-empty line is `---`), the frontmatter MUST conform to the host's discovered schema:

- **Required fields per artifact class.** The host's per-class contract (rule files require `name` + `description`; skill files require `name` + `description`; documentation pages may require `title` + `summary` + `tags`) is honored per `rules/host-discovery.md`.
- **Field shape.** Every required field is non-empty (per the PreToolUse Write hook validation at the hooks pipeline). Booleans are `true` / `false` (not `yes` / `no` unless the host's discovered convention uses them). Lists use the host's ratified shape (block `- item` or flow `[item, item]`).
- **Field order.** Sibling frontmatter ordering is preserved; new fields land at the host-ratified position, not at top or bottom by default.

### 6. Link Discipline

Every link MUST be **resolvable** at emission time:

- **Internal links.** Links to host files resolve to existing files; anchors resolve to existing headings. When documenting placeholder link syntax, spell it `text -> path/to/file.md` or `text -> path/to/file.md#section` (not as a live link).
- **External links.** Permalinked where possible — commit-pinned over branch-pointed; archived versions where the canonical source may rot.
- **Cited material.** Quotes and paraphrases carry the source as a link or footnote citation. Folklore claims (no source) are removed or sourced.

Stale links are findings per `rules/visual-leverage.md` §4 staleness-check pattern: a link whose target has moved or been removed is stale, and staleness is repaired in the same change-set as the prose modification, never deferred.

### 7. Code Block Discipline

- **Language tag.** Every fenced block declares its language (` ```python `, ` ```bash `, ` ```yaml `, ` ```json `). An untagged block forgoes syntax highlighting; the missing tag is a finding.
- **Per-language code-craft.** Block contents honor the per-language sibling rule (Python → `code-craft-python.md`; Shell → `code-craft-shell.md`; other languages → host-discovered convention via `code-craft-conventions.md`).
- **Runnable examples.** Examples claiming to be runnable MUST run as-shown. Pseudocode is labeled (` ```python title="pseudocode" ` or a comment marker) so the reader is not misled.
- **Inline-code discipline.** Backticks for symbols, paths, command names, file names; plain prose for natural-language usage. `pathlib.Path` (symbol) is backticked; "the path object" (noun) is not.

### 8. Heading Hierarchy

Heading levels carry semantic weight:

- **One H1 per file.** The H1 is the primary title; subsequent sections use H2 and below.
- **No skipped levels.** H2 → H3 is allowed; H2 → H4 is not (the missing H3 breaks document outliners).
- **Headings are anchors.** Every referenced heading becomes an anchor (Markdown auto-generates the anchor from heading text per the host's rules — kebab-case-of-heading is the common shape).
- **Sentence case or title case.** The host's convention is honored uniformly; mixed casing across siblings is a finding.

### 9. Linting & Static Analysis (M13.7)

The artifact MUST pass the host's ratified Markdown linter clean:

- **markdownlint** (or `markdownlint-cli2` / `markdownlint-cli`) — the host's `.markdownlint.json` / `.markdownlint.yaml` is honored. Common rules: MD013 (line length — host-configured; 80 / 100 / 120 the prevalent values), MD024 (no duplicate headings), MD033 (inline HTML allowed by config), MD041 (first line is a top-level heading).
- **vale** or another prose-linter — when configured, the host's `.vale.ini` and styles (`Microsoft`, `write-good`, custom dictionaries) apply; the artifact passes the configured severity threshold clean.

### 10. Length Discipline

Long Markdown artifacts (above 200 lines / 2000 tokens) MUST honor the incremental generation protocol per `rules/large-file-generation.md`. Sections growing beyond the artifact's coherence threshold are split into cross-linked sibling files, never left as monolithic walls of prose.

## Disclosure surface

Every Markdown artifact emission, restructure, or hedge-elimination is recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[Discovery — source: .markdownlint.json | .vale.ini | sibling-md-files; value: <ruleset | style>; honored]` for lint-config and prose-linter discoveries.
- `[Discovery — source: sibling-frontmatter-schema; value: <field-list>; honored]` for frontmatter-schema discoveries.
- `[Refinement — improvement: clarity; intercepted: <hedge-form | passive-voice | filler-sentence>; replacement: <revised-form>]` for hedge / passive / filler interceptions.
- `[Default — applied: <auto-decision>; class: pure-formatting-normalization]` for markdownlint / prettier-md normalizations on existing files where the host has a ratified style.

## Failure tells

A README that opens with "This document describes …" (filler — the title declares what the document describes). An ADR with a "Background" section running ten paragraphs of throat-clearing before the decision (purpose-drift). A how-to guide structured as a sequential narrative ("First we'll explore the concept, then we'll see how it works …") instead of goal-then-steps (purpose-shape mismatch). Hedging vocabulary in prescriptive prose: "users should generally commit small changes" / "the function might return null in some cases" / "this is typically the safer approach" (M8 violation). Passive voice obscuring the actor: "It was decided that …" / "The bug was fixed" without naming who decided / who fixed (responsibility opaque). Content-free qualifiers in prescription: "very important", "fairly safe", "rather slow" (no information). Untagged fenced code blocks (`` ``` `` followed by code with no language tag — markdownlint MD040 violation). Internal links pointing to moved or removed files (link rot). External links pointing to mutable refs (`main` / `master` / `latest`) where commit-pinned is available (volatile reference). Heading hierarchy with skipped levels (H2 → H4) breaking document outliners. Multiple H1 headings in a single file (one-H1 violation). Frontmatter fields missing the host-ratified required set (`description` non-empty per the hooks pipeline hook validation). A 500-line Markdown artifact authored as a single monolithic write rather than via the incremental generation protocol (CM-23 / `rules/large-file-generation.md` violation).

## Bindings (§0.j five-direction)

- **Drives →** ● Every Markdown artifact's quality floor across every host project (purpose-driven structure, sentence-level justification, precision over politeness, active-voice construction, hedge-elimination). ● Every documentation page, ADR, RFC, runbook, README, CONTRIBUTING, CHANGELOG entry. ● The frontmatter validation surface at the hooks pipeline PreToolUse Write hook (the hook enforces non-empty `description` on rules / skills / agents / commands). ◐ The link discipline at every cross-rule citation in the ecosystem.
- **Satisfies →** ● the fifteen-mandate registry row **M13 — Code Craft** at the Markdown per-language tier. ● the rules registry row "Code Craft — Markdown".
- **Established by ↑** ● the fifteen-mandate registry (ratifies M13). ● The CommonMark and GitHub Flavored Markdown specifications (the upstream syntax standards). ● `markdownlint` rules catalog and `vale` style inventories (the upstream prose-linter rulebooks this rule projects).
- **Gated by ←** ● The path-filter (`*.md`, `*.markdown`) — this rule activates only on Markdown-language artifact touches. ● the trivial-vs-non-trivial threshold (trivial-scope Markdown edits run an abbreviated check covering link-resolution and frontmatter-presence only).
- **Cross-bound with ↔** ↔ `rules/code-craft-conventions.md` (universal-delegation stub yields to this rule when the artifact's path matches; the universal floor M13.1–M13.11 is materialized here in prose idioms). ↔ `rules/code-craft-python.md` + `rules/code-craft-shell.md` (sibling per-language code-craft rules — code blocks in Markdown delegate to these per the §7 fenced-block discipline; consistent body shape across the trio). ↔ `rules/clean-room-generation.md` §5 Prose and Documentation (this rule is the per-language projection of §5; sentence-level justification, precision over politeness, active-voice construction are inherited from §5.1–§5.4). ↔ `rules/definitiveness.md` (M8 — hedge-elimination discipline applies in full to Markdown prescriptive prose). ↔ `rules/large-file-generation.md` (CM-23 — long-Markdown incremental-generation protocol). ↔ `rules/visual-leverage.md` (M9 — diagram + prose pairing inside Markdown structural artifacts). ↔ `rules/authoritative-referencing-quotation.md` (§6 link / citation discipline carries the attribution this companion requires). ↔ `rules/host-discovery-manifests.md` (per-language code-craft rules consume the per-language manifest discoveries). ↔ `rules/production-ready-prs.md` (M13 — code-craft sub-elements feed into the same-change-set tests / docs requirements). ↔ `rules/ten-dimension-check-dimensions.md` (↔ reciprocal of the peer's Cross-bound citation).
