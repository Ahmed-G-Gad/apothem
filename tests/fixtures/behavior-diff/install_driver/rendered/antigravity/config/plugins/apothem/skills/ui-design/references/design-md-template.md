<!-- SPDX-License-Identifier: MIT -->

# DESIGN.md Template

Reference for the [`ui-design`](../SKILL.md) skill. `DESIGN.md` is the single design context for a project: the skill reads it before designing and updates it after. Keep it short and factual. A value belongs here only if the interface uses it.

## How to maintain it

- Read it first. Where a requested change contradicts it, the user's brief wins; record the new decision and its reason.
- Add a token or component in the same change that first uses it.
- Never record a value that was not chosen: leave the line as `TODO(clarify): ...` instead of inventing a brand colour, font, or voice rule.
- A single page may override a default locally, with a comment at the override. If the same override appears on three pages, promote it into this file.
- Date each decision in the log; remove decisions that no longer apply instead of leaving contradictions.

## Template

Copy the block below to the project's design-context location and fill it in.

````markdown
# Design

Surface class: persuade | operate | read | experience (per screen group if mixed)
Dials: variance <value>, motion <value>, density <value> (user-set or default)
Accessibility target: <for example WCAG 2.2 AA>
Supported viewports and inputs: <smallest width, touch / pointer / keyboard>

## Voice

Tone: <three adjectives and one sentence describing how copy sounds>
Terms: <product terms spelled and capitalised one way>
Avoid: <words and patterns the copy never uses>

## Colour tokens

| Token | Light | Dark | Use |
|-------|-------|------|-----|
| color-bg | | | Page background |
| color-surface | | | Cards, panels |
| color-text | | | Body text |
| color-text-muted | | | Secondary text |
| color-border | | | Dividers, outlines |
| color-primary | | | Primary actions, links |
| color-focus | | | Focus ring |
| color-success / warning / danger / info | | | Status |

Contrast checked: <pairs and ratios, date>

## Type scale

| Token | Size / line height | Weight | Use |
|-------|--------------------|--------|-----|
| text-xs | | | Captions |
| text-sm | | | Secondary |
| text-base | 16 px / 1.5 | | Body |
| text-lg | | | Lead |
| text-xl and up | | | Headings |

Families: <family, source, licence>

## Spacing, radius, elevation

Spacing scale: <for example 4, 8, 12, 16, 24, 32, 48, 64 px>
Radius: <small, medium, large values>
Elevation: <levels and shadows>
Layers: <z-index scale>
Breakpoints: <values, and why>
Content width: <maximum>

## Motion

Durations: <short, medium, long in ms>
Easing: <entering, leaving, moving>
Reduced-motion behaviour: <what is removed, what stays>

## Components

| Component | Variants and states | Notes |
|-----------|--------------------|-------|
| Button | primary, secondary, quiet, destructive; hover, focus, active, disabled, loading | Minimum target size |
| Input | text, select, checkbox, radio; default, focus, error, disabled | Label and helper placement |
| Table | default, dense; empty, loading, error | Sort, truncation rules |
| Dialog | | Focus return, dismissal |

## Patterns

Empty states: <structure and tone>
Error states: <where and how errors appear, recovery action>
Loading states: <skeleton or progress, threshold>

## Decisions

| Date | Decision | Reason |
|------|----------|--------|
````
