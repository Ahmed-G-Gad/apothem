---
name: "ui-design"
version: "0.1.0"
updated: "2026-10-24"
description: "Design or refine a user interface to a craft floor. Matched when the user asks to 'design a page', 'build a landing page, dashboard or form', 'improve this UI', 'make it look better', or 'pick a palette and type scale'. Classifies the surface, applies ranked rules, keeps DESIGN.md current."
archetype: "authoring-template"
user-invocable: true
argument-hint: "[surface or page] [--variance conventional|balanced|distinctive] [--motion none|subtle|expressive] [--density airy|comfortable|compact]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep, WebSearch"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Design a new interface, or refine an existing one, so that it meets a stated brief and a fixed quality floor. The skill fixes four things before any markup is written: the surface class, the dial settings, the project's design context in `DESIGN.md`, and the rule priorities that decide conflicts. It then runs one loop, brief, shape, build, refine, and ends with the pre-delivery checklist.

## Detection Signal

The user asks to design, lay out, restyle, or improve a page, screen, component, dashboard, form, landing page, or document layout; asks for a colour palette, type scale, or spacing system; or says an interface looks cramped, dated, or hard to use.

**Falsifiable counter-signal.** A request to fix application logic, an API, or a data query behind the interface is NOT a match. A request to critique an interface without changing it belongs to the `design-critic` subagent, not to this skill.

## Non-Goals

- **Not a brand-identity studio.** Names, logos, and brand strategy come from the user; the skill consumes them as tokens.
- **Not a framework tutor.** It states the design decision and builds in the framework the project already uses.
- **Not a reviewer.** Independent critique of a finished interface belongs to the `design-critic` subagent; this skill checks its own output against the floor only.

## Workflow

### 1. Brief

Restate the brief in four lines: who uses the surface, the one job it must do, the constraints (framework, devices, deadline, existing brand), and what success looks like. Read `DESIGN.md` if the project has one; search for it with Glob before assuming it does not exist. If the brief and the project context disagree, the brief wins and the difference is stated. Missing facts that change the design go to structured inquiry.

### 2. Classify and set the dials

Pick exactly one surface class from `references/surface-classes.md`: persuade, operate, read, or experience. The class sets the priorities and the default dials. Report the three dials, variance, motion, density, with their values and say which came from the user and which from the class default. Defaults are stated, never assumed silently.

### 3. Shape

Before code, settle three things in prose or a short outline: the layout and reading order, the visual hierarchy (what is primary, secondary, quiet), and every state each component can be in: default, hover, focus, active, disabled, loading, empty, error, success. A screen with only a happy-path state is not shaped.

### 4. Build

Build with the rule catalog in `references/rule-catalog.md`. Categories are ranked; a higher category wins any conflict with a lower one, and the loser is adjusted, not dropped. Take colours, type, spacing, and components from `DESIGN.md` tokens; introduce a new token only when no existing one fits, and add it to `DESIGN.md` in the same change. Use real content lengths, not placeholders. A page may override a project default only locally, with a comment at the override stating what it overrides and why.

### 5. Refine

Refinement preserves what already works: keep the structure, tokens, and wording the user did not ask to change, and change the smallest thing that meets the new brief. Replace a design wholesale only when the brief itself changed, and say so before doing it. After each pass, re-run the checks that the edit could have broken.

### 6. Record and deliver

Update `DESIGN.md` from `references/design-md-template.md`: new tokens, new components, decisions with their reasons. If the project has none and the user agrees, create it at the project root unless host discovery per `rules/host-discovery.md` finds an established location for design context. Then complete `references/pre-delivery-checklist.md` and report the result per the Return Contract.

## Craft floor

Verify before calling any interface done:

- Text and interface contrast meet the catalog thresholds, in every theme shipped.
- Every interactive element shows a visible focus state and is reachable and operable by keyboard alone.
- Empty, loading, and error states exist and were seen, not assumed.
- Layout survives the longest and shortest real content, and a narrow viewport.
- Motion respects the reduced-motion preference.

Refuse to ship:

- Placeholder text such as lorem ipsum in a delivered interface.
- Meaning carried by colour alone.
- Icon-only buttons without an accessible name.
- Layout that shifts while the page loads.
- Text rendered inside images.

## Missing lookups

Use the search tool for an outside palette, font, or pattern reference only when the brief calls for one. When a search for an asset, palette, font, or pattern returns nothing, or the tool is unavailable, say so and say that defaults were used. A value that was invented is never presented as sourced, and a font or image is never claimed licensed without a license record.

## Return Contract

| Field | Content |
|-------|---------|
| `class` | The surface class and why |
| `dials` | Variance, motion, density, each marked user-set or default |
| `changes` | Files created or edited, and the tokens added to `DESIGN.md` |
| `overrides` | Local deviations from project defaults, with reasons, or `none` |
| `checklist` | Each pre-delivery item as pass, fail, or not checked, with how it was checked |

An item marked `not checked` names the reason. A delivery with an unexplained gap in this table is non-conformant.

## Foundational Stanzas

### Refusal & Escalation

REFUSE work outside interface design, such as changing business logic, and REFUSE to ship anything on the refuse list. Name what was declined and the boundary it crossed, then offer the next step through the structured-inquiry channel per `rules/interactive-questions.md`.

### Output Surface

Interface source lands in the project's own source tree and `DESIGN.md` at the location the host uses for design context; the Return Contract table is the closing report. The skill holds read and search tools only, so files are written through the host's normal editing path. Planning notes stay under `<project-root>/.apothem/plans/`.

### File-Authoring Contract

Each new source file carries the canonical header through `scripts/inject-header.py`; exempt classes are listed in `src/apothem/schemas/header-exceptions.txt`. Edits to an existing file keep its existing header.

### Structured Inquiry on Ambiguity

Brand identity, target audience, supported devices, framework, and accessibility target are discovered per `rules/host-discovery.md` or asked through the structured-inquiry channel per `rules/interactive-questions.md`; they are never guessed.

## Recommended Next Step

**Review the delivered interface in a real browser at a phone width and a desktop width**, using only the keyboard for one full pass, then commit the interface and its `DESIGN.md` update together.

## Bindings (§0.j five-direction)

- **Drives →** ● Every interface this skill designs or refines. ● The `DESIGN.md` entries that later work reads as design context.
- **Satisfies →** ● `CLAUDE.md` Source Layout row for the skills/ class. ● The craft-floor verify and refuse lists in `rules/code-craft-ui.md`.
- **Established by ↑** ● `CLAUDE.md` Ambiguity Handling (structured inquiry over invention). ● `skills/README.md` (this skill's index entry).
- **Gated by ←** ● A statable brief. ● The harness's Read, Glob, Grep, and search surface for discovering project context.
- **Cross-bound with ↔** ↔ `rules/code-craft-ui.md` (the short rule form of the floor and priorities). ↔ `rules/host-discovery.md` (design context is discovered). ↔ `rules/interactive-questions.md` (the inquiry channel). ↔ `agents/design-critic.md` (the independent critique of an interface this skill delivers).
