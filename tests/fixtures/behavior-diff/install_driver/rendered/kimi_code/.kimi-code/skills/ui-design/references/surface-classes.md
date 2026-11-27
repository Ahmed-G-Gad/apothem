<!-- SPDX-License-Identifier: MIT -->

# Surface Classes

Reference for the [`ui-design`](../SKILL.md) skill. Every build is classified on two axes before shaping begins. **Scope** says how much is being built: a component, a page, or an app screen. **Genre** says what register a page speaks in: editorial, product-minimal, atmospheric, or playful. Scope picks the rule set. Genre picks the defaults inside it. Every build writes both into the `scope:` and `genre:` fields of its build record (see [build-record.md](build-record.md)). When a `DESIGN.md` exists, it carries them too (see [design-md-template.md](design-md-template.md)).

## Reading older DESIGN.md files

Earlier files name one of four classes. Read them through this map; do not rewrite them unless the user asks.

| Old class | Read as |
|-----------|---------|
| operate | App scope |
| read | Page scope, using the prose shapes in [page-shapes.md](page-shapes.md) |
| persuade | Page scope; route the genre by keyword below |
| experience | Page scope; route to atmospheric, or to playful when the brief asks for it |

## Scope detection

### Component scope

Each of these is one signal:

- The ask names one element. That can be a control: a button, input, select, checkbox, switch, slider, or date picker. It can also be an overlay (modal, popover, tooltip, dropdown), a small container (card, chip, badge, avatar, banner, snackbar, tab strip, form), or a lone nav or footer.
- The target file holds one component.
- The user says "only the X" or an equivalent.

Two of these three signals confirm component scope. One signal alone is not enough, so an ambiguous ask, such as "a pricing section", gets one clarifying question. If the user does not answer, or the run is headless, an ask with one signal is treated as a component; this default overrides the two-signal rule. An ask with no signal is page scope.

### App scope

A working screen is app scope: a dashboard, admin area, console, settings view, or tool. Two more signals: the screen sits behind a login, or tables, forms, and controls cover more than half of its area at 1440 wide.

Everything else is page scope. Pages follow [page-anatomy.md](page-anatomy.md), [page-shapes.md](page-shapes.md), and [hero.md](hero.md).

## Component scope

Keep: intake, genre, the project's existing tokens, the family limits of [typography](typography.md), section 1, and `cpy-04`.

Skip: page structure, nav and footer chrome (the stock-chrome clauses `cpy-00.10` and `cpy-00.11`), hero, page-level imagery, and the build log. The layout and imagery reference files still load, since their baseline rules grade for components too. A component is not logged and never counts toward rotation. The rules it skips grade `not checked`, with the reason "scope". The [rule catalog](rule-catalog.md), section "Flags and downgrades", is the only list of them and of the partial checks a component keeps.

Deliver two things:

1. The component, written to the project's existing conventions for file layout, naming, and styling. When the build writes no stylesheet, the build record opens the component's own source file ([build record](build-record.md), section 1).
2. A preview file that stacks every interactive state, each in its own labeled row.

The preview MUST show, for each control, every state its kind needs under the `lay-02` row of the [rule catalog](rule-catalog.md), which is the only list of those sets. Each row forces its state through a helper class. The preview stylesheet repeats each state rule under its helper class, for example `.btn.is-hover`. The reviewer then sees every state at once, and the live states still work. Helper classes live only in the preview file's stylesheet, so the component's own CSS keeps its ring on `:focus-visible` alone (`acc-03`).

## App scope

### Rules that change

- The page rules an app screen skips grade `not checked`, with the reason "scope". The [rule catalog](rule-catalog.md), section "Flags and downgrades", is the only list of them.
- Keep the baseline: accessibility, tokens, contrast, focus, states, and honesty (see [rule-catalog.md](rule-catalog.md) and [copy-and-honesty.md](copy-and-honesty.md)). `cpy-04` still applies.
- The direction supplies palette, type faces, radius, and surfaces only. It never supplies layout or decoration.
- One type family is enough. A familiar sans or the system face is fine.
- Use the fixed `app-text-*` steps that the [template](design-md-template.md), section "Reference scale", sets at its one app ratio, plus `text-base`, `text-sm`, and `text-xs`. `typ-00.6` checks app screens against that set ([typography](typography.md), section 6). Headings do not scale fluidly.
- A display face, if any, stays off labels, buttons, and data.
- The accent marks three things only: the main action, the current selection, and status. A second neutral fills sidebars, toolbars, and panels.

### Shell and navigation

- Reuse the shell the project already has.
- A new shell starts as a top bar. Move to a sidebar only past seven destinations. Collapse the sidebar into a menu below 60rem.
- Prefer standard patterns, such as tabs, breadcrumbs, and a command palette, over invented ones.
- Use a modal only after inline editing and disclosure are ruled out.

### Density

- Controls MAY stand at the app heights in [interaction and motion](interaction-and-motion.md), section 4, when the hit area still meets `tgt-04`. Every control also meets `tgt-01`.
- In a dense row or toolbar where hit areas that size would overlap, the `tgt-04` guard applies: name the region in `declared:` and close the finding with a waiver line.
- One container recipe serves the whole screen. Where it trips `col-02.a`, its guard is the recipe named in `declared:` as the direction's surface treatment. Only an accepted waiver line closes that finding ([rule catalog](rule-catalog.md)).
- Prefer tables to cards. A table MAY run wider than the prose measure.

### Data states

Every region fed by data MUST have each data-region state the `lay-02` row names, designed and seen. Loading and empty follow [interaction and motion](interaction-and-motion.md), section 10. Error and empty copy follow [copy and honesty](copy-and-honesty.md), section 4. A screen with only its populated view is unfinished. In a redesign, build the states the code supports. Hand the rest to the owner as a list.

### Behavior

- Filters, tabs, and pagination live in the URL, so a screen can be shared and restored.
- A destructive action is undoable or confirmed.
- Motion only signals a change of state. It keeps to the app durations in [interaction and motion](interaction-and-motion.md), section 13.3, toasts and modals included, and never runs as a sequence.
- A statistic shows the product's own figure: a number set in tabular figures with its label beside it. Leave out icon tiles (`img-02.c`) and gradients. Show a trend arrow only for a measured trend (see [imagery-and-data.md](imagery-and-data.md)).
- The screen still needs a signature: the one object the tool is known for, such as a ledger, a timeline, or a queue. A welcome line over four stat cards is not a signature.

## Genre routing

Route each page or component silently by keyword. Do not ask unless two genres collide.

| Genre | Keywords |
|-------|----------|
| Atmospheric | AI, generative, music, video, voice, dark |
| Product-minimal | SaaS, enterprise, API, platform, developer tool, infrastructure, B2B |
| Playful | playful, fun, friendly, soft, children, games, community |
| Editorial | Everything else, including consumer and family prompts that ask for neither fun nor softness |

- Editorial is the quiet default.
- Product-minimal also applies when the user supplies a brand color and the prompt otherwise reads as restrained.
- Once a direction is recorded in the build record's `direction:` field, its genre takes over (see [direction-and-themes.md](direction-and-themes.md)).
- If keywords for two non-default genres both appear, add one either/or question to intake, or choose one and say which.
- On a page this skill did not build, a tie resolves to product-minimal, said aloud, and every habit rule grades against that genre ([rule catalog](rule-catalog.md), "Flags and downgrades").

## Genre registers

Each register sets accent footprint, layout, motion, copy voice, allowed and refused devices, and suitable chrome. Chrome lines name only the nav and footer slugs of [copy and honesty](copy-and-honesty.md), sections 10 and 11. A refused device that cites no id grades as `scl-00.genre-registers`, in every register. Color detail lives in [color-and-surfaces.md](color-and-surfaces.md); type detail lives in [typography.md](typography.md).

### Editorial

- **Accent:** one, kept to its posture's footprint.
- **Layout:** asymmetric, with large type and thin rules instead of card borders. Column spans such as 4+8 and 3+9.
- **Motion:** quiet, with one orchestrated entrance.
- **Copy:** specific, with one literary turn per section at most. Verbs over adjectives.
- **Allowed:** hairlines, printer's flowers, drop caps, double rules, italics in running text, asymmetric columns, treated photos with factual captions, headlines set to an edge, one highlighter band behind the lowercase letters.
- **Refused:** gradient pills; a fully centered hero, unless the material is itself a centered poster; frosted glass (`col-02.b`); pure black or pure white tokens (`col-03.b`).
- **Chrome:** nav `masthead` or `edge-split`; footer `colophon` on the prose-document and manifesto shapes, `dated-signoff` on the letter shape, otherwise `closing-sentence`.

### Product-minimal

- **Accent:** the ink itself, or one hue limited to focus and one control. It fills large areas only when a posture says so.
- **Layout:** wide product shots and slim visible borders. A split hero still fires `lay-04.a`. Its guard is met only when the product view is the brief's strongest real asset, named in `signature:`, and a waiver line closes it.
- **Motion:** minimal. Reveals off.
- **Copy:** declarative and technical. Names its audience concretely.
- **Allowed:** pill controls, primary filled in ink and secondary outlined; untinted neutrals; a surface with a subtle border and 8px radius; large, tight display type. Pure white paper is allowed under the `col-03.b` exemption in [color and surfaces](color-and-surfaces.md), section 1.
- **Refused:** italic serif body text; hairlines everywhere; asymmetric prose columns; ornament; overshooting easing; gradient text (`typ-02.a`); glass (`col-02.b`); terminal styling used as decoration when the product is no developer tool; monospace labels as the page's voice.
- **Chrome:** nav `three-part-bar`, `floating-capsule`, `mega-menu`, `search-first`, or `edge-split`; footer `paragraph-credits`, or `sitemap-columns` for a hub with a real sitemap.

### Atmospheric

- **Accent:** one hue, on the canvas treatment and focus rings. Accent on display text is flagged (`scl-00.genre-registers`); a waiver line that meets the material guard, naming the accented word, closes it.
- **Layout:** canvas first, tool second. A centered hero works when type is the visual. A visual beside the text is a split hero and fires `lay-04.a`. Its guard is met only when the visual is the brief's strongest real asset, named in `signature:`, and a waiver line closes it. Display type takes the [template](design-md-template.md)'s type-as-visual exception only when type is the hero visual.
- **Motion:** fades only.
- **Copy:** direct and specific. One figurative line on the first screen at most.
- **Allowed:** fixed radial glows within the count and coverage limits of [color and surfaces](color-and-surfaces.md), section 4; a blurred backdrop only behind a `floating-capsule` nav; a centered hero; accent-filled pill controls; elevation through lightness steps.
- **Refused:** colored glow shadows, a spotlight behind the hero, mesh gradients, light sections inside a dark build, a third hue, glass cards (`col-02.b`), gradient text (`typ-02.a`).
- **Chrome:** nav `floating-capsule`, `edge-split`, or `search-first`; footer `closing-sentence`.

### Playful

- **Accent:** gentle and low in chroma by default. A `multi-role` or `saturated-surface` posture, recorded in the build record's `color:` field, lifts chroma to the playful ceiling in [color and surfaces](color-and-surfaces.md), section 1. That chroma is spread over named roles that each do a different job, as section 2 of that file sets for the posture.
- **Layout:** rounded surfaces, soft offset shadows, alternating tinted bands. Default radii: 12px `radius-card`, 8px `radius-field`, `radius-pill` for controls.
- **Motion:** responds to the pointer. One small entrance. Spring or bounce easing is flagged (`scl-00.genre-registers`); a waiver line that meets the material guard closes it for the moments it names.
- **Copy:** warm and concrete. Never whimsical for its own sake.
- **Allowed:** soft offset shadows; a hover lift on cards that are links (`mot-01.b`); one moment of character; emoji inside a sentence. When every lifted card is a link, `mot-00.13.9` does not fire.
- **Refused:** saturated pink or violet outside a `multi-role` or `saturated-surface` posture recorded in `color:`; cartoon typefaces; frosted glass (`col-02.b`); gradient-filled text (`typ-02.a`); ornamental status dots (`cpy-06`); sticker pills everywhere. A hard offset shadow is refused too; a waiver line that meets the material guard closes it.
- **Chrome:** nav `slab`, `floating-capsule`, or `announcement-strip`; footer `oversized-wordmark`. A solid `floating-capsule` works; a blurred one does not.

## Dials

The user's setting always wins. Where the user set none, take the default below and state it in the closing report. The build record's `motion:` field records the dial and whether the user set it.

| Scope or genre | Variance | Motion | Density | Character | Motion pattern |
|----------------|----------|--------|---------|-----------|----------------|
| Component | from the host project | subtle | from the host project | brisk | state feedback only |
| App screen | conventional | none | compact | severe | state change, two shortest tokens |
| Editorial | distinctive | subtle | airy | calm | one orchestrated entrance |
| Product-minimal | balanced | none | comfortable | brisk | reveals off |
| Atmospheric | distinctive | subtle | airy | calm | fades only |
| Playful | balanced | subtle | comfortable | brisk | pointer response, one small entrance, springs only by waiver (`scl-00.genre-registers`) |

- **Variance** is how far the design departs from familiar patterns. `conventional` reuses standard layouts. `balanced` keeps standard structure and spends distinctiveness on type, color, and imagery. `distinctive` allows unusual layout and needs a reason in the brief.
- **Motion** sets how much moves. **Motion pattern** names what moves. `none` means no decorative motion: state changes still animate, on the two shortest duration tokens. Every effect beyond state feedback needs a reduced-motion path (`acc-08`).
- **Character** is the default motion character: `still`, `severe`, `brisk`, or `calm`. It scales every duration token ([interaction and motion](interaction-and-motion.md), section 13.4). A direction's Motion line MAY name another, and `DESIGN.md` records it in `Character:`.
- `expressive` is never a genre default. Only a user-set `expressive` dial, recorded in `motion:`, meets the guard of `mot-01.a`.
- **Density** is how much fits per screen. `compact` keeps the house hit area (`tgt-04`) and never drops below the `tgt-01` floor.
