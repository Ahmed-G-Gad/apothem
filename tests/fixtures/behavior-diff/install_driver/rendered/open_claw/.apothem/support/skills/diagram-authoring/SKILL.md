---
name: "diagram-authoring"
version: "0.1.0"
updated: "2026-06-14"
description: "Diagram authoring and rendering — matched when the operator asks to 'draw a diagram', 'make a flowchart / sequence / state / ER / architecture diagram', 'author a data visualization', 'render this Mermaid', 'export a diagram to SVG/PNG/PDF', or otherwise needs a structural picture authored and rendered. One deterministic pipeline — pick notation by subject → author source → validate syntax → render → export — spanning declarative diagrams (flowchart / sequence / state / class / ER / gantt / mindmap) and data-driven visualizations (bar / line / scatter / network / hierarchy / geo). Correct-by-construction (validated before render) and portable (SVG / PNG / PDF via a discovered headless renderer). Not for: shipping or assuming a vendor render server (the renderer is discovered, never bundled); fabricating a visualization's dataset (supplied or discovered, never invented); illustrating non-structural prose a paragraph already carries. Harness-agnostic; deterministic output."
archetype: "authoring-template"
userInvocable: true
argument-hint: "[diagram subject] [--notation auto|declarative|data-driven] [--format svg|png|pdf]"
disable-model-invocation: true
allowed-tools: "Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Author a structural picture — a flowchart, sequence, state machine, class / ER model, gantt, mindmap, or a data-driven visualization (bar, line, scatter, network, hierarchy, geographic) — and render it to a shareable image through one deterministic pipeline:

**pick the notation from the subject → author the source → validate the syntax → render → export.**

The skill unifies declarative diagram authoring and data-driven visualization behind a single procedure and a single validate-then-render contract, so a diagram is **correct-by-construction** (validated before render) and **portable** (exported to SVG / PNG / PDF) regardless of which notation the subject called for.

## Detection Signal

The operator asks to "draw / author a diagram", names a diagram class (flowchart, sequence, state, class, ER, gantt, mindmap, architecture), asks for a "data visualization" / "chart" / "graph" of a dataset, asks to "render" diagram source to an image, or asks to "export" a diagram to a file format. A request to embed a diagram inside a structural document also routes here (the `document-authoring` skill consumes this skill's render output).

## Non-Goals

- **Not a bundled rendering server.** A deterministic procedure that invokes whatever diagram renderer the host makes available (a headless diagram CLI, a headless browser, or a render service in the MCP inventory) — it ships or assumes no specific vendor's server. The renderer is discovered, not bundled.
- **Not a notation monoculture.** It selects the right notation for the subject — declarative diagram grammar for relationship / flow / state pictures, a data-viz grammar for quantitative pictures — never forcing one notation onto every subject.
- **Not an unvalidated emitter.** Diagram source is syntax-validated before render; a render of invalid source is a failure surfaced with the offending construct, not a silently-broken image.

## Conformity Posture

- **Discover-don't-assume preamble (M1).** Discover the host's available diagram renderer and its invocation (a headless diagram CLI on PATH, a headless browser, or an MCP-registered render service) per `rules/host-discovery.md`, and the host's diagram-asset directory convention. Record each with provenance. The renderer is never assumed — it is discovered, and where absent the gap is surfaced.
- **Visual-leverage alignment (M9).** Authored diagrams carry the provenance + `verified:` date metadata per `rules/visual-leverage.md`, so the picture reflects current reality, not aspirational or stale state.

## Procedure

### 1. Frame the Subject & Pick the Notation

Read the subject and classify it:

| Subject class | Notation family | Members |
|---------------|-----------------|---------|
| relationship / flow / state / structure | declarative diagram grammar | flowchart, sequence, state, class, ER, gantt, mindmap |
| quantitative / dataset | data-viz grammar | bar, line, scatter, network, hierarchy, geographic |

Under `--notation auto` (default) the classification is by subject; when ambiguous, inquire. Record the chosen notation and why.

### 2. Author the Diagram Source

Author the source in the chosen notation, derived from the subject's intent (the structure to depict, the data to plot). For data-driven visualizations, bind the supplied / discovered dataset to the visual encoding (axes, scales, marks, color) **deterministically** — the same dataset produces the same picture. Keep the source human-readable and diffable (text source over binary where the notation permits).

### 3. Validate Before Render

Validate the source syntax before any render — parse the declarative grammar or the data-viz spec. On a parse error, surface the offending construct and halt; never render invalid source into a broken image. This validate-then-render contract is the skill's robustness floor.

### 4. Render & Export

Render the validated source to an image via the discovered renderer; export to the requested `--format`:

- **SVG** (default) — scalable, diffable.
- **PNG** — raster embedding.
- **PDF** — print.

When the render reports a *recoverable* error (a layout overflow, an unsupported construct), apply **one** corrective pass (adjust the construct → re-validate → re-render) before surfacing failure — a bounded validate→correct→re-render loop, never unbounded retry.

### 5. Self-Check & Emit

Attach the provenance + `verified:` metadata. Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the emitted source + image. Emit the diagram source, the rendered image, and the single recommended next move.

## Arguments

- `[diagram subject]` — the structure or dataset to depict, in natural language.
- `--notation auto|declarative|data-driven` — notation family (default: `auto`, classified by subject).
- `--format svg|png|pdf` — export format (default: `svg`).

## Return Contract

The diagram **source** (text, diffable, with provenance + `verified:` metadata), the rendered **image** at the chosen format, the **notation choice + rationale**, and a single `## Recommended Next Step`. Deterministic per `rules/determinism.md`: the same subject + dataset + notation produces byte-stable source and a reproducible render. The rendered binary's exact bytes may vary with the discovered renderer version — the declared non-deterministic element, stamped with the renderer + version.

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any request beyond authoring and rendering a diagram — name what was refused, name the boundary crossed, surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE emitting an image from source that failed syntax validation — surface the validation error and the offending construct instead. When the subject is ambiguous between two notations, surface the choice; never guess.

### Output Surface

Diagram source and rendered images land at the operator's chosen location (a structural document's asset directory, a plan suite's working surface, or an operator-named path) per host-discovery and the suite-locality invariant at `rules/context-management.md` §2.6.1. Diagram source carries a provenance + verification-date comment per `rules/visual-leverage.md` so the rendered picture is auditable against the reality it abstracts. Per CM-7, the diagram describes its subject in natural domain language.

### File-Authoring Contract

Diagram-source files (a `.mmd` / `.svg` / data-viz spec) authored as host-project artifacts route through `scripts/inject-header.{sh,py}` where the filetype carries a header variant; rendered binary images (`.png` / `.pdf`) are header-exempt per `src/apothem/schemas/header-exceptions.txt`. Edits preserve any existing banner; the header-inject-guard hook enforces the contract.

### Structured Inquiry on Ambiguity

When the notation, the diagram class, the dataset shape, the target format, or the rendering surface is ambiguous, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. NEVER fabricate the data a visualization plots — the dataset is supplied or discovered, never invented.

## Recommended Next Step

**Invoke the `diagram-authoring` skill via the Skill tool** with `<subject> --notation auto --format svg` — review the validated source and the rendered SVG, then embed the source (not just the image) in the consuming document so the picture stays diffable and re-renderable. Re-run with `--notation` set explicitly when the subject spans both a structural and a quantitative view.

## Bindings (§0.j five-direction)

- **Drives →** ● Every authored-and-rendered diagram across the host's structural artifacts. ● The validate-then-render contract that gates every image emission. ◐ The document-authoring skill, which consumes this skill's render output for embedded figures.
- **Satisfies →** ● `CLAUDE.md` Source Layout row "diagram-authoring" (skills/ class). ● The elevation dimension **structural novelty** (one unified author→validate→render→export pipeline across declarative + data-driven notation — a shape no single source capability carries alone). ● `rules/visual-leverage.md` (M9 diagram provenance + verification-date discipline).
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ folder-with-`SKILL.md` class). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication). ● `rules/own-voice-reimplementation.md` (zero-verbatim own-voice; `reference-token-grep` = 0). ● `rules/agnostic-posture.md` (17-harness agnostic floor).
- **Gated by ←** ● A discovered diagram renderer (the gap is surfaced where absent). ● The host's structured-inquiry + Edit + Write + Bash tool surface. ● A statable subject (and, for data-viz, a supplied / discovered dataset — never invented).
- **Cross-bound with ↔** ↔ `rules/visual-leverage.md` (M9 — provenance + `verified:` metadata; this skill is the authoring instrument for the diagrams that rule mandates). ↔ `rules/own-voice-reimplementation.md` + `rules/agnostic-posture.md` (own-voice + agnostic floors). ↔ `rules/determinism.md` (deterministic pipeline). ↔ `skills/document-authoring/SKILL.md` (sibling own-voice authoring skill; consumes this skill's render output for embedded figures).
