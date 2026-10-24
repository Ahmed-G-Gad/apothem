---
name: "code-craft-ui"
description: "Path-filtered companion sub-rule to code-craft-conventions.md: the user-interface craft floor for component, markup and style files. Fixes the category priority order, a verify list and a refuse list for any UI change, and requires stated defaults in place of invented sourced values."
pathFilter: "**/*.tsx, **/*.jsx, **/*.vue, **/*.svelte, **/*.css, **/*.scss, **/*.html, **/components/**"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Code Craft — UI (Companion Sub-Rule)

## Purpose

Hold a minimum standard on every edit to interface source: components, templates, markup and stylesheets. The parent `rules/code-craft-conventions.md` supplies host discovery and the M13 floor; this rule adds what only an interface can get wrong. It stays short because it loads on each matching file. The `ui-design` skill carries the full procedure: surface classes, the design loop, and the complete rule catalog.

## Obligations

### 1. Category priority

When two concerns conflict, the earlier category in this list wins:

1. Accessibility
2. Touch and pointer targets
3. Performance
4. Layout and responsiveness
5. Typography and colour
6. Motion
7. Forms
8. Navigation
9. Data display

A change that trades a higher category for a lower one MUST say so in its summary.

### 2. Verify before calling a UI change done

The author MUST check each item against the rendered result or, when nothing can be rendered, against the source, and report which method was used:

- Text and interactive-control contrast meets the host's stated contrast target, or WCAG AA when the host states none.
- Every interactive element shows a visible focus state.
- Empty, loading and error states exist for each view that fetches or lists data.
- Layouts hold at the longest and shortest real content the field can carry, not only at the sample string.
- Every control is reachable and operable from the keyboard, in a logical order.
- Animation and transitions honour the reduced-motion preference.

### 3. Refuse

The author MUST NOT ship any of the following in code the change adds or edits:

- placeholder or lorem text in a shipped view;
- meaning carried by colour alone;
- icon-only buttons without an accessible name;
- elements that load without reserved space and shift the layout;
- text rendered inside images.

An instance in code the change does not touch is reported in the summary, not rewritten unasked.

### 4. State defaults; never invent sourced values

When a palette, font, spacing scale, icon set or pattern is looked up and the lookup returns nothing, the author MUST fall back to the host's design tokens or a plain default, and MUST say that a default was used. A value the author chose MUST NOT be described as taken from a style guide, brand kit or research source it did not come from. Where the host keeps a design context file (for example `DESIGN.md`), a local override of one of its values MUST carry a comment naming the value it overrides and the reason.

## Enforcement

Path-filtered to the globs in this rule's `pathFilter` field and demand-loaded as the companion to `rules/code-craft-conventions.md` §6. A change that touches a matching file without the verify report, or that matches a refuse entry, is a finding in code review. The `ui-design` skill's pre-delivery checklist is the extended form of §2.

## Bindings (§0.j five-direction)

- **Drives →** The craft floor on every edit to component, markup and stylesheet files matching the path filter.
- **Satisfies →** `rules/code-craft-conventions.md` §6 Companion Sub-Rule Anchor pointer.
- **Established by ↑** `rules/code-craft-conventions.md` (parent rule; M13 code craft). The `ui-design` skill, whose verify and refuse lists this rule restates in short form.
- **Gated by ←** The path-filter. The parent rule's host-discovery walk, which supplies the host's tokens and contrast target before this rule's checks run.
- **Cross-bound with ↔** `rules/code-craft-conventions.md` (parent rule; the parent cites it back under its own `↔` line).
