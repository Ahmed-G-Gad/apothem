---
trigger: glob
description: "Path-filtered companion sub-rule to code-craft-conventions.md: the user-interface craft floor for component, markup and style files. Fixes the category priority order, a verify list and a refuse list for any UI change, and requires stated defaults in place of invented sourced values."
globs: "**/*.tsx, **/*.jsx, **/*.vue, **/*.svelte, **/*.css, **/*.scss, **/*.html, **/components/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Code Craft — UI (Companion Sub-Rule)

## Purpose

Hold a minimum standard on every edit to interface source: components, templates, markup and stylesheets. The parent `rules/code-craft-conventions.md` supplies host discovery and the M13 floor; this rule adds what only an interface can get wrong. It stays short because it loads on each matching file. The `ui-design` skill carries the full procedure: scope and genre, the ordered pipeline, and the banded rule catalog.

## Obligations

### 1. Category priority

When two concerns conflict, the earlier category in this list wins:

1. Accessibility
2. Touch and pointer targets
3. Performance
4. Layout and responsiveness
5. Typography and color
6. Motion
7. Forms
8. Navigation
9. Data display

A change that trades a higher category for a lower one MUST say so in its summary.

### 2. Verify before calling a UI change done

The author MUST check each item against the rendered result or, when nothing can be rendered, against the source, and report which method was used:

- Text and interactive-control contrast meets WCAG AA or the host's stated target, whichever is stricter (the `ui-design` catalog's `acc-01`).
- Every interactive element shows a visible focus state.
- Empty, loading and error states exist for each view that fetches or lists data.
- Layouts hold at the longest and shortest real content the field can carry, not only at the sample string, and at a narrow viewport.
- Every control is reachable and operable from the keyboard, in a logical order.
- Animation and transitions honor the reduced-motion preference.

### 3. Refuse

The author MUST NOT ship any of the following in code the change adds or edits:

- placeholder or lorem text in a shipped view;
- meaning carried by color alone;
- icon-only buttons without an accessible name;
- elements that load without reserved space and shift the layout;
- text rendered inside images;
- a faked success state, shown without the work behind it;
- invented proof: figures, quotes, customers, logos or awards the user did not supply.

An instance in code the change does not touch is reported in the summary, not rewritten unasked.

The `ui-design` rule catalog holds the items in §2 and §3 as baseline rules: `acc-01`, `acc-02`, `acc-03`, `acc-04`, `acc-06`, `acc-08`, `acc-09`, `lay-01`, `lay-02`, `lay-08`, `prf-01`, `img-01`, `cpy-01`, `cpy-02`, and `cpy-08`.

The catalog's accessibility rows cover the WCAG 2.2 level A and AA criteria the skill's interfaces meet. Each row states its own threshold, and a row that goes beyond WCAG says so. Pointer targets meet the SC 2.5.8 floor (`tgt-01`). Every drag action also works by single clicks or taps (`tgt-03`). Every path-based or multipoint gesture also works with a single pointer (`tgt-02`, gestures only). Rows `acc-12`, `acc-13`, and `acc-14` cover single-key shortcuts, focus hidden by sticky chrome, and text spacing. Rows `acc-15` to `acc-20` cover content on hover or focus, flashing, timing, consistent help, redundant entry, and accessible authentication. Rows `acc-21` to `acc-30` cover skip links, input purpose, audio description, link purpose and headings, context changes, pointer cancellation, reading order, language of parts, consistent navigation, and error prevention. The house hit area, stricter than WCAG, is the habit rule `tgt-04`; its row states its scope and exemptions, including a link inside running text.

### 4. State defaults; never invent sourced values

A palette, font, spacing scale, icon set or pattern lookup MAY return nothing. The author MUST then fall back to the host's design tokens or a plain default, and MUST say that a default was used. A value the author chose MUST NOT be described as taken from a style guide, brand kit or research source it did not come from. Inside a `ui-design` skill run, the rule catalog's section "Scope of taste" governs local overrides, and the next sentence does not apply. In an edit made outside the skill, where the host keeps a design context file (for example `DESIGN.md`), a local override of one of its values MUST carry a comment that names the value it replaces and the reason.

## Enforcement

Path-filtered to the globs in this rule's `pathFilter` field and demand-loaded as the companion to `rules/code-craft-conventions.md` §6. A change that touches a matching file without the verify report, or that matches a refuse entry, is a finding in code review. The `ui-design` skill's baseline rules and pre-delivery checklist are the extended form of §2 and §3.

## Bindings (§0.j five-direction)

- **Drives →** The craft floor on every edit to component, markup and stylesheet files matching the path filter.
- **Satisfies →** `rules/code-craft-conventions.md` §6 Companion Sub-Rule Anchor pointer.
- **Established by ↑** `rules/code-craft-conventions.md` (parent rule; M13 code craft). The `ui-design` skill, whose baseline verify and refuse lists match this rule's §2 and §3, and whose banded rule catalog holds the full baseline.
- **Gated by ←** The path-filter. The parent rule's host-discovery walk, which supplies the host's tokens and contrast target before this rule's checks run.
- **Cross-bound with ↔** `rules/code-craft-conventions.md` (parent rule; the parent cites it back under its own `↔` line).
