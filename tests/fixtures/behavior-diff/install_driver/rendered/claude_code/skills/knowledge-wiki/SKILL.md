---
name: "knowledge-wiki"
description: "Adds sources to and audits an index-first Markdown knowledge base, when the user asks to 'add this paper to the wiki', 'ingest these sources', 'lint the wiki' or 'what changed in the knowledge base'. Modes: ingest, lint, drift, hubs. Not source discovery or a one-off summary."
user-invocable: true
argument-hint: "[--mode ingest|lint|drift|hubs] [--kb PATH] [--source PATH_OR_ID] [--focus QUESTION]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-24"
  archetype: "research-template"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Keep a project's knowledge base as plain Markdown pages that a reader can navigate from one index file and trust page by page. Each source is read under a stated focus, the claims it supports are filed as pages with typed relations, and a deterministic lint plus a drift report show whether the base still holds together. Page shapes are in [`references/page-templates.md`](references/page-templates.md), the lint checks in [`references/lint-catalog.md`](references/lint-catalog.md), and the drift and hub procedures in [`references/drift-and-hubs.md`](references/drift-and-hubs.md).

## Detection Signal

The user asks to add a source to the project wiki or knowledge base, to check the base for broken structure, to see what changed in it since last time, or to find the pages it depends on most.

**Falsifiable counter-signal.** A one-off summary of a document, a citation-format conversion, or a question about the code itself is NOT a match: no knowledge-base page is read or written.

## Non-Goals

- **Not source discovery.** It files sources the user names; finding new literature belongs to `skills/multi-source-research/SKILL.md`.
- **Not a cross-source synthesis for one question.** That is `skills/source-synthesis/SKILL.md`; a synthesis page here stores such a result, it does not derive it.
- **Not a fact-checker.** It records what a source says and how much of it was read; it does not rule on whether the source is right.
- **Not a repair tool.** Lint reports findings; fixes are made on request, one finding class at a time.

## Workflow

### 0. Resolve the base (every mode)

1. Take `--kb PATH`, else Glob for a directory that holds both `index.md` and `log.md`. Exactly one hit is the base. Several hits, or none, go to the structured-inquiry channel; in `ingest` mode, creating a new base is one option, with `knowledge-base/` under the project root as the recommended default and a user-named path as the alternative. Never choose a location silently. The session-start check watches only a base at `knowledge-base/`, `wiki/`, `docs/knowledge-base/`, or `docs/wiki/`; a base elsewhere works in every mode but gets no session-start line.
2. Read `index.md` in full and the last 20 lines of `log.md`. Take the mode from `--mode`, else from the request wording; if two modes fit, ask.

### Mode `ingest`

1. **Fix the focus.** Take `--focus`, else ask for the question being put to this source. A source with no focus is not ingested.
2. **Open the source.** Take it from `--source`, else from the request. Read it and record the basis honestly: `full-text`, `abstract-only`, or `excerpt` with the portion named. A source that cannot be opened (paywall, dead link, unreadable file) gets no focus block; file a stub page with status `unread`, log it, and report it. Reachability handling follows `rules/source-accessibility.md`.
3. **Match before creating.** Grep the index and the pages for the source's cite key, DOI, and title. A hit means append a new focus block `F<n+1>` to the existing page and leave earlier blocks untouched; a hit on an `unread` stub sets its status to `active` and writes `F1`, and a hit on a redirect stub is followed to its target. A focus that repeats an existing block is skipped and reported.
4. **Write the claims.** One line per claim. Record a locator only if the page, section, or line was seen while reading; otherwise write `locator: none seen`. Never estimate a locator.
5. **File entities and relations.** For each entity the source bears on, update or create `entities/<id>.md`. A relation line names one of `supports`, `contradicts`, `extends`, `uses`, `part-of`, a confidence of `high`, `medium`, or `low`, and the source block it came from. A relation with no block is not written. Each factual sentence on an entity page ends with a block citation. Synthesis pages are written only on request, from claims already filed; when an ingest adds evidence to an existing one, add an `Evidence` line and say if its `Answer so far` no longer follows.
6. **Apply the hard stop.** A claim attributed to a source that has no focus block (never opened, or known only through another source's citation) is written in running text as `[unverified: <reason>]`. It is never a typed relation and never a bare statement of fact. Clearing a marker takes an opened source and a new focus block; `agents/fact-checker.md` can test a single claim against sources.
7. **Keep the index and the log.** Add one line per new page to `index.md` and append one line per change to `log.md`: `create` for a new page, `ingest` for a focus block, `update` for an edit to an existing entity or synthesis page. IDs are kebab-case, unique across all page kinds, and never reused; a rename leaves a redirect stub at the old ID.
8. **Check the touched pages.** Run lint checks L1 to L4, L6, and L8 on them and fix whatever the ingest itself broke.

### Mode `lint`

Run every check in the lint catalog with Glob and Grep, in catalog order, over the whole base. A check that cannot run (no bibliography file, no drafts location) is reported as skipped with the reason, never as passed. Edit no pages in this mode.

### Mode `drift`

Compare the stored fingerprint with the current one as set out in the drift-and-hubs reference. No baseline in `log.md` means record one and print nothing else. A matching fingerprint means print one line saying nothing changed, then stop. A differing fingerprint produces the drift report, followed by a new baseline entry. The stored fingerprint is the newest `baseline` line in `log.md`; the session-start hook reads that same line and, when the fingerprint no longer matches, adds one line that points here. Only this mode writes a baseline, so the line repeats each session until the mode has run.

### Mode `hubs`

Count distinct inbound links per page and test the high-degree pages as bridges, following the drift-and-hubs reference. Report; do not restructure.

## Return Contract

| Mode | Output |
|------|--------|
| `ingest` | Pages created and appended (path, focus block, basis), claims marked unverified, stubs for unopened sources, log lines added, and the L1 to L4, L6, and L8 result for touched pages |
| `lint` | Findings grouped by check ID with `path:line`, the count per check, the checks skipped and why, and the unverified-claim inventory |
| `drift` | One line for a recorded baseline, one line for no change, or the report: log entries since the baseline, pages added, renamed, or retired, and focus blocks added |
| `hubs` | Most-linked pages with inbound counts, bridge pages with the clusters each one joins, and any restriction applied to the bridge test |

Every report names the base path and the date it was produced. A report that leaves out the skipped or restricted parts of its own run is non-conformant.

## Foundational Stanzas

### Refusal & Escalation

REFUSE to write a claim as fact when its source was not opened, to estimate a page or section locator, to overwrite or reorder an earlier focus block, to reuse a retired ID, or to edit pages during `lint`, `drift`, or `hubs`. Name the refused action and the boundary it crossed, then offer the compliant alternative through the structured-inquiry channel per `rules/interactive-questions.md`.

### Output Surface

Reports write to STDOUT. Page and log writes land only inside the resolved base, through the host's normal file-edit permission flow. Planning artifacts go to `<project-root>/.apothem/plans/`, never into the base.

### File-Authoring Contract

A NEW page follows the templates in the page-templates reference, with front matter at byte 0. Where the host project requires an authorship header on Markdown files, route the new file through `scripts/inject-header.py`; exempt classes are listed in `src/apothem/schemas/header-exceptions.txt`. Edits to an existing page preserve its header.

### Structured Inquiry on Ambiguity

Base location, the focus question, the ID chosen on a title collision, and the confidence of a relation a source only implies are decisions the user owns. Route them through the structured-inquiry channel per `rules/interactive-questions.md` with a recommended default; discover per `rules/host-discovery.md`, never invent.

## Recommended Next Step

**Run `lint` after each ingest batch** and resolve blocking findings before ingesting further; run `drift` at the start of the next working session to see what moved.

## Bindings (§0.j five-direction)

- **Drives →** ● Every page, focus block, relation line, and log entry written into a knowledge base. ● Every lint, drift, and hub report this skill emits.
- **Satisfies →** ● `CLAUDE.md` Source Layout row for the skills/ class. ● The research cohort's durable source-and-claim record surface.
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ class declaration with the folder-with-`SKILL.md` convention). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication).
- **Gated by ←** ● The harness's Read / Glob / Grep surface and its file-edit permission flow. ● A resolvable base, or the user's answer on where to create one.
- **Cross-bound with ↔** ↔ `rules/authoritative-referencing.md` (a claim cites its source or is marked unverified). ↔ `rules/source-accessibility.md` (unreachable sources become stubs). ↔ `rules/host-discovery.md` (the base is discovered). ↔ `rules/interactive-questions.md` (the inquiry channel). ↔ `skills/source-synthesis/SKILL.md` + `skills/multi-source-research/SKILL.md` (sibling research skills). ↔ `agents/fact-checker.md` (the verification surface for unverified claims).
