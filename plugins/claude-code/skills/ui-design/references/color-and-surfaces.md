<!-- SPDX-License-Identifier: MIT -->

# Color and Surfaces

Reference for the [`ui-design`](../SKILL.md) skill. This file sets the palette, contrast, dark mode, depth, and texture. Rule ids, bands, and grades live in the [rule catalog](rule-catalog.md). Genre comes from [surface classes](surface-classes.md). The color posture goes in the `color:` field of the [build record](build-record.md). A device this file lets a direction claim is named in the record's `declared:` field, or in `DESIGN.md` when the project has one. Naming it never closes a flag by itself: a waiver line that meets the material guard does ([rule catalog](rule-catalog.md), "Habit").

## 1. The four-layer palette

Write every color in OKLCH. Below, lightness (L) is a percentage and chroma (C) is the raw OKLCH value. The palette has four layers.

| Layer | Light mode | Dark mode |
|-------|-----------|-----------|
| Paper | L 92-98, C 0.005-0.015; product-minimal MAY reach L 100 at C 0 | Section 6, Paper row |
| Saturated-surface paper (the `saturated-surface` posture of section 2 only) | L 30-85, C 0.06-0.24; ink and rules derived from it to pass `acc-01` | Re-derived (section 6) when a second mode ships |
| Ink | L 16-24, C 0.005-0.014. Body text in ink SHOULD reach 7:1 against its paper; this aim is polish, and the pass line is `acc-01` (section 3) | Section 6, Ink row, with the same 7:1 aim for body text |
| Neutrals | 5 to 9 steps from paper to ink, C 0.005-0.018 | The same steps, re-derived (section 6) |
| Accent | C 0.12-0.22, plus an on-accent ink token. Playful multi-role and saturated-surface pages MAY reach C 0.24 ([surface classes](surface-classes.md)) | Re-derived (section 6) |

- A direction contract's `mid` paper band ([direction and themes](direction-and-themes.md), section 2) is legal only with the `saturated-surface` posture, and it takes the saturated-surface row.
- On a saturated-surface paper, text takes whichever ink row meets the `acc-01` text contrast against it. Where neither ink does, body text sits on a paper or ink panel, never on the saturated surface itself.
- The focus color shares the accent's hue. Its chroma is 0.18-0.22, lowered as far as needed for the value to sit in sRGB; that gamut fit takes a route from the [rule catalog](rule-catalog.md), "Checks that need a computation". Its lightness stays within 5 points of the accent. When that value misses the `acc-03` contrast against any paper it touches, move its lightness away from that paper until it passes, past the 5-point band if needed. `acc-03` wins over the band.
- Product-minimal MAY use the ink itself as its accent, a neutral accent below C 0.05. The focus color then takes the anchor hue, with chroma set as above. Its lightness is set by the `acc-03` contrast need against every paper, not by the accent's lightness.
- Each neutral leans toward one anchor hue. A page with an anchor hue that still uses untinted grays is flagged (`col-00.1`), since flat gray reads as a default. Product-minimal pages are exempt.

### Pure black and white

- Every color comes from a token (`tok-01`). A literal `#000`, `#fff`, or any other literal color outside the token block breaks that baseline rule (`tok-01`).
- A token set at 0 or 100 percent lightness fires `col-03.b`. Its guard: the value is named in `declared:` and passes `acc-01`. Pure white paper on product-minimal pages does not fire.
- To fix either one, first move the lightness into the paper or ink range of section 1 (for example L 96-98 paper, L 16-24 ink). Then tilt the value toward the anchor hue at chroma 0.005 or more. Chroma alone never fixes it: at 0 or 100 percent lightness the value stays black or white.

## 2. Color posture

Pick one posture before writing code, and write it in the build record's `color:` field.

| Posture | Meaning |
|---------|---------|
| `signal-only` | The default. The accent signals and does nothing else. |
| `dominant-color` | One field color fills 30-60% of the page, named in `declared:` as a surface color. The accent still only signals. |
| `multi-role` | Three or four named colors, each with one job. Each color's job and area allowance are named in `declared:`. |
| `saturated-surface` | The background is the color. Ink and rules are derived from it. |

A declared surface color never counts toward the accent's area.

### Accent footprint

Under `signal-only`, the accent marks nine things only:

- the active nav item;
- the focus ring;
- the hover underline on links;
- the main control;
- the current selection;
- a status mark;
- the one data series that carries a chart's point;
- scroll progress, such as the progress spine of [interaction and motion](interaction-and-motion.md), section 13.10;
- the drop position during a drag.

Measure the footprint at the 1280x800 fold, on the `first-1280x800.png` capture of the [pre-delivery checklist](pre-delivery-checklist.md), section 1. Add solid accent fills, large headings set in the accent, and full-width accent bands. Divide by the viewport area. This is clause `col-01.a`. Atmospheric blooms that stay inside the bloom limits of section 4 do not count, and neither does a declared surface color.

| Genre | Aim | Limit |
|-------|-----|-------|
| All genres except atmospheric | 5% | 8% |
| Atmospheric | 20% | 30% |

A custom direction reads the row of the genre in its record's `genre:` field ([rule catalog](rule-catalog.md), "Flags and downgrades").

An area at or under the aim raises nothing. Past the aim, `col-01.a` grades `habit-open` in two bands, the middle band (up to the limit) and the upper band (past the limit). A fix or a waiver line closes either band; each band's guard is in the `col-01` row of the [rule catalog](rule-catalog.md). A color spread across the whole page stops pointing at anything.

## 3. Contrast

Contrast is the baseline rule `acc-01`. Its ratios, the large-text definition, the WCAG exceptions, and when a stricter target stated by the host or the brief applies live in that row of the [rule catalog](rule-catalog.md). Measure each pair on the computed background, with any texture or overlay in place.

| Element | `acc-01` class |
|---------|----------------|
| Text that is not large: body, labels, captions, button text, placeholder, helper and muted text, marked blanks ([copy and honesty](copy-and-honesty.md), section 13) | Text ratio (SC 1.4.3) |
| Large text, as the `acc-01` row defines it | Large-text ratio |
| Non-text against adjacent colors: meaningful icons, chart marks and data series needed to read a chart, focus indicators, and a control boundary that is the only cue identifying the control, such as a field edge | Non-text ratio (SC 1.4.11) |

The WCAG ratio is the only pass line. A perceptual-contrast figure never replaces the ratio and never passes a pair the ratio fails.

A ratio comes from a tool, never from hand arithmetic. The routes, and the `not checked` grade when no route exists, are in the [pre-delivery checklist](pre-delivery-checklist.md), section 1, "Static checks".

- A rule that puts an element on a dark background MUST also set that element's text color (`acc-01`).
- A page MUST NOT set gray text on a colored background (`acc-01`).
- Button text meets its `acc-01` ratio against its fill in every enabled state.
- Where the accent carries text, an on-accent ink token MUST exist (`acc-01`, `tok-01`).
- Red against green is never the only cue for a status (`acc-02`). Add an icon, a word, or a shape.

This is a baseline section under `acc-01`, and how each of its sentences grades is set in the [rule catalog](rule-catalog.md), "Grade words in topic files".

## 4. Banned and flagged treatments

These gradients and grounds are banned, text fills included (`col-03.a`):

- purple-to-blue gradients;
- purple-to-pink gradients;
- cyan on a dark ground.

The guard for `col-03.a`: the hues come from a captured or supplied brand spec.

The following are flagged:

- Gradient text is flagged (`typ-02.a`). Its waiver guard is in the `typ-02` row of the [rule catalog](rule-catalog.md).
- A gradient background with no source in the tokens (`col-01.b`).
- A gradient with more than three stops (`col-00.4`).
- A color token that depends on alpha (`col-00.4`). Alpha is for overlays, shadows, and frame outlines only. A frame outline sits on an element that takes no focus, which the `acc-03` row allows.
- A framework's default palette used as tokens or utility classes, unless the project already uses it (`col-00.4`).

### Glow and wash

These are flagged (`col-00.4`):

- aurora or mesh blobs behind text;
- soft-focus orbs that float or drift;
- colored radial halos and spotlights;
- tinted glow shadows with no offset on a dark ground.

Atmospheric pages MAY use two radial blooms that never move. Each covers 20-30% of the canvas. These are the bloom limits; blooms inside them do not count toward the accent footprint of `col-01.a`. Every other page uses flat or grained surfaces, shows elevation through lightness, and gives shadows a real offset and blur, or uses the 1px ring of section 7.

## 5. The generic look

### The warm trio

On a custom or unthemed build, the following three together are flagged (`col-00.5`):

- cream paper: L 90 or higher, C 0.006 or higher, hue 55-105;
- a high-contrast serif as the display face (class list in [typography](typography.md));
- a terracotta or clay accent: C 0.08 or higher, hue 15-55.

Prompts about warm, bookish, or family subjects pull hardest toward this look. The flag does not fire when the prompt asks for this exact look. To fix it, change the accent first, then the paper, then the display face.

### Other machine-made signs

Each item below is flagged as a sign of a generated page:

- monospace labels on a direction not built from monospace (`typ-00.9`, [typography](typography.md), section 9);
- labels or controls in tracked capitals (`typ-01`);
- one heading word picked out by color or weight (`typ-03.b`);
- metadata joined by middle dots, or arrows glued to link text (`cpy-06`);
- italic display type used as ornament (`typ-00.10`, [typography](typography.md), section 10);
- glow shadows or radial halos on a dark theme (`col-00.4`, section 4).

Each item grades under the id it cites, with that id's guard in the [rule catalog](rule-catalog.md). An item with no id of its own grades under `col-00.5`.

## 6. Dark mode

### When to ship it

Ship both light and dark modes only when the user asks, or when the project already has a mode system. A direction that is dark by design is one mode, not two.

### Re-derive each token

Dark mode is a second full rendering of the same token system. Recompute each token with the table below. Never invert colors or flip the gray ramp. The anchor hue does not move. Every contrast pair passes in both modes. When a re-derived token falls under its `acc-01` ratio, fix the derivation and keep the threshold.

| Token | Dark-mode value |
|-------|----------------|
| Paper | L 12-18, C 0.008-0.015, tinted toward the anchor hue; never pure black |
| Elevation | Each raised step is 3 points of L lighter, never darker |
| Ink | L 90-96, tinted; never `#fff` |
| Secondary inks | Re-spaced in even steps between the new paper and the new ink |
| Rules | L 26-34, checked against the raised surface |
| Field edge | Meets the `acc-01` non-text ratio against the paper and against every raised surface a field sits on. Never takes the rule value |
| Accent | Chroma lowered by 0.02-0.04, L raised by 5-10, hue kept |
| On-accent ink | Meets the `acc-01` text ratio on the accent, or the large-text ratio for large text |
| Focus ring | Meets the `acc-03` contrast against each paper and every color it touches |
| Status colors | Error and success: L 68-72, hue kept, chroma kept or lowered by up to 0.02 to stay inside sRGB. Each meets the `acc-01` text ratio on the dark paper |
| Body weight | With a variable font, 50 lighter (400 becomes 350), since light text on dark looks heavier. This step is not a separate weight. A static face keeps its light-mode weight |

### Emission

- The light tokens stay as they are.
- The root element ships with `data-mode="auto"`. A toggle changes it to `light` or `dark`.
- Each mode sets `color-scheme` for itself. Native controls and scrollbars then follow the chosen mode, not the system setting.
- One override block holds only the tokens that change. It applies under `data-mode="dark"`. It applies again inside a `prefers-color-scheme: dark` query while the mode is still `auto`.
- The toggle saves the choice in local storage. A blocking script inline in `<head>` applies the stored choice before the first paint. The first frame then already shows the chosen mode.
- The script wraps the storage read in `try`/`catch`. When storage throws or holds no valid value, the root keeps `data-mode="auto"`.

```css
:root { --paper: oklch(97.5% 0.006 250); --ink: oklch(21% 0.012 250); }
:root[data-mode="auto"] { color-scheme: light dark; }
:root[data-mode="light"] { color-scheme: light; }
:root[data-mode="dark"] {
  color-scheme: dark;
  --paper: oklch(15% 0.011 250); --ink: oklch(93% 0.008 250);
  --error: oklch(70% 0.19 27); --success: oklch(70% 0.12 150);
}
@media (prefers-color-scheme: dark) {
  :root[data-mode="auto"] {
    --paper: oklch(15% 0.011 250); --ink: oklch(93% 0.008 250);
    --error: oklch(70% 0.19 27); --success: oklch(70% 0.12 150);
  }
}
```

### Dark surfaces

- Drop shadows are off. Show height with lighter steps or a thin inner ring. A drop shadow on a dark ground looks like a glow.
- A card is always lighter than its canvas. A darker card looks like a hole.
- All headings share one ink.
- Never invert or brighten raster images with CSS. Pick photographs that sit well on a dark ground. Or mount a bright photo in a raised well, like a print in a frame.
- Duotone plates and textures need their own dark versions.
- Chart marks follow the accent rule. Gridlines use the dark rule color. Sparkline fills drop to half their opacity.

### Check both modes

- Run every check in both modes. When the host can render, capture dark mode by setting `data-mode="dark"` on the root, or by emulating the color-scheme preference. When it cannot, compute the dark contrast pairs from the token values by a route in the [pre-delivery checklist](pre-delivery-checklist.md), section 1, "Static checks".
- `tok-01` and `col-03.b` apply inside the dark block too.
- The record's `palette:` field names both modes ([build record](build-record.md)).

## 7. Depth, shape, and browser surfaces

- `shadow-card` defaults to one of two recipes: a small offset, `0 1px 2px color-mix(in oklch, var(--ink) 5%, transparent)`, or a 1px ring with no offset at 6% in the same `color-mix()` form. Both are token-derived (`tok-01`), and the ink's own hue tints them toward the anchor hue. A direction MAY set its own single recipe, such as a hard or soft offset. A page still uses one recipe, and the border-and-shadow limit below still holds.
- A raised surface is never darker than the surface under it.
- A hairline border and a broad soft shadow never share a surface. Broad means a blur of 24px or more after any negative spread. This line is the one statement of the border-and-shadow limit; other files cite it.
- Each nesting depth has one radius (`lay-00.page-wide-invariants`, owned by [layout and composition](layout-and-composition.md)). Nested corners share a center: the inner radius is the outer radius minus the padding, and never below 2px.
- Cap image radii, for example with `min(1vw, var(--radius-card))`.
- When a page commits to a palette, the browser's own surfaces follow it: `::selection`, `caret-color`, `scrollbar-color`, the focus ring, and link underlines.
- A single container recipe boxing content where the containment ladder calls for a varied step is `col-02.a`. A recipe is one radius, shadow, and border together. The static check fires when one card recipe wraps 6 or more selectors that are not instances of one repeated item. It also fires when pill rounding sits on more than 4 selectors that are not controls. The one-radius-per-depth and one-shadow-style rules above never fire it alone. Frosted panels over a plain background are `col-02.b`.

## 8. Texture

Texture is a material with a ration. It is not there for mood.

### When it is allowed

- Texture is flagged (`col-00.8`); a waiver line that meets the material guard closes it.
- The texture comes from a physical printing or display process: stencil duplicator, letterpress, ticket stock, line printer, or a tube screen. The page uses only the mark that process leaves.
- Product-minimal pages carry no texture. A page never mixes two families. Texture is never added to make a flat page look busy.

### The budget

- One family per page: grain, halftone dots, misregistration, scanlines, or a deckled edge. A halftone that belongs to a photo treatment does not count.
- The opacity value lives in a token.

| Placement | Highest opacity |
|-----------|-----------------|
| Any layer under or over running text, whatever its placement | 0.05, or none |
| Whole page, where no body text sits above the layer | 0.08 |
| Whole page, low-frequency wash (base frequency 0.02 or lower), where no body text sits above the layer | 0.12 |
| Inside one card or plate, where no body text sits above the layer | 0.15 |

A whole-page layer lies under running text wherever the page carries prose, so it takes the 0.05 cap. The higher caps apply only where body text sits on a texture-free panel or nowhere above the layer.

- Texture never moves and never takes pointer events, except the one misregistration settle in the families table. Assistive technology never sees it.
- It is pure CSS or inline SVG, with no image requests. Measure contrast with the texture in place.

### The five families

| Family | Recipe | Limits |
|--------|--------|--------|
| Speck grain | A 200px inline SVG tile: fractal noise at base frequency 0.85, 2 octaves, stitched. A color matrix sets alpha to noise times 9 minus 4, which breaks the noise into visible specks. On a dark ground, set the RGB rows to output 1 for white specks | Plain turbulence at this opacity is an unseen haze. The matrix is what makes the specks show |
| Halftone dots | A repeating radial gradient. Cell 12px and dot 1.5px, both tokens. Ink or one spot color | Plates and section bands only. Never under or over type. Never a field made all of accent |
| Misregistration | Two pseudo-element copies of one word sit behind the letters. They shift 1-3px in opposite directions, in two spot inks, so only colored edges show. Set the element to `inline-block` so the copies track the glyphs | One key word per page, in the hero, named in the waiver line's guard and in `declared:`. It MAY settle into place once on load, within the long duration token. It stays still under reduced motion and never loops. Past 3px it looks broken |
| Scanlines | A fixed overlay over the whole page: a repeating gradient of 2px clear and then a 1px line at 5% ink alpha, inside the running-text cap | Only on a direction built on screen-era material, with scanlines named in the waiver line's guard and in `declared:`. It sets a mood; it never draws a monitor frame |
| Deckled edge | A 6px radial mask repeating on a 12 x 24 tile along one side of a ticket or stub | One element class per page. It marks an object; it is not a general border |

Photo treatments are in [imagery and data](imagery-and-data.md).
