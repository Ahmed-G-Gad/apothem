<!-- SPDX-License-Identifier: MIT -->

# Hero

Reference for the [`ui-design`](../SKILL.md) skill. Page scope only (see [surface classes](surface-classes.md)); [SKILL.md](../SKILL.md), "Reference loading", says when it loads. It covers the opening screen: its posture, its fit to the fold, its visual, its words, and its entrance. What the hero shows comes from the visitor's job in [page anatomy](page-anatomy.md); the theme decorates it ([direction and themes](direction-and-themes.md)). Rule ids and grades live in the [rule catalog](rule-catalog.md). A flag in this file that cites no id grades under the catch-all `hro-00.<section>`.

## 1. The hero is the first screen

The hero fills the first screen: the next section begins inside the band that section 3 sets. It is not taller, and it does not stop short over an empty strip. The short header is the one exception: it follows its own limit (section 3). Check the hero on the first-screen captures that the [pre-delivery checklist](pre-delivery-checklist.md), section 1, lists.

**Sizing.** The balanced split, the wide-visual split, the narrow centered column, action as visual, and list as visual declare `min-height: calc(100dvh - var(--nav-height))` when the nav sits in the page flow. When the nav overlays the hero, they declare `min-height: 100dvh`. `nav-height` is a Frame token in the [`DESIGN.md` template](design-md-template.md). Below 60rem every posture drops its minimum height and shrinks to its content. Only the full-bleed image MAY stay full-screen there.

Choose the posture from the page's job, not from habit. Record its slug from the table in section 2 in the `hero:` field of the [build record](build-record.md). The `rep-03` row of the [rule catalog](rule-catalog.md) compares that slug, with the nav, footer, and opening section, against the build log.

Copy beside a picture is the posture generated pages fall into by default. The split fires `lay-04.a`. A waiver is accepted only when the picture is the brief's strongest real asset, named in the record's `signature:` field. Otherwise choose another posture.

## 2. Eight postures

| # | Posture (`hero:` slug) | Layout | Suits |
|---|---------|--------|-------|
| 1 | **Balanced split** (`balanced-split`) | Fills the screen below the nav (the sizing rule in section 1). Copy on 6 columns, visual on 6, both centered vertically. | A product whose picture carries the page. |
| 2 | **Wide-visual split** (`wide-visual-split`) | Copy on 5 columns, visual on 7 at the size in section 6. The visual MAY bleed past the outer edge. Give the copy the 7 columns when a headline set at `text-display` needs the room. | Screens, objects, and photos that reward size. |
| 3 | **Short header** (`short-header`) | Ends at the short-header limit in section 3, so the first section shows above the fold. | Reference material, docs, and utilities. |
| 4 | **Bottom-anchored** (`bottom-anchored`) | A full-height field with the headline set at its foot. At 1920 wide the headline reaches its maximum size before anything else grows. | Statement pages, studios, and events. |
| 5 | **Narrow centered column** (`narrow-centered-column`) | Fills the screen below the nav (the sizing rule in section 1), one column no wider than 44ch. With no picture, type is the hero's main visual, so the headline MAY take the type-as-visual ceiling in the display exceptions of the [`DESIGN.md` template](design-md-template.md), "Reference scale". | One message, one action. |
| 6 | **Full-bleed image** (`full-bleed-image`) | A photo or canvas at 92 to 100dvh. Copy sits on the image's quietest area with room around it, low-left or centered, never jammed into a corner. | Places, rooms, food, and work that sells by sight. |
| 7 | **Action as visual** (`action-as-visual`) | The action itself, set large beside or below a shorter headline. Examples: a sign-up field beside the newest issue, open booking slots, a purchase box with options, a download beside a screenshot. | Subscribe, book, buy, and try jobs. |
| 8 | **List as visual** (`list-as-visual`) | The content list forms the hero under a small headline: a line-up, a menu, issues, projects. | Pages people visit for the list itself. |

A custom hero is allowed. It names itself `custom` in the record. It is exempt from `hro-01.b`, `hro-01.c`, the last three points of section 3, the ratio of section 4, and the height flag of section 5. `hro-01.a` applies to it, and so do the text budget and the entrance rule.

## 3. Fold fit

**At 1280x800 (`hro-01.a`).** The headline, the supporting line, the primary action, and the visual's point of interest all show without scrolling.

**At 1440x900.**

- The hero SHOULD equal one screen: the next section begins between y=760 and y=900.
- The vertical centers of the visual and the text block stay inside the split center offset in [layout and composition](layout-and-composition.md), "Balance and height".
- The gap from text to visual is no more than `section-1`.
- The visual does not hug the window edge.

The full-bleed-image, bottom-anchored, and short-header postures, and custom heroes, are exempt from the last three points. The short header is also exempt from the first and follows its own limit instead.

**Short-header limit.** At 1440x900, a short header SHOULD end so that the first section begins between y=450 and y=540.

**At 1920x1080.** The container holds its maximum width, and the hero still fits the screen.

## 4. Vertical balance

Measure two painted spaces: above the content (nav bottom to the first hero element) and below it (the last hero element to the next section).

- **Ratio.** Below divided by above SHOULD fall between 1.0 and 1.5. This applies to the balanced split, the wide-visual split, the short header, the narrow centered column, action as visual, and list as visual.
- **Bottom-anchored** reverses the ratio: the space sits above.
- **Full-bleed image** is exempt when its copy is anchored on purpose. Custom heroes are unconstrained.
- **Fold proximity** (`hro-01.b`). At 1280x800, the lowest hero element ends within 160px of the fold. The clause fires only on the balanced split, wide-visual split, narrow centered column, action-as-visual, and list-as-visual postures. It does not fire on the short header, bottom-anchored, full-bleed-image, and custom postures, since each one ends away from the fold by design.
- **Dead band** (`hro-01.c`). At 1440x900, the empty space below the lowest hero element stays at 160px or less. Measure it from that element to whichever comes first, the fold or the hero's bottom edge. Every posture is checked except bottom-anchored, full-bleed-image, and custom.

Spare height goes to a larger visual or larger type. It MUST NOT be filled with more copy (`hro-00.4`).

**Order of the two checks.** On a posture that both the ratio and fold proximity cover, grow the type or the visual until both hold. When the content cannot reach both, fold proximity (`hro-01.b`) holds. The ratio is then a polish finding, closed by an `ack` line that names the content limit ([rule catalog](rule-catalog.md), "Exception lines").

## 5. Height units and centering

These are flags under `hro-00.5`:

- A hero sized in plain `vh`. Size it in `dvh` or `svh`; plain `vh` makes mobile layouts jump as the browser bar moves.
- A hero whose declared `height` or `min-height` exceeds `100dvh` minus the height of a nav in the page flow (`var(--nav-height)`, or zero when the nav overlays the hero). The `full-bleed-image`, `bottom-anchored`, and `custom` postures are exempt.
- A hero whose title, intro, action, and image are stacked on one center line. That four-item centered stack is the stock hero.

Prefer at most two centered items, plus one item placed off the axis on purpose: aligned to the margin, set flush right, or hung from a numeral. Atmospheric and playful genres ([surface classes](surface-classes.md)) MAY use a centered canvas.

## 6. The visual

- **Size.** The visual spans 6 or 7 columns and stands at 60% of screen height or more: at least 540px tall at 1440x900. An upright object, such as a cover, a phone, or a bottle, MAY instead stand at 75% of screen height over 4 or 5 columns.
- **Alignment.** At 1440x900, its center meets the split center offset that section 3 cites.
- **Grid.** The hero grid has two tracks and its own gap, matching the posture: `1fr 1fr` for the balanced split, `5fr 7fr` for the wide-visual split. The gap alone separates copy from visual. It runs from `space-8` to `section-1`. On narrow screens the gap turns vertical at `space-7`. Every gap comes from a spacing token (`tok-01`), whose value the [`DESIGN.md` template](design-md-template.md), "Reference scale", sets.
- **Subject.** The visual shows the actual subject: the room, the cover, the product, the dates ([imagery and data](imagery-and-data.md)). It stays inside the accent budget (`col-01.a`, [color and surfaces](color-and-surfaces.md)). A still weighs under 2MB; video follows [imagery and data](imagery-and-data.md), section 12. When it moves, it has a reduced-motion fallback (`acc-08`).
- **Forms.** A working form belongs in a later section or the close, not in the hero by default. The action-as-visual posture is the exception.
- When the visual misses a check, change the visual. Do not change the copy to compensate.

### A hero without a visual

A type-only hero takes one of two routes:

- grow the headline across 8 to 12 columns to `text-display`, or to the type-as-visual exception in the [`DESIGN.md` template](design-md-template.md), "Reference scale", when type is the hero visual; or
- take the short-header posture, so the first section begins inside the short-header limit in section 3.

## 7. Text budget

- Headline: within the headline budget in [copy and honesty](copy-and-honesty.md), section 2 (`cpy-05`). Its setting follows the headline-length bands in [typography](typography.md), section 6.
- One lead sentence, within the subhead budget in the same section (`cpy-05`).
- One or two actions. Exactly one is primary (`lay-06.a`, [page anatomy](page-anatomy.md)).

Nothing else goes in the hero: no badges, no feature bullets, no second paragraph. The linked announcement that [copy and honesty](copy-and-honesty.md), section 7, allows sits outside the hero, in the nav strip or above it. Word choice follows [copy and honesty](copy-and-honesty.md).

Narrow-screen sizing is in section 1.

## 8. Entrance

- One settling movement (`mot-01.a`).
- The entrance, stagger included, MUST meet the page-load reveal total in [interaction and motion](interaction-and-motion.md), section 13.6 (`hro-00.8`). Section 13.6 gives the formula and the ceiling; section 13.3 gives only the duration tokens and the stagger spacing.
- It starts from a state that is already visible. Content shows with script off, and a reveal hides content only under a class that script adds (`prf-02`).
- A fade plus an 8px rise counts as one movement. Fade, sweep, and scale MUST NOT be layered on one element (`hro-00.8`).
- No pointer-driven parallax (`mot-00.13.8`). No bounce or spring easing outside the playful waiver of `scl-00.genre-registers`. No starfields.
- No carousel that advances by itself. Hero motion that runs past the time limit of `acc-11` meets that row.
- Under reduced motion the hero appears in its final state. See [interaction and motion](interaction-and-motion.md).

## 9. Hero-first build stage

The opening screen gets the closest scrutiny, so it is built and settled before the rest of the page. This stage runs only where the "Hero stage" entry of the [rule catalog](rule-catalog.md), "Flags and downgrades", says. A restyle or polish pass has no hero stage; it edits the whole page and runs the finish review alone (same section).

1. Build the nav and the hero alone. Write nothing below the fold yet.
2. Run the static checks. Then take the first-screen captures that the [pre-delivery checklist](pre-delivery-checklist.md), section 1, lists, saved and named as that section sets, and run the hero-stage checks ([rule catalog](rule-catalog.md), "Flags and downgrades"). A dev server starts only under the run gate in [SKILL.md](../SKILL.md), "Agent operations", "Run gate", with the approval Step 0 obtained; without it, follow that section. A render check that cannot run grades `not checked` with its reason from the catalog's "Grades" section, "`not checked` reasons".
3. Pass the hero review inputs to the [`design-critic`](../../../agents/design-critic.md) subagent in review mode, in a fresh context with no memory of the build. The pre-delivery checklist, section 3, "Hero review inputs", is the only list of those inputs; it also gives the action for each verdict. The builder passes the path of `review-protocols.md` without reading that file.
4. Spend this stage's share of the verification budget; the [pre-delivery checklist](pre-delivery-checklist.md), section 2, sets it per stage. Build below the fold once the hero has no open `fail`, `habit-open`, or `warn`, or once that budget's last point is met.

Photo credits and whole-page checks wait until the full page exists ([pre-delivery checklist](pre-delivery-checklist.md)).
