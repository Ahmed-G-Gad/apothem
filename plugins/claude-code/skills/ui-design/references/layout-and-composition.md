<!-- SPDX-License-Identifier: MIT -->

# Layout and Composition

Reference for the [`ui-design`](../SKILL.md) skill. This file sets the canvas, the spacing, the section rules, the composition library, and responsive behavior for page scope. Which of its sections an app screen or a component skips is listed only in the [rule catalog](rule-catalog.md), "Flags and downgrades", under page-only layout sections and the component and app scopes. Rule ids and grades live in the [rule catalog](rule-catalog.md). A flag in this file that cites no id grades under the catch-all `lay-00.<heading>`, where the heading is the one it sits under, in kebab case. Hero rules live in [hero](hero.md); page structure lives in [page anatomy](page-anatomy.md) and [page shapes](page-shapes.md).

All measurements assume a 1440 x 900 reference viewport unless a line says otherwise. Every padding, margin, and gap value comes from a spacing token in the [`DESIGN.md` template](design-md-template.md) (`tok-01`). Each length below names its token. Token values, including how they change at each breakpoint, live only in the template's "Reference scale".

## The canvas

### One container

- All content sits in one centered container: maximum width `container`, side gutters `gutter`. The container is border-box, with `gutter` as its inline padding. That gives 1312 px of content at 1440 wide.
- At wider screens the content stays at 1312 px and only the outer margins grow.
- A page MUST have exactly one container width. A container with no maximum width is flagged (`lay-00.one-container`).
- Line length and column counts hold above 1440. Grids MUST NOT add columns on wide screens. A visual sized in `vw` MUST carry a `max-width`.

### Twelve columns

Every section aligns to one shared 12-column grid with a `col-gap` column gap. With 1312 px of content, the spans measure:

| Span | Width |
|------|-------|
| 1 column | 80 px |
| 4 columns | 416 px |
| 6 columns | 640 px |
| 8 columns | 864 px |
| 10 columns | 1088 px |

Alignment runs unbroken from the nav to the footer. A section below the hero that invents its own grid breaks the page; the hero grid of [hero](hero.md), section 6, is the one exception.

### Two layers per section

Each section is two nested elements.

- The **outer** layer owns the background and the top and bottom padding.
- The **inner** layer owns the maximum width and the left and right padding only.
- A full-bleed color band swaps the outer background and keeps the same inner layer, so the band stays on the grid.
- The inner layer MUST NOT take the four-side `padding` shorthand. It silently resets the vertical rhythm the outer layer set.

## Spacing

### The ladder

The tiers below are `pol-01`. Raw lengths outside the scale fall under `tok-01`.

| Relationship | Token |
|--------------|-------|
| Heading to its lead line | `space-5` to `space-6` |
| Heading group to section body | `space-8`; `space-7` below 40rem |
| Grid items, across | `col-gap` |
| Grid items, down | `space-8`; `space-7` in tight layouts |
| Padding inside a card or well | `space-7`; `space-6` below 40rem |

Related things sit close. Unrelated things sit apart.

### Section gaps

- Use three gap sizes between sections: `section-1`, `section-2`, and `section-3`. Mix them. One gap at every boundary looks templated and is flagged (`lay-00.section-gaps`).
- The minimum gap between two sections on the same background is `section-1`.
- A band (a background change) takes `section-1` of its own padding above and below. Padding at a boundary where the background changes MUST NOT drop under `section-1` at the current width; the [`DESIGN.md` template](design-md-template.md), "Reference scale", sets that token per breakpoint.
- A dense structure that divides itself with rules and color, such as a long index, MAY use uniform gaps.

### Space is earned by mass

Whitespace matches the weight of what it frames. A `section-2` gap suits a section 600 to 800 px tall. Under a 200 px section the same gap reads as a hole.

When a page feels empty, enlarge the heading or the visual, or give the section more real content. Never close the gaps to hide a thin page.

### Proximity and padding

- A heading sits nearer to what it introduces than to what precedes it (`pol-01`). Aim for twice as much space above as below.
- Flag an `h2` to `h4` whose top space is under 0.75 times its bottom space and short by 12 px or more (`pol-01`). Headings inside boxes under 200 px tall are exempt.
- **Minimum inset.** Text inside a filled or side-bordered box larger than 100 x 30 px keeps at least `clamp(var(--space-3), 0.5em, var(--space-6))` from the sides and `clamp(var(--space-2), 0.3em, var(--space-4))` from the top and bottom. Chips, callouts, and bands take this minimum. Cards and wells take the card padding in "The ladder", which meets or exceeds it. Both clamps are token-derived forms under `tok-01`.
- On a phone, running text stays at least 8 px from the screen edge. The `gutter` token there sets the default inset.
- Icons, opening quotes, and large type align optically at edges, not by their boxes (`pol-06`).

## Page-wide invariants

Each item below holds across the whole page (`lay-00.page-wide-invariants` unless an id is named):

- Buttons: a single filled-primary recipe (`lay-06.b`).
- Container: a single maximum width.
- Column gap: below the hero, every grid uses the same one.
- Corner radius: one value for each nesting depth. This invariant never fires `col-02.a` on its own ([color and surfaces](color-and-surfaces.md)).
- Heading groups: centered ones never outnumber left-aligned ones.
- Visual weight: one primary axis, either left, right, top-heavy, or bottom-weighted. Centered weight is the default a model drifts into, not a choice.

## Density budget

- The page has 6 to 9 sections, counting hero and footer. A thin prompt gets 5. Shorter pages appear only where the job table in [page anatomy](page-anatomy.md), section 2, names them.
- The page keeps the page and band word budgets in [copy and honesty](copy-and-honesty.md), section 2 (`cpy-05`). That section also says what counts as a word.
- Hero limits (action count and the ban on any other block) live in [hero](hero.md), section 7. Headline and lead word budgets live in copy and honesty, section 2.
- Richness comes from scale and imagery, never from more words. The word budget is a house rule; see [copy and honesty](copy-and-honesty.md).

## Section rules

### Content first

Each section presents one piece of real content at its strongest: the menu, the line-up, the latest issue, the product in use, the price. Pick the content first, then the composition that suits it.

Content that labels itself, such as a menu, a timetable, a track list, or the product's own screen, MAY drop the heading group or carry its title inside.

### Skeletons

At most two adjacent sections share a skeleton, such as "heading group, then one body block". Break a third with a different composition, a statement, or a band.

### The heading group

- A section heading keeps the section-heading budget in [copy and honesty](copy-and-honesty.md), section 2, with at most one lead line beneath it.
- Place the group across columns 1-6 or 1-7, or split it: heading on columns 1-5, lead on 7-12, sharing a baseline.
- Center a heading group only above a symmetrical body.
- Staged layouts MAY title each stage with one word.
- Measured at 1440, the median `h2` below the hero is 40 px or larger (`lay-07.b`). The clause does not fire on the prose-document, letter, and photo-led shapes, since their headings act as text or annotation (see [page shapes](page-shapes.md) and [typography](typography.md)).

### Width and mass

- Below the hero, the widest row of each section body spans 10 or more of the 12 columns, unless the body is a single statement (`lay-07.a`). The clause does not fire on the prose-document, letter, and question-answer shapes. It also does not fire on running prose of two paragraphs or more held at the `pol-02` measure ([typography](typography.md)), on the hairline-rows variant (composition 5), or on the sticky-pane shape. Fix a narrow body by adding a visual beside the text, splitting the text, or setting it as a statement.
- Every body has mass: at least one of these.
  - A visual 360 px or taller. A visual under 360 px does not count as mass, and one under 300 px is flagged (`lay-00.width-and-mass`).
  - Three or four items running edge to edge.
  - A list or table with at least three rows that spans ten or more columns, or the rows of the hairline-rows variant (composition 5).
  - An interactive control built from the brief's own facts.
  - A statement set at section-heading size or larger.
- A heading and a paragraph alone are a heading group, not a section.
- One single-line band that holds an action is allowed per page.
- Remedies for a thin section: widen to ten columns, add an image, set a large statement, or merge it into a neighbor.

### Balance and height

- In a text-beside-visual split, the vertical centers of the two halves sit within 60 px. Neither column leaves more than 20 percent of the row blank.
- Sections run 520 to 900 px tall by default. The content sets the exact height.
- A section 360 to 519 px tall is allowed only when its body is a single statement, a figure row, or a stat row. Any other body that short gets more real content or merges into a neighbor.
- Under 360 px is for bands only: an action strip, a logo strip, or one statement. The number of bands a page carries is set in [page anatomy](page-anatomy.md), section 7.
- The footer and a colophon are exempt from these section-height rules. The footer follows [copy and honesty](copy-and-honesty.md), section 11.

### Containment ladder

Divide content by climbing this ladder, and vary the step from join to join:

1. Open space.
2. A 1 px rule.
3. A tinted well: one paper-tone step, no border.
4. A card: a border or a shadow. A hairline border and a broad shadow never share one card; [color and surfaces](color-and-surfaces.md), section 7, sets the blur that counts as broad. Only for content with its own interactions or of a different kind.

Do not use white cards on a tinted page, cards inside cards, or bordered boxes inside wells. Surface tones live in [color and surfaces](color-and-surfaces.md).

### Stat rows

- Separate neighboring figures with thin top or vertical rules. No leading padding before the first and none after the last.
- Reset the rules when the column count changes, for example top rules once the items stack below 60rem.
- Each figure has a label that does not wrap and no icon. Large figures use tabular numerals (`pol-04`).
- Only figures the user supplied (`cpy-02`). See [copy and honesty](copy-and-honesty.md).

### Grids

- No empty cell and no lone item on a last row under a fuller row. Change the item count or the column count.
- Logo rows divide evenly: 3 and 3, never 5 and 1.

## Overflow and stacking guards

- **Overlap** (`lay-05`). No text is drawn under an opaque box, an image, or other text. Sticky and fixed chrome is excepted.
- **Sticky stacking.** Never stick two elements at `top: 0`. Offset the second by `var(--nav-height)`, the Frame token in the [`DESIGN.md` template](design-md-template.md). The sticky nav takes the `z-header` layer. Every other sticky part takes `z-pin`, which sits below it (`tok-01`).
- **Focus not obscured** (`acc-13`). A sticky header, sticky bottom bar, banner, or toast never covers the whole of a focused element. Set `scroll-padding-top` on `html` from `var(--nav-height)`, plus `var(--strip-height)` when an announcement strip sticks. Every sticky bottom bar takes its height from `var(--bar-height)`, and `scroll-padding-bottom` reads the same token, so no literal length enters (`tok-01`). Check it by tabbing through the page at the full-page capture widths in the [pre-delivery checklist](pre-delivery-checklist.md), section 1.
- **Content extremes** (`lay-08`). The layout holds at the longest and the shortest real content each field can carry, and at a test string 40 percent longer than the English: nothing clips, overlaps, or collapses. Check each of the three at the full-page capture widths in the [pre-delivery checklist](pre-delivery-checklist.md), section 1.
- **Text spacing** (`acc-14`). Apply the four spacing overrides the `acc-14` row of the [rule catalog](rule-catalog.md) sets, then check at the full-page capture widths in the pre-delivery checklist, section 1. Nothing clips or overlaps. Every label set to `nowrap` still fits, or its row reflows.
- **Radio tabs.** CSS-only tabs built on radios positioned absolutely at `top: 0` make the page jump on each click. Keep the radios in normal flow at the size [interaction and motion](interaction-and-motion.md), section 7, sets, or focus with `preventScroll` from a script.
- **Overflow.** Grid columns that hold images use `minmax(0, 1fr)`, not `1fr`. Display headings get `min-width: 0` plus `overflow-wrap: break-word` (not the `anywhere` value). Shrinkable flex items take `min-width: 0`; icons and images take `flex-shrink: 0`.
- **No horizontal scroll** (`lay-01`). Set `overflow-x: clip` on `html` and `body`. `hidden` on `body` makes a scroll container, which breaks `position: sticky`. Widths use `100%`, never `100vw`. Check every width of the supported range in the pre-delivery checklist, section 1. A section built to overflow, such as a rail, keeps its own overflow visible.

## Compositions

A composition is an arrangement, not a component. Each one is drawn in the theme's materials from [direction and themes](direction-and-themes.md).

- A page uses 3 to 6 distinct compositions. A page shape built wholly from one composition is exempt from the 3-to-6 range.
- The same composition MUST NOT appear in two adjacent sections (`lay-00.compositions`). The exception is a page shape built wholly from one composition; there, neighbors change ratio and, where allowed, side.
- Identical card grids for unlike content are a habit finding (`lay-03.b`).

| # | Composition | Layout | Numbers |
|---|-------------|--------|---------|
| 1 | Text and visual split | A text group sits beside a visual. The group holds a heading, a lead, and either a few short facts (two to four) or a single action. Swap sides at most once per page. Two splits on a page use different ratios, except in a page shape built wholly from splits. | Ratios 6/6, 5/7, 4/8, putting the visual on columns 7-12, 6-12, or 5-12. Visual 440 px or taller, aspect 4:3 to 4:5 (portrait for product photos). |
| 2 | Full-width showcase | Heading group, then one wide visual across all 12 columns. Up to two smaller visuals below at unequal widths, never three equal frames. | Aspect 16:9 to 21:9, 560 px or taller. Secondaries 8+4 or 7+5. |
| 3 | Item grid | One row of 3-4 items or a 2 x 2 block: plans, products, places, rooms, dishes. Each has a photo, a large number, or a title that fills the cell, plus one line. Cells match height and align at the top. No empty frames, no stock faces passed off as real people (`cpy-02`), no icon tiles over headings (`img-02.c`). | Cells 240 px or taller. |
| 4 | Bento tiles | Tiles of mixed span on the shared 12-column grid. A 6-column bento is that grid read in pairs of tracks, with the same `col-gap`. Two or more carry a visual. One tile clearly leads. | 4-6 tiles. Spans such as 8+4 over 4+4+4, or 7+5 over 5+7. Rows 280-360 px. |
| 5 | Hairline rows | Full-width rows split by thin rules: title on the left, text or number on the right. Variant: the heading group takes a narrow left column beside the rows (FAQ, index, timeline, price list). | 3-5 rows, 72-120 px each. Title 1-5, detail 6-12. Variant: heading 1-4, rows 5-12. |
| 6 | Data table | Full-width table, tabular numerals, the row-naming column one weight heavier. | 4-5 rows, 56-72 px each. |
| 7 | Figure row | Three or four real numbers set large with labels below, spread across the grid, split by vertical rules. | Figures at `text-display-sm`. |
| 8 | Process steps | Three or four stages, across or down. Numbers come from a real ordered list, never a typed "01" over the heading. Each stage has a title, one line, and a visual when the material has one. In the vertical form, visuals stay on one side. | 3-4 stages. |
| 9 | Single statement | One sentence over two or three lines, with its attribution or one action. Once per page. | 8-10 columns wide. From `text-section` up to `text-display`. Poster scale only through the poster exception in the [`DESIGN.md` template](design-md-template.md), "Reference scale". |
| 10 | Background band | A full-width background change around the normal container: alternate paper, ink, or the accent where the color posture allows it. The band carries the real action of the visitor's job. Examples: open booking slots, the purchase box, app-store badges next to a phone screen, or the date and place of the coming event. An email sign-up is never its default. | Padding `section-1` top and bottom. |
| 11 | Form beside facts | Form fields across 6 or 7 of the 12 columns, beside the heading group and two to four facts. One primary action. | Fields on 6-7 columns. Inputs at `field-height`, inside the field-height column of the table in [interaction and motion](interaction-and-motion.md), section 4. 2-4 facts. |
| 12 | Overflow rail | A horizontal strip that runs past the container edge so the next item is visibly cut: dates, issues, products, rooms, episodes. Scrolls by touch and keyboard with snap points. The scrollbar MUST stay visible, colored through `scrollbar-color` from tokens. When the items run past one screen width, previous and next buttons also sit beside the rail. | 5 or more items. |
| 13 | Pinned visual, scrolling panels | One visual sticks across 6 or 7 of the 12 columns while short panels scroll past on the remaining columns. Each panel changes the visual: a state, a crop, or a step. | Visual on 6-7 columns. 3-4 panels. Static below 60rem. |
| 14 | State switcher | One region whose states sit behind a segmented control: lunch or dinner, monthly or yearly, phone or watch, one schedule per day. Every state holds real content. The first state shows with scripting off (`prf-02`). | 2-5 states. |
| 15 | Dense index | A tight list of the brief's own entries with facts in columns (issue, date, topic; project, year, client; episode, length). MAY filter. The leading row is set larger. | 6-20 rows. |
| 16 | Time schedule | Times against places or days: acts across two stages, a weekly class plan, opening hours as a strip. Marks the current or next slot. Only for times a visitor picks between or plans around. Never dress a process, a work day, or a delivery up as clock times. | One column per day on phones. |
| 17 | Purchase offer | The item and everything needed to buy it: photo or screen, options (size, scent, plan), price, the buy action, and one line on shipping or terms. On a buy page it MAY serve as the hero. | One primary action. |

## Responsive behavior

### Two breakpoints

Breakpoints are in `rem`, so they follow the reader's font setting. Component rules reuse the same two widths and are written in one direction only. Add a third breakpoint only where the content breaks without it.

The token sheet changes `gutter`, `col-gap`, and the three section tokens at these breakpoints. Their values live only in the [`DESIGN.md` template](design-md-template.md), "Reference scale".

| Breakpoint | What changes |
|------------|--------------|
| Above 60rem | The full canvas. |
| Below 60rem (layout; 960 px at the default 16 px root) | Multi-column grids stack. Tilted and clipped effects drop. Sticky panes stop sticking. Heroes resize as [hero](hero.md), section 1, "Sizing", sets. |
| Below 40rem (type; 640 px at the default 16 px root) | Margin captions move into the flow. Annotations merge. Grids reach one column. Small interface text steps up from `text-sm` to `text-base`. |

The page stays usable at the zoom level and the narrow width that the `acc-09` row of the [rule catalog](rule-catalog.md) sets.

### Stacking order per composition

Below 60rem, each composition stacks in reading order: heading group first, body after. The source order matches that stacked order, so the reading order and the visual order agree (`acc-27`).

- **Split:** the visual follows its text.
- **Showcase:** the wide visual, then the secondaries in order.
- **Item grid:** two columns, then one below 40rem.
- **Bento:** the lead tile first.
- **Hairline rows and index:** the title sits over its detail.
- **Figure row:** two across, then one; the rules switch to top rules.
- **Rail:** stays a rail.
- **Pinned pair:** releases; each panel sits with its own state of the visual.
- **Schedule:** one column per day.
- **Form beside facts:** the heading and facts first, then the form.

Visuals keep their aspect ratio and drop their minimum height. Only rails, and tables built for it, scroll sideways.

### Fluid values and capability queries

- Values that change smoothly, such as display type, use `clamp()`. Layouts that change in steps use media queries.
- Detect input by capability, not width. Use `(hover: hover)` for hover-only polish, such as a thicker underline. Use `(pointer: coarse)` for larger hit areas, at the coarse-pointer size of `tgt-04` in the [rule catalog](rule-catalog.md).
- Small interface text (metadata, nav links, controls) changes step at 40rem, as the table in "Two breakpoints" sets. Both are existing steps of the reference scale, so no step is added (`typ-00.6`). Body text never goes below the body floor in [typography](typography.md), section 8 (`typ-00.8`).
- Components that respond to their own width use container queries.
- Desktop sidebars and filter panels fold into a menu or a disclosure on narrow screens.

### Labels kept to one line

The wrapping rules for buttons, main nav links, footer links, tabs, and breadcrumbs are in [interaction and motion](interaction-and-motion.md), section 4. When a label wraps where that section forbids it, fix it in this order:

1. Shorten the label.
2. Forbid wrapping on that control and let its row reflow.
3. Collapse the row: on narrow screens keep one or two short items visible and move the rest into a menu.

### Viewport units and safe areas

- Heights that meet the mobile browser bars use `dvh` or `svh`. The hero's height units follow [hero](hero.md), section 5.
- Widths use `100%`, never `100vw`.
- When the page extends under a notch, set each side's padding to the larger of the gutter and the inset: `max(var(--gutter), env(safe-area-inset-left))`, and the matching right-hand value. That `max()` is a token-derived form under `tok-01`.

### Tables

- Headers are sentence case and do not wrap. Rules are horizontal only. No enclosing border or card. The table spans the full width.
- On phones, keep two columns visible: the column that identifies each row and the column holding its action. Rebuild every row as a labeled block, or freeze the first column and let the others scroll sideways.
- A table of ten or more columns on a phone needs a redesign, not a squeeze.
- Features and metadata are definition lists, with the term one weight heavier.

### Translation and direction

- Margins, padding, and positions use logical properties (`margin-inline`, `padding-block`, `inset-inline-start`).
- Leave room for the longer test string in "Content extremes" (`lay-08`), under "Overflow and stacking guards".
- Do not hard-code date or number formats.

### Banned practices

These are banned (`lay-00.banned-practices`):

- Sniffing the device or user agent instead of querying features.
- Interactions that only work on hover (`acc-15`).
- Breakpoints written in `px`.
- Fixing a crowded layout by shrinking body text under the `typ-00.8` floor.

Final checks before delivery are in the [pre-delivery checklist](pre-delivery-checklist.md).
