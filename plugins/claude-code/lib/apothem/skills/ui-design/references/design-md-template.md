<!-- SPDX-License-Identifier: MIT -->

# DESIGN.md Template

Reference for the [`ui-design`](../SKILL.md) skill. This file holds three templates and the token rules. `DESIGN.md` is the optional locked system. The token sheet and the base sheet are the two stylesheets every build writes by hand; no scaffold command exists. Rule ids come from the [rule catalog](rule-catalog.md). This file's catch-all is `tok-00`.

## 1. DESIGN.md, the locked system

`DESIGN.md` is optional. It freezes a design system so later pages, and other projects, reuse it instead of choosing again. A normal single-page build does not write it.

- Write it in two cases only: the user asks for it (lock the system, export the tokens, make it portable), or a multi-page [redesign](redesign.md) needs one shared system. The user's approval of a house-style entry counts as asking for it: when no `DESIGN.md` exists yet, the skill writes it from the token sheet with that one entry. A `Variants` entry needs an existing `DESIGN.md` and never creates one ([rule catalog](rule-catalog.md), section "Scope of taste"). Never write it for a component: a component's house-style proposal goes into the closing report alone ([rule catalog](rule-catalog.md), section "House style").
- Put it at the project root, unless the pre-flight scan finds an established home for design context.
- Its build log, `design-log.md`, sits beside it ([build record](build-record.md)). Both belong to the project and are committed.
- Generate it from the token sheet (section 2), not from the direction's source notes. Its `Tokens` section copies the role tokens the direction sets; the reference scale stays in the token sheet. A filled file runs 50 to 80 lines.
- Never overwrite an existing `DESIGN.md`. A later run refreshes its `Exports` section and nothing else. The system itself changes only by the user's own edit, or by an entry the user approved, such as a house-style proposal from the rule catalog. After the user approves an entry, the skill adds it to the matching section and changes nothing else.
- Every run looks for it first. When it exists, it is the direction. It outranks a candidate direction and a captured brand ([direction and themes](direction-and-themes.md)).
- Pages share the system; they do not vary it. A real exception goes into `Variants` after the user approves the entry, and the code then reads the variant's token. The [rule catalog](rule-catalog.md), section "Scope of taste", sets how a page-local override grades and what a build without `DESIGN.md` changes instead.
- It holds decisions, never reasons. Each build's reasons go on the `why:` line of its log entry.
- The skill's working state never lives in it or beside it. The pre-flight cache, redesign before-records, and the cached brand spec go in `<project-root>/.apothem/ui-design/`, which stays out of version control ([build record](build-record.md)).

Habit guards read the build record's `declared:` field, and the `Declared` section of `DESIGN.md` when one exists. Naming a device in either place closes no finding by itself; only an accepted waiver line does, and only where the [rule catalog](rule-catalog.md) allows a guard ("The material guard"; "Exception lines").

Copy this block and fill it in:

````markdown
# Design

## System
Genre: <genre, per surface classes>
Opening shape: <the first page's shape, per page shapes>
Direction: <source>; <axes code>; <colorway or default>; <mood phrase, per SKILL.md Step 1>
Posture: color <posture>

## Tokens
```css
:root {
  /* copied from the token sheet: each role token the direction sets, at its current value */
}
```

## Controls
Primary: fill <token>; ink <token>; radius <token>; height <px>
Secondary: fill <token or none>; border <token>; radius <token>; height <px>
Field: border `field-edge`; radius <token>; height `field-height` at <px>

## Motion
Dial: <none | subtle | expressive>
Character: still | severe | brisk | calm

## Declared
<device or outlier face>: <its one job, and the default it replaces>, or none

## Variants
<page or section>: <what differs>, or none

## Exports
Token sheet: <path>
Base sheet: <path>
Build log: <path to design-log.md>
Other: <W3C token JSON path, framework theme path, component-library map path>, or none
````

- `Direction` follows [direction and themes](direction-and-themes.md). `Posture` records the color posture from [color and surfaces](color-and-surfaces.md), section 2, and nothing else. The hero posture, nav, and footer are chosen per page, so each page's [build record](build-record.md) and log entry hold them, and `rep-03` compares them there.
- `Dial` follows the dials in [surface classes](surface-classes.md). `Character` scales every duration token ([interaction and motion](interaction-and-motion.md), section 13.4).
- `Declared` uses the same entries as the build record's `declared:` field.
- A value nobody chose stays `TODO(clarify): ...`. Never invent a brand color or font (`cpy-02`).

## 2. Token sheet

The token sheet sits beside the project stylesheet. It joins the direction's role tokens to the shared reference scale below. Every page uses that scale.

### Rules

- Every color, font family, padding, margin, gap, and `z-index` value comes from a custom property declared in `:root` or in a direction block. A literal value for any of these elsewhere breaks `tok-01` (baseline).
- A value in one of the token-derived forms the [rule catalog](rule-catalog.md) lists under `tok-01`, "Token-derived forms", counts as coming from a token.
- The off-scale optical adjustments a page MAY carry are counted in the `tok-01` row. Each one is a single adjustment that a render showed was needed, such as nudging an icon onto a text baseline. Each carries the marker comment that row sets, on its own declaration.
- Declare every new token in the token sheet. A reference to an undeclared token breaks `tok-01`.
- When the project already names its tokens (its own background variable, a framework theme block), map the roles onto those names. Do not add a parallel set.
- The skill replaces the project's token file only on an explicit request to take over the whole system.
- In a utility-framework project, extend the framework theme. Do not write arbitrary inline values.

### Spacing conventions

- Space siblings with `gap`. Keep `margin` for breaking out of the flow.
- Spacing tiers and heading proximity follow the ladder in [layout and composition](layout-and-composition.md), "The ladder" (`pol-01`).

### Families and names

Name a token for its job (`ink`, `paper`, `accent`), never for its look (`black`, `blue-500`). A new token takes a job name the same way.

| Family | Group | Tokens |
|--------|-------|--------|
| Color | Grounds | `paper`, `paper-2`, `paper-3`; optional `field` |
| Color | Picture | `wash`; optional `wash-2` |
| Color | Text | `ink`, `ink-2`, `muted` |
| Color | Lines | `rule`, `field-edge`; optional `rule-2` |
| Color | Signal | `accent`, `accent-ink`, `focus`; optional `accent-2` |
| Color | Status | `error`, `success` |
| Type | Faces | `font-body`, `font-display`; optional `font-outlier` |
| Type | Fixed steps | seven steps, `text-xs` through `text-3xl` |
| Type | App steps | `app-text-lg` through `app-text-3xl`, for app scope only |
| Type | Fluid roles | `text-display`, `text-display-sm`, `text-section`, `text-title`, `text-lead` |
| Type | Display setting | `display-weight`, `tracking-display` |
| Space | Scale | `space-1` to `space-10` (see "Reference scale") |
| Space | Frame | `container`, `gutter`, `col-gap`, `nav-height`; optional `bar-height`, `strip-height` |
| Space | Controls | `field-height` |
| Space | Sections | `section-1`, `section-2`, `section-3` |
| Shape | Edges | `rule-hair`, `radius-card`, `radius-pill`; optional `radius-field` |
| Shape | Depth | `shadow-card` |
| Motion | Durations | `micro`, `short`, `long` |
| Motion | Curves | `ease-in-out`, `ease-out`, `ease-in` |
| Layers | Stack | `z-raise` up to `z-tip` (see "Reference scale") |

The direction fills the color, face, shape, and display-setting values ([direction and themes](direction-and-themes.md), section 3). `field-edge` is the border of a text field. In every mode it meets the `acc-01` non-text ratio against `paper` and against every raised surface a field sits on, and it never takes the `rule` value. [Color and surfaces](color-and-surfaces.md), section 6, re-derives it for dark mode. `wash` is the fill behind a picture position; when the direction sets none, the token sheet declares `--wash: var(--paper-2)`. `wash-2` is optional and gives that fill a second hue. `font-outlier` is optional; when the direction sets no outlier face, the token sheet declares `--font-outlier: var(--font-display)`. Curve and duration values are in [interaction and motion](interaction-and-motion.md), section 13.

### Reference scale

The space steps and the type steps below each follow a stated rule, so a missing step of either is derived, not guessed. The section tokens, `gutter`, `col-gap`, `nav-height`, and the floors of the display exceptions follow no rule. They are fixed choices, read from the code block, never derived.

- **Space.** Ten steps, `space-1` to `space-10`. Up to 16px the steps go 2px, then 4px apart: 2, 4, 8, 12, 16. From 16px up, each step is 1.5 times the one below, rounded up to a multiple of 8px: 24, 40, 64, 96, 144.
- **Ladder coverage.** These steps hold every token that [layout and composition](layout-and-composition.md), "The ladder", names. That section, not this one, assigns a step to each relationship.
- **Sections.** Gaps between sections, and band padding, use `section-1` to `section-3` only. Their values change at the two layout breakpoints, so a section gap never reads a `space-*` token.
- **Frame.** `container`, `gutter`, and `col-gap` hold the grid in [layout and composition](layout-and-composition.md). `nav-height` is the rendered height of the site nav, inside the range in [copy and honesty](copy-and-honesty.md), section 10; the code block below sets its default. The hero's minimum height and `scroll-padding-top` read it. A page with a sticky bottom bar declares `bar-height` at that bar's height, and `scroll-padding-bottom` reads it (`acc-13`). A page with a sticky or fixed announcement strip declares `strip-height` at the strip's height, and `scroll-padding-top` adds it.
- **Page ratio.** Pages step at a ratio of 1.2. This section is the only place that states a type ratio or a type value; other files cite it.
- **Fixed type steps.** Step n above the 16px body is 16 times 1.2 to the power n, rounded to the nearest whole pixel, then written in rem: 19, 23, 28, and 33px as `text-lg` to `text-3xl`. Below the body, `text-sm` (14px) and `text-xs` (12px) are set by hand for legibility, not by the ratio.
- **Step jobs.** `text-base` sets body text. `text-sm` sets the small role in [typography](typography.md), section 6: labels, captions, and metadata. `text-xs` sets secondary reading text, such as badge counts and legal lines, and sits at the floor `typ-00.8` checks. `text-lg` to `text-3xl` set fixed text inside a component or a panel, such as a stat figure or a price, where a fluid role would resize with the viewport.
- **App steps.** App scope uses one ratio, 1.125, and no range: 18, 20, 23, and 26px as `app-text-lg` to `app-text-3xl`, by the same rounding. Below them it keeps `text-base`, `text-sm`, and `text-xs`. `typ-00.6` checks app screens against this set.
- **Fluid type roles.** Each role grows in a straight line from its floor at a 375px viewport to its ceiling at 1440px, then holds.
- **Fluid ceilings.** Display 84px, smaller display 64px, section heading 48px, item title 28px, lead 22px.
- **Fluid floors.** Divide each ceiling by 1.25 once per step and round to the nearest 2px. The 1.25 is a floor divisor, not a scale ratio. The display roles drop three steps, the section heading two, and the title and lead one.
- **Fluid slope.** The middle term of each `clamp()` is that straight line, with both numbers rounded to two decimals.
- **Zoom rule.** Every fluid `clamp()` here meets the ratio limit and the rem part that the `acc-09` row of the [rule catalog](rule-catalog.md) sets, so the text still grows under browser zoom.
- **Display exceptions.** Only these sizes go above the 5.25rem display ceiling. None is a scale step. Each is a full `clamp()` built by the fluid-role rule: a straight line from its floor at 375 wide to its ceiling at 1440, with the rem part in the middle term. Each meets the `acc-09` ratio limit.
  - Type as the hero's main visual: `clamp(3rem, 4.51vw + 1.94rem, 6rem)`, 48px to 96px.
  - A one-word heading: `clamp(3.5rem, 6.01vw + 2.09rem, 7.5rem)`, 56px to 120px.
  - Poster scale and the one graphic-number opener share one size: `clamp(4rem, 7.51vw + 2.24rem, 9rem)`, 64px to 144px.
- **Field height.** `field-height` defaults to 48px on pages. At app scope the token sheet declares it at 40px instead. The allowed field heights for pages and app screens are in the field-height column of [interaction and motion](interaction-and-motion.md), section 4. An app field reaches `tgt-04` through its `<label>` or through a wrapping element that carries the `::after` extension of section 3 of that file, never through its own `::after`. The [rule catalog](rule-catalog.md) row `tgt-04` defines the hit area.
- **Status.** `error` and `success` below hold light-paper values. As text they meet the `acc-01` text ratio on any ground at L 85 or lighter whose chroma stays inside the paper and neutral rows of [color and surfaces](color-and-surfaces.md), section 1. At L 85 and the least favorable hue they measure 4.53:1 and 4.61:1, and both values sit inside sRGB. So `paper`, `paper-2`, and `paper-3` qualify while each stays at L 85 or lighter. On a darker ground, lower their lightness until the ratio holds again. A dark paper re-derives both by [color and surfaces](color-and-surfaces.md), section 6.
- **Layers.** Each layer sits 10 above the one beneath it, so up to nine local steps fit between any two.

```css
:root {
  --space-1: 2px; --space-2: 4px; --space-3: 8px; --space-4: 12px;
  --space-5: 16px; --space-6: 24px; --space-7: 40px; --space-8: 64px;
  --space-9: 96px; --space-10: 144px;
  --text-xs: 0.75rem; --text-sm: 0.875rem; --text-base: 1rem;
  --text-3xl: 2.0625rem; --text-2xl: 1.75rem;
  --text-xl: 1.4375rem; --text-lg: 1.1875rem;
  --app-text-3xl: 1.625rem; --app-text-2xl: 1.4375rem;
  --app-text-xl: 1.25rem; --app-text-lg: 1.125rem;
  --text-display: clamp(2.75rem, 3.76vw + 1.87rem, 5.25rem);
  --text-display-sm: clamp(2rem, 3vw + 1.3rem, 4rem);
  --text-section: clamp(1.875rem, 1.69vw + 1.48rem, 3rem);
  --text-title: clamp(1.375rem, 0.56vw + 1.24rem, 1.75rem);
  --text-lead: clamp(1.125rem, 0.38vw + 1.04rem, 1.375rem);
  --container: 1440px; --gutter: 64px; --col-gap: 32px; --nav-height: 64px;
  --field-height: 48px; /* optional, declared only when used: --bar-height, --strip-height, --radius-field */
  --section-1: 120px; --section-2: 144px; --section-3: 176px;
  --z-raise: 10; --z-pin: 20; --z-header: 30; --z-popover: 40;
  --z-dialog: 50; --z-toast: 60; --z-tip: 70;
  --error: oklch(48% 0.19 27); --success: oklch(44% 0.12 150);
}
@media (width < 60rem) {
  :root { --gutter: 24px; --section-1: 80px; --section-2: 96px; --section-3: 120px; }
}
@media (width < 40rem) {
  :root { --gutter: 16px; --col-gap: 16px;
          --section-1: 56px; --section-2: 72px; --section-3: 96px; }
}
```

| Layer | Holds |
|-------|-------|
| `z-raise` | Content that overlaps its neighbor, such as text set over a photo |
| `z-pin` | Sticky parts inside the content: table headers, a sticky pane |
| `z-header` | The sticky or fixed site header |
| `z-popover` | Menus, dropdowns, and listboxes |
| `z-dialog` | Modal dialogs and their backdrop |
| `z-toast` | Toasts and live status messages |
| `z-tip` | Tooltips and the focused skip link |

- A native `<dialog>` opened with `showModal()`, and any element shown through the Popover API, renders in the top layer, which ignores `z-index`. A tooltip, menu, or toast opened from inside a native modal renders inside the dialog or as a popover, never on a z-index layer; a status message that reports on the modal's work renders inside the dialog (`acc-10`). `z-popover`, `z-dialog`, and `z-tip` serve non-native fallbacks only.
- Stack with the named layers only. A raw `z-index` number breaks `tok-01`. A local step between two layers is written from the lower token, for example `calc(var(--z-pin) + 1)`.
- Breakpoint behavior beyond these values is in [layout and composition](layout-and-composition.md). Type roles and their elements are in [typography](typography.md).

## 3. Base sheet

The base sheet holds everything the baseline already settles, so a page does not repeat it. It contains:

- a short reset;
- `overflow-x: clip` on `html` and `body` (`lay-01`);
- a scrollbar, selection color, and caret color from direction tokens;
- a default focus ring in `focus`, drawn with `outline` on `:focus-visible` and absent at rest, so forced-colors mode repaints it (`acc-03`);
- headings with `text-wrap: balance` and the `ch` width caps in [typography](typography.md), section 6;
- paragraphs with `text-wrap: pretty` and a measure inside the body range in [typography](typography.md), section 8; the lead inside its range in section 6;
- a tabular-numeral utility class (`pol-04`);
- picture-container styles: a fixed aspect ratio, `object-fit: cover`, and the `wash` token behind the image ([imagery and data](imagery-and-data.md));
- the global reduced-motion override in [interaction and motion](interaction-and-motion.md), section 13.7 (`acc-08`).

### Writing the sheets by hand

For each build, write the token sheet and the base sheet beside the project stylesheet. Add the two import lines, tokens first. When the project already has a token file, extend it in place instead (section 2, "Rules"), and write only the base sheet entries the project lacks. When `DESIGN.md` exists, the token sheet copies its tokens unchanged. Then write the build record in the file and at the position that the [build record](build-record.md), section 1, sets. The two sheets and the record come before the nav and the hero. The picture swap script follows [imagery and data](imagery-and-data.md). After that, write only the page.

## 4. Framework mapping

### Utility framework, version 4

- Put the two imports after the framework's own import. Put the base sheet in the `base` layer; outside it, its element rules beat the utilities.
- Put face, text-size, tracking, radius, shadow, and curve tokens in a static `@theme` block. Their names already sit in the framework's namespaces (`--font-*`, `--text-*`, `--tracking-*`, `--radius-*`, `--shadow-*`, `--ease-*`), so they become utilities and stay variables.
- Color tokens carry no `--color-` prefix, so they stay in `:root`. An inline `@theme` block maps each one as `--color-<role>: var(--<role>)`, such as `--color-paper: var(--paper)`, and that mapping produces the color utilities.
- All other tokens stay in `:root`.
- Never put tokens in the framework's spacing namespace. That redefines the width and max-width utilities. Every `space-*` step above 2px is a whole number of the framework's 4px units.
- Ten token names clash with framework defaults: the seven fixed text steps and the three curves. That is fine for a new project or a full redesign. When adding one page to an existing project, scope those tokens to the page root.
- The framework strips comments, so read the build record from the source files.

### Utility framework, version 3

- Use one `:root` block. Put the build record and the imports above the framework directives.
- Put the base sheet in the `base` layer.
- Add utilities through `theme.extend`, with each value a `var()` reference.

### Headless component library

Map the library's variables to page tokens: background, foreground, card, popover, primary, secondary, muted, accent, destructive, border, input, ring, and radius. In that library, `accent` means a hover surface and `muted` means a quiet background. Both clash with the page's own meanings. Either leave the page's `accent` and `muted` out of the mapping or rename them. State which under `Exports` when `DESIGN.md` exists, and in the closing report otherwise.

## 5. Token JSON export

Only on request, export the tokens as W3C design-token JSON:

- group tokens by path (`color.paper`, `space.5`), with a `$type` on each;
- keep OKLCH values as strings; convert to hex only when the consumer requires it, and mark that conversion as lossy;
- export a fluid size at its ceiling; the `clamp()` stays in the CSS.

A token export is one of the requests that writes `DESIGN.md` (section 1). Record the JSON path under its `Exports` section.
