---
name: "own-voice-reimplementation"
description: "Every reference-derived feature is reauthored in apothem's own voice with zero verbatim code/text/branding, is demonstrably more elegant and effective than the reference, and cites the relevant harness's own latest official documentation (a convention-pin snapshot dated within the prior 90 days)."
pathFilter: "**/rules/**/*.md, **/commands/**/*.md, **/skills/**/*.md, **/agents/**/*.md, **/site/**/*.md*, **/assets/**"
alwaysApply: false
paths:
  - "**/rules/**/*.md"
  - "**/commands/**/*.md"
  - "**/skills/**/*.md"
  - "**/agents/**/*.md"
  - "**/site/**/*.md*"
  - "**/assets/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Own-Voice Reimplementation — Zero Inheritance, Elevated Beyond, Harness-Doc-Aligned

## What this rule enforces

Every feature, structure, or convention apothem derives from observing a reference platform is **reauthored** in apothem's own voice. Zero verbatim code, text, marketing copy, or branding crosses the boundary — the reimplementation is an independent derivation from understood intent, not a transcription. The reimplementation **MUST** be more elegant, more sophisticated, and more effective than the reference; "as good as" is non-conformant where "better" is reachable. Every reimplemented surface that derives a convention from a harness **MUST** cite that harness's own latest official documentation through its `STANDARD-CONVENTION-PIN.md` — a convention-pin snapshot dated within the prior 90 days.

## Pre-conditions

Applies whenever any apothem surface reimplements a feature, structure, layout, naming scheme, design element, or convention observed in a reference platform. Surfaces authored without reference to any external platform carry no reimplementation obligation — only the standing plain-language and code-craft floors.

## Required behavior

### 1. No-Verbatim Rule

The reimplementation **MUST NOT** copy any byte of the reference's code, prose, marketing copy, branding, color palette, slug, route name, file name, identifier, or naming convention. Every artifact **MUST** be independently derivable from the feature's understood intent — never from the reference's expression of it. Because nothing is copied, **no attribution is triggered**: no inherited authorship to credit, no license obligation, no origin to cite. A reimplementation that would require an attribution line to be lawful has copied something and **MUST** be reauthored from intent.

### 2. Elevation Requirement

The reimplementation **MUST** be demonstrably more elegant, more sophisticated, or more effective than the reference. The author **MUST** name the dimension of improvement — clarity, structural novelty, robustness, performance, accessibility, maintainability, or expressiveness — and state how the apothem surface realizes it. A reimplementation that merely matches the reference on every dimension **SHOULD** be reworked until at least one dimension is elevated; one that paraphrases without elevation is non-conformant.

### 3. Harness-Documentation Pin

Every reimplemented surface that derives a convention from a harness **MUST** cite that harness's `STANDARD-CONVENTION-PIN.md` at `src/apothem/harnesses/<name>/STANDARD-CONVENTION-PIN.md`, and the cited pin's `snapshot-date` **MUST** fall within the prior 90 days. The citing surface **MUST** state the verification recipe: compute the day-delta between today and the pin's `snapshot-date`, confirm `delta <= 90`. A pin older than 90 days **MUST** be refreshed against the harness's latest official documentation before the surface ships; a stale pin surfaces as an advisory finding with the refresh as its next step, and the phase's Definition of Done is not met until the pin is refreshed (CI's `--strict` opt-in enforces the freshness floor mechanically, per the agnostic-posture advisory discipline).

### 4. Worked Before/After Example — Own-Voice Reauthoring

The transformation below demonstrates own-voice reauthoring on a neutral, invented feature concept — a per-session continuous-learning loop. The "reference" column is a paraphrase of *intent only*, carrying none of any real platform's wording or structure; the "apothem own-voice" column is a structurally novel, elevated reimplementation.

| Aspect | Reference (paraphrased intent) | apothem own-voice reimplementation |
|---|---|---|
| **Feature concept** | After each session, the tool records what it learned and reuses it next time. | A **convention-promotion ledger**: confirmed patterns graduate from session-local scratch to a durable, indexed memory tier through an explicit four-field promotion record (`source` / `target` / `date` / `rationale`). |
| **Trigger** | "It learns as you go." | Promotion fires only on a **recurrence threshold** (a pattern observed across distinct sessions), never on a single observation — the threshold is the contract, not an implicit heuristic. |
| **Structure** | A flat log of notes. | A **two-tier topology** (project-scoped + global) with a directional promotion invariant and an auditable ledger, so the learning surface is itself inspectable and reversible. |
| **Elevation dimension** | — | **Structural novelty + auditability**: the apothem version replaces an opaque "it learns" black box with an explicit, reviewable promotion contract — a different mechanism, not a rephrasing of the reference's. |

The apothem column shares **no wording, no data shape, and no naming** with the reference; it solves the same intent (carry forward what proved useful) through an independently-derived mechanism that is more inspectable than the paraphrased reference. This is reauthoring, not paraphrase.

### 5. Standing Definition-of-Done Gate

The mechanical reference-token sweep — gate name **`reference-token-grep`**, anchored at this rule — is a **standing per-phase Definition-of-Done gate**. Every later phase's exit gate **MUST** run it; **zero in-scope hits** is the preserved baseline at every phase boundary. The gate sweeps in-scope authored surfaces (per this rule's `pathFilter`) for any reference brand, slug, author name, or other reference-identifying token. A non-zero in-scope hit count surfaces as an advisory finding with reauthoring as its next step; the phase's Definition of Done is not met until the leaking token is reauthored away, and CI's `--strict` opt-in enforces the zero baseline mechanically. The zero baseline **MUST NOT** be silently relaxed for "just this phase".

### 6. Resolved Placeholders

Two former reference-internal placeholders are **RESOLVED as NOT-NEEDED** under the no-copy discipline; neither **MUST** be silently reconstructed:

- **Exact reference-site palette / typography / logo.** NOT-NEEDED. The project authors an **original design system** — its own palette, type scale, and mark — from its own brand intent, never sampled from a reference site. Capturing the reference's visual tokens would violate §1.
- **Reference config-file bodies.** NOT-NEEDED. Apothem **derives config conventions from each harness's own latest official documentation** (per §3's pin discipline), never from a reference platform's config files. The authoritative source is the harness vendor's documentation, not any reference platform.

Re-introducing either placeholder under a renamed heading is a §1 violation surfaced at the §5 gate.

## Mechanical enforcement

`conformity/reference_token_grep.py` — the reference-token sweep anchored at this rule — enforces the §5 zero-in-scope-hits baseline across this rule's `pathFilter` surfaces. `conformity/plain_language_grep.py` — the sibling user-facing plain-language sweep — enforces the adjacent closed-set forbidden-vocabulary discipline on the same user-facing surfaces. The two matchers run together at every phase exit gate.

## Disclosure surface

Every reimplementation outcome is recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[Reimplementation — surface: <name>; elevation: <dimension>; harness-pin: <snapshot-date>]` for every reauthored surface, naming the elevated dimension and the cited pin's snapshot date.
- `[Reimplementation — placeholder-resolved: <palette-typography-logo | config-bodies>; resolution: not-needed]` for each of the two §6 placeholder resolutions.
- `[Reimplementation — gate: reference-token-grep; in-scope-hits: 0]` for every phase-exit gate run that preserves the baseline.

## Failure tells

A block of code or copy carried verbatim from a reference platform. A reimplementation that restates the reference's feature in fresh words but reuses its structure, naming, or data shape (paraphrase, not reauthoring). A reference brand, slug, or author name leaking into a shipped in-scope surface. A harness-documentation pin whose `snapshot-date` exceeds 90 days cited as current. A design token (palette / type / logo) sampled from a reference site rather than authored originally. A config convention reproduced from a reference platform's config file rather than derived from the harness's own documentation. A silently reconstructed §6 placeholder under a renamed heading.

## Bindings (§0.j five-direction)

- **Drives →** The per-phase zero-leak Definition-of-Done gate (`reference-token-grep`) that every later phase's exit gate runs. The mechanical matcher at `conformity/reference_token_grep.py`. Every reauthored in-scope authored surface under this rule's `pathFilter`.
- **Satisfies →** The own-voice reimplementation mandate (zero verbatim inheritance, mandatory elevation, harness-doc alignment). The product-artifact boundary that keeps shipped surfaces free of reference branding.
- **Established by ↑** The no-copy reimplementation directive. The harness convention-pin discipline at `src/apothem/harnesses/<name>/STANDARD-CONVENTION-PIN.md`.
- **Gated by ←** The `pathFilter` (in-scope authored surfaces only; non-derived surfaces are exempt). The `reference-token-grep` zero-hit baseline at every phase boundary.
- **Cross-bound with ↔** `rules/plain-language.md` (sibling user-facing-vocabulary sweep on the same shipped surfaces). `rules/agnostic-posture.md` (host-agnostic posture; reimplementations derive conventions from each harness's own documentation, not from a single reference). `rules/recommend-next-step.md` (terminal-surface forward-move discipline this rule's tail honors).

## Recommended Next Step

**Proceed to Phase 00D — the `rules/` → `skills/` investigation** to map which reimplementation disciplines belong in path-filtered rules versus detectable-technique skills, per `rules/recommend-next-step.md`.
