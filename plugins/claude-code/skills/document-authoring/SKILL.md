---
name: "document-authoring"
version: "0.1.0"
updated: "2026-10-02"
description: "Long-form structured-document authoring — matched when the operator asks to 'write a thesis / dissertation / paper / report', 'author a LaTeX document', 'build a document from an outline', 'compile this to PDF', 'manage citations / bibliography', or otherwise needs a long, citation-bearing, typeset document produced. Drives an approval-gated hierarchical pipeline (outline → operator-approve → draft → review), verifies every citation against a real retrievable source (never fabricated — unresolvable references land in an unverified-citations ledger), and compiles through a deterministic detect→route pipeline that inspects the source, selects engine / bibliography tool / index passes by rule, and self-corrects one recoverable build error before surfacing failure. Figures route to diagram-authoring. Not for: a short prose snippet or single-paragraph rewrite (ordinary prose authoring, below threshold); fabricating a citation to fill a gap; rendering figures. Harness-agnostic; deterministic output."
archetype: "authoring-template"
userInvocable: true
argument-hint: "[document subject] [--kind thesis|paper|report|book] [--format latex|markdown]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep, WebSearch, TodoWrite"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Produce a long-form, citation-bearing, typeset document — a thesis, dissertation, paper, report, or book — through an approval-gated hierarchical pipeline (outline → operator-approve → draft → review) under two invariants:

- **Honest citation** — every reference resolves to a real, retrievable source, or it lands in the unverified-citations ledger; none is invented.
- **Deterministic compile** — the compile step inspects the source, *detects* which engine / bibliography tool / index passes the source requires, and *routes* them by rule, not by guess.

Figures are authored and embedded through `diagram-authoring`. The result is robust by construction: the document compiles cleanly because the pipeline detected and satisfied its build requirements, and it cites honestly because every reference was verified.

## Detection Signal

The operator asks to write a thesis / dissertation / paper / report / book, author a LaTeX (or Markdown) document, build a document from an outline, compile a document to PDF, or manage a citation / bibliography surface. A short prose snippet or a single-paragraph rewrite is below this skill's threshold — that is ordinary prose authoring, not the long-form structured-document pipeline.

## Non-Goals

- **Not a citation fabricator.** Every reference is verified against a real, retrievable source (a supplied bibliography, a discovered citation database, or a resolvable DOI / URL). A reference that cannot be verified is surfaced as unverified — never invented to fill a gap.
- **Not a blind compiler.** The compile step detects the source's build requirements (engine, bibliography tool, index, special packages) and routes them deterministically; it does not run one fixed toolchain blindly and hope.
- **Not an unapproved drafter.** At thesis / dissertation scale, the outline is approved before prose is drafted (approval-gated), so the operator's structure governs — the skill does not draft a 200-page document off an unconfirmed outline.
- **Not a figure renderer.** Figures route to `diagram-authoring`; this skill composes them into the document, it does not reimplement diagram rendering.

## Conformity Posture

- **Discover-don't-assume preamble (M1).** Discover the host's document toolchain (typesetting engine, bibliography tool, citation database) and its invocation per `rules/host-discovery.md`, plus the host's document conventions (citation style, template layout). Record each with provenance. The toolchain is discovered, not assumed; where absent, the gap is surfaced.
- **Authority-inquiry surface (M5).** Citations are authoritative data — discovered or supplied, never invented, per `rules/authority-inquiry.md`.

## Procedure

### 1. Frame & Outline (approval-gated)

Read the subject and document kind. Author a hierarchical outline (document → chapter / section → subsection) and **surface it for approval** through the structured-inquiry channel before drafting prose. The approved outline is the contract every drafted section traces back to — plan-compliance is checked at review.

### 2. Discover Toolchain & Citation Source

Discover the typesetting engine, bibliography tool, citation style, and citation source the document requires (and the host provides). Record with provenance. The compile requirements are derived from the source's features, not assumed.

### 3. Draft Against the Outline

Draft each section against the approved outline. Bind every claim that needs support to a **verified citation** — resolve each reference to a real source (supplied bibliography, discovered database, resolvable DOI / URL); an unresolvable reference is marked unverified, never fabricated. Author figures through `diagram-authoring` and compose them into the document.

### 4. Deterministic Compile (detect → route)

Compile through a detect-then-route pipeline that routes the build *by rule*:

- select the **engine** from the source's typesetting features;
- select the **bibliography tool** from the reference-declaration form;
- run an **index pass** where the source declares an index;
- inject the **corrective package** where a known layout warning is detected;
- run the **multi-pass build** with cross-reference validation.

On a recoverable build error (a missing label, an undefined reference, a layout overflow), apply **one** corrective pass (fix the construct → re-validate → re-compile) before surfacing failure — a bounded detect→correct→recompile loop, never unbounded retry.

### 5. Review & Self-Check

Review the compiled document against the approved outline (plan-compliance), verify cross-references resolve, verify every citation is verified-or-flagged, and run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md`. Emit the document source, the bibliography, the compiled artifact, the unverified-citations ledger (if any), and the single recommended next move.

## Arguments

- `[document subject]` — the document's subject / thesis statement in natural language.
- `--kind thesis|paper|report|book` — the document kind (default: inferred from subject, confirmed via inquiry).
- `--format latex|markdown` — the source format (default: `latex` for typeset output; `markdown` for lightweight).

## Return Contract

- the document **source**;
- the **bibliography**;
- the compiled **artifact** (PDF where typeset);
- the **unverified-citations ledger** (every reference that cannot be verified, with the gap);
- the **compile-route record** (detected engine / bib-tool / passes, with provenance);
- the fifteen-bar gate attestation;
- a single `## Recommended Next Step`.

Deterministic per `rules/determinism.md`: the same outline + content + toolchain produces byte-stable source. The compiled binary's exact bytes may vary with the discovered engine version — the declared non-deterministic element, stamped with the engine + version.

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any request beyond authoring a structured document — name what was refused, name the boundary crossed, surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE asserting a citation as verified when its source cannot be retrieved — it lands in the unverified-citations ledger with both the claim and the gap. REFUSE drafting full prose at thesis scale before the outline is approved.

### Output Surface

The document source, its bibliography, and the compiled artifact land at the operator's chosen location per host-discovery and the suite-locality invariant at `rules/context-management.md` §2.6.1. Document source carries natural domain language describing its subject (CM-7) — zero apothem-internal scaffolding.

### File-Authoring Contract

Document-source files authored as host-project artifacts (`.tex` / `.md` / `.bib`) route through `scripts/inject-header.{sh,py}` where the filetype carries a header variant; compiled binary artifacts (`.pdf`) are header-exempt per `src/apothem/schemas/header-exceptions.txt`. Edits preserve any existing banner; the header-inject-guard hook enforces the contract.

### Structured Inquiry on Ambiguity

When the document kind, the target structure, the citation style, the bibliography source, or the compile toolchain is ambiguous, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). The outline-approval gate is itself an inquiry. NEVER fabricate a citation or a domain fact.

## Recommended Next Step

**Invoke the `document-authoring` skill via the Skill tool** with `<subject> --kind <thesis|paper|report|book>` — approve the hierarchical outline when surfaced, then review the compiled artifact and resolve every entry in the unverified-citations ledger before circulating the document. Re-run after outline edits to re-derive only the affected sections.

## Bindings (§0.j five-direction)

- **Drives →** ● Every long-form structured document authored across the host. ● The verified-citation contract that gates every reference. ● The deterministic detect→route compile pipeline. ◐ Embedded figures, delegated to `diagram-authoring`.
- **Satisfies →** ● `CLAUDE.md` Source Layout row "document-authoring" (skills/ class). ● The elevation dimension **robustness** (detection-signal-driven compile pipeline + citation verification — failure modes handled by rule, not retry-and-hope). ● `rules/authority-inquiry.md` (citations verified, never invented).
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ folder-with-`SKILL.md` class). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication). ● `rules/own-voice-reimplementation.md` (zero-verbatim; `reference-token-grep` = 0). ● `rules/agnostic-posture.md` (17-harness agnostic floor).
- **Gated by ←** ● A discovered document toolchain (the gap is surfaced where absent). ● The outline-approval gate (no full draft before approval). ● The host's structured-inquiry + Edit + Write + Bash tool surface.
- **Cross-bound with ↔** ↔ `skills/diagram-authoring/SKILL.md` (figures are authored + rendered there and composed here). ↔ `rules/own-voice-reimplementation.md` + `rules/agnostic-posture.md` (own-voice + agnostic floors). ↔ `rules/authority-inquiry.md` (citation verification). ↔ `rules/determinism.md` (deterministic pipeline). ↔ `skills/dev-toolkit/SKILL.md` + `skills/surgical-guard/SKILL.md` (sibling own-voice engineering skills).
