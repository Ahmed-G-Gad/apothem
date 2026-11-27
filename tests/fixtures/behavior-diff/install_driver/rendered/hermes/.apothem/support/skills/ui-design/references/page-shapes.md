<!-- SPDX-License-Identifier: MIT -->

# Page Shapes

Reference for the [`ui-design`](../SKILL.md) skill. A page shape is a complete set of structural decisions for a page. The entries below name finished structures; they are not options to pick from. Rule ids come from the [rule catalog](rule-catalog.md). This file's catch-all is `shp-00`.

Name a shape by the steps in section 3; coin a kebab-case name when none matches.

- You MUST NOT start a build by picking from this list. Starting from the menu pulls every brief toward the same few shapes.
- Read only the entry of the shape that applies. Skip the others.
- Nav and footer are decided with the hero, as part of the shape ([page anatomy](page-anatomy.md), [hero](hero.md)).

## 1. The six-axis fingerprint

Every page reduces to one value on each of six axes. Write it as six values joined by ` / `, in this order, in the build record and the log entry.

1. **Heading position:** left margin; floating above in open space; centered display; anchored at the bottom; over a photo or color block; sticky; structural number (a real ordered list, or one large numeral); run into the prose.
2. **Body composition:** one column; two asymmetric columns with a caption margin; several justified, hyphenated columns; margin sidenotes; three equal columns; full bleed (a prose-led body, bleeding images, pull quotes); asymmetric spans such as 2-1-3.
3. **Divider language:** hairline (0.5px to 1px, inset or edge to edge); ornament; whitespace; color-block edge; double rule.
4. **Button voice:** one solid fill; outlined; underlined link; oversized solid; a typographic word alone; the form itself as the action.
5. **Image treatment:** bleeding off the page; cropped tight to the grid; inline; aligned to the margin; none.
6. **Reveal:** one fade-up stagger; horizontal sweep; clip-path text unmask; count-up (real figures only); typewriter (terminal context only, caret inside a command being typed); none.

Example: `left margin / one column / whitespace / underlined link / inline / none`.

Two traps on axis 1. A narrow, auto-centered heading over full-width, left-aligned content reads as a mistake. A label set beside or above a heading is an eyebrow, not a heading position.

### Coherence and anti-repetition

- **Coherence.** The six values MUST belong to one design world. A justified, newspaper-like body calls for a typographic action, not an oversized solid button.
- **Anti-repetition (`rot-01.b`).** A new page keeps its shared axes with the logged builds inside the limit of the `rot-01` row in the [rule catalog](rule-catalog.md). That row also holds the band and the only guard. The [build record](build-record.md) stores the fingerprint the check reads.
- When the direction or the material leaves no choice but `none` on the image or reveal axis, write that value `none (forced)`. The `rot-01` row says how the comparison treats it.

### One divider language, varied by seam

Pick one divider language per page. Vary its weight and position from seam to seam: a full rule here, an inset hairline there, a wider gap at the section that turns the argument. The same rule with the same gap at every seam is what makes a page look templated.

### One reveal per shape

- Each shape allows one reveal pattern at most (`mot-01.a`), on one element by default: the first caption, the first claim, or the first sample. Everything else is there.
- A page has at most one scroll-driven pattern (`mot-01.c`). A sticky or pinned sequence uses up that allowance.
- The final content is in the markup, and the page reads correctly with script off (`prf-02`) and under reduced motion (`acc-08`). See [interaction and motion](interaction-and-motion.md).

## 2. The shapes

Each entry gives what the shape is, where it fits, where it does not, and any hard condition. A hard condition is not negotiable: without it, the shape is not used. An uncited hard condition that is broken is flagged (`shp-00.2`). Figures and quotes follow [copy and honesty](copy-and-honesty.md); captures and placeholders follow [imagery and data](imagery-and-data.md).

- **Modular grid** (`modular-grid`). 6 to 9 blocks spanning 1x1, 2x1, 1x2, or 2x2, under a display heading. The grid starts inside the hero or as the first section after it. At 1440x900 its first row begins inside the window in [hero](hero.md), section 3. Grid gap only, no rules. An outlined button in the hero, verb-first text links on tiles. Images cropped tight inside blocks (columns `minmax(0, 1fr)`), never full bleed. No reveal, or one fade as the grid appears.
  - Fits: many equal entry points, such as feature pages and SaaS landings. Not for: one big idea.
  - Hard: figure and quote blocks exist only when the user supplied them (`cpy-02`).
- **Prose document** (`prose-document`). Reads as a memo, letter, or journal, with no marketing apparatus. Headings are short bold phrases that run into the paragraph. One column, at the prose-led measure and leading in [typography](typography.md), section 8. Whitespace divides, with one centered ornament at most. The action is a verb-first link inside a sentence, the only action on the first screen. That link meets `tgt-04` through the running-text exemption of its row in the [rule catalog](rule-catalog.md); `tgt-01` still applies. Images in the flow at text width. No motion.
  - Fits: case studies, founder essays, mission pages, products sold on a philosophy. Not for: transactional pages, where prose hides the actions.
- **Statement hero** (`statement-hero`). One huge statement or visual fills the first screen, pressed to the container edges, set at the poster-scale clamp in the display exceptions of the [`DESIGN.md` template](design-md-template.md), "Reference scale". Wrapping caps keep the all-caps leading in [typography](typography.md), section 7. Below the fold the page changes, to a work list or one content block, across a heavy rule or a hard background change. A small action and one sentence sit at the base. Type as the visual, or one edge-to-edge photo. The first screen is still; content below MAY slide in from the side.
  - Fits: portfolios, brands with one declarative voice. Not for: products whose value has to land in seconds.
- **Figure hero** (`figure-hero`). A large supplied number in tabular figures beside a real headline that says what it means. The number is never the only text and never labeled by a tiny caption. Later sections each rest on a supporting number or chart, divided by thin rules. A verb-led outlined button under the qualifier. Charts replace photos. The hero number MAY count up, only because it is real, following the number tick-up recipe and its range in [interaction and motion](interaction-and-motion.md), section 11; the markup holds the final value.
  - Fits: B2B, fundraising, impact reports. Hard: a supplied number with its unit and source.
- **Capture tour** (`capture-tour`). Real product captures, arranged as a guided walkthrough. Plain, functional headings at section size. Each capture is a figure with a factual caption and one inline annotation; the figures divide the page. No browser or device frame. One action in the hero; where the theme allows sticky elements, a bottom bar with that action appears after the third capture. The bar follows the sticky bottom bar rule in [layout and composition](layout-and-composition.md), "Overflow and stacking guards" (`acc-13`). One text unmask on the first caption.
  - Fits: SaaS, developer tools. Not for: conceptual or service products with no interface.
  - Hard: until real captures arrive, the product is rebuilt inside a placeholder position.
- **Question and answer** (`question-answer`). Each section is a short, direct question with a one- or two-paragraph answer, optionally in a disclosure. Thin rules or background changes between pairs. Verb-led links inside answers, one outlined action at the bottom, one diagram at most in a long answer. No load motion. Disclosures open with the accordion recipe in [interaction and motion](interaction-and-motion.md), section 11, the one layout animation that section 13.2 there permits. Standalone, the hero asks question one; otherwise it follows another opening shape.
  - Fits: next to pricing, skeptical readers, regulated or educational sectors.
- **Manifesto** (`manifesto`). Big uppercase display, level or rotated -2 to -4 degrees. One weight, one color; emphasis comes only from line breaks. A direction whose mark is a highlighted word MAY use it once, in the hero, under a `typ-03.b` waiver with the device named in `declared:`. Wrapping lines keep the all-caps leading in [typography](typography.md), section 7. Short paragraphs, one assertion each. Background changes or theme rules between sections, no cards. One solid accent button on the first screen, repeated at the bottom as the last word; with the same label and target it counts once (`lay-06.a`). No imagery for an idea; for a physical cause, at most one screen of photos in the theme treatment. Past the fold, the first claim MAY slide in sideways a single time; nothing else moves.
  - Fits: repositioning announcements, mission pages. Not for: checkout, pricing, product tours.
- **Photo-led** (`photo-led`). Full-width photos lead. Headline and one sentence sit on a small solid plate at the image base; a factual corner caption uses the body face. Full-bleed photo bands alternate with sections carried by the theme's material: a menu in rows, hours as a table, a statement. Image edges divide. A verb-led link on the plate is the only action. No spatial motion. Photos stay inside the photo-led share in [imagery and data](imagery-and-data.md), section 5 (`img-03.a`), and two photo-led sections never sit next to each other (`img-03.b`).
  - Fits: fashion, hospitality, photography, lifestyle. Not for: subjects with nothing to photograph.
  - Hard: until the user's photos arrive, placeholder positions hold open-archive photos fetched after the user approves ([imagery and data](imagery-and-data.md)).
- **Quote hero** (`quote-hero`). A supplied quotation, wholly italic at `text-display-sm`, never one italic word. Attribution in one quiet body-face line below, then a verb-led link. Body: further supplied quotes, case studies, or a modest feature list. Sections part with a short rule, or with a single quote mark set at the center. Only image: the person's photo, the company mark, or none. First screen still; content below MAY stagger in.
  - Hard: the quote is verbatim, with name, role, and company exactly as given. Never written or paraphrased (`cpy-02`).
- **Editorial serif** (`editorial-serif`). Large serif display phrases standing alone. A narrow margin column of captions, dates, and side notes beside a wide main column. Thin rules between sections. A plain text-link action: no box, fill, or arrow. Ordinals come from a real ordered list. No image, or one photo of printed type. A staggered fade-up on first load.
  - Hard: only for briefs about type, publishing, or writing, or when the user asks for it by name. An editorial tone alone does not qualify; this is the most imitated look, and reaching it from a vague brief means the brief went unread.
- **Variant grid** (`variant-grid`). Equal cards, 3 to 5 per row (columns `minmax(0, 1fr)`), each a variant of one core product: typefaces, palettes, SKUs. A one-line heading that does not push the first row below the fold. Thin rules between rows. Every card links to its detail page; no global action, so the first card's link is the first-screen action. Each card shows a supplied thumbnail or swatch. Without one, it shows an open-archive photo of that type of item, fetched after the user approves. Failing that, it uses type alone: name, a fact, price, and a swatch if variants differ by color. No empty frames. No motion.
  - Fits: type foundries, palette tools, capsule collections. Not for: brands with a product hierarchy.
- **Letter** (`letter`). First-person and intimate. Opens with a greeting in display italic, the whole line, set at the `text-title` role of the [`DESIGN.md` template](design-md-template.md), "Reference scale". Prose in one narrow column, as if typed, at the letter measure in [typography](typography.md), section 8. Paragraph spacing divides, with the odd three-asterisk break. No buttons: the first paragraph's inline link is the first-screen action, and a verb-led sign-off link closes the page. Both links sit in running text, so they meet `tgt-04` through its running-text exemption in the [rule catalog](rule-catalog.md); `tgt-01` still applies. Optional scanned signature or quiet inline photo. No motion. Pair with the `narrow-centered-column` hero ([hero](hero.md), section 2) and the `dated-signoff` footer from [copy and honesty](copy-and-honesty.md), section 11.
  - Fits: personal brands, founder announcements, pivots, appeals. Not for: commerce.
- **Link index** (`link-index`). The page is a categorized list of links, with no hero image and no narrative. A short heading names the index, its scope, and its order, with one line of support; the list starts on the first screen. An optional filter row or disclosure above it, no sidebar by default. Thin rules or paper bands between rows. Links do the work of buttons. An entry link set inside its line of descriptive text meets `tgt-04` through the running-text exemption in the [rule catalog](rule-catalog.md); an entry link that stands alone in its row meets the house target itself. At most one photo of the collection, plus small marks beside entries. No motion.
  - Fits: documentation hubs, knowledge bases, archives, large link pages. Not for: a hard sell.
- **Workflow stages** (`workflow-stages`). Numbered stages of how the user works with the product over time. The number lives in the heading or comes from an ordered list, never a separate label, and never sits on a rule. Each stage: a short explanation and one full-size object that meets the visual mass height in [layout and composition](layout-and-composition.md), "Width and mass", of a different kind per stage (capture if supplied, else a figure or rows from the brief). Rules between stages. The hero action returns once at the bottom and counts once (`lay-06.a`). Optional sideways reveal on stage one, or a pinned sequence instead.
  - Hard: a real sequence. With one screenshot or none, stages MUST NOT each get a placeholder position; a page holds no more empty positions than [imagery and data](imagery-and-data.md), section 8, allows (`img-04.a`).
- **Diptych rows** (`diptych-rows`). Each block splits in two: text on one side, proof (a capture or supplied quote) on the other. Proof stays on one side, mirrored once at most, never zigzagging. Rows differ by weight, not side. The first row leads, and its proof takes the wider span; later rows alternate 6/6 and 5/7, so neighbors never share a ratio. All rows keep one column gap. A clean gutter, no rules. An outlined button under the text. In the hero, the two parts fade in a single time, the second starting one block stagger after the first ([interaction and motion](interaction-and-motion.md), section 13.3).
  - Fits: SaaS feature pages, developer tools pairing prose with code. Not for: narrative or photo-led brands.
- **Sticky pane** (`sticky-pane`). A left pane holds the heading while the right pane scrolls 3 to 6 detailed captures per section, paced like film. The pane re-anchors per section, offset below any sticky nav. The action appears in the pane at the section's last capture; without script it is always visible. No fades: the sticky scroll is the page's one scroll pattern. Below 60rem the pane becomes a heading over its stacked captures.
  - Fits: premium products, detailed feature stories. Risky for mobile-first readers unless the fallback holds.
- **Typeface demo** (`typeface-demo`). The face is the design. The hero sets it at three sizes; the body walks through display size, text size, italic, language support, and OpenType features. Each sample has a caption under it, never a label over it. One outlined purchase action on the first screen and again at the bottom. No imagery. One text unmask on the first sample.
  - Hard: a custom or distinctive face.
- **Project cards** (`project-cards`). Project cards in a responsive grid (columns `minmax(0, 1fr)`), equal or varied in span, under a short line that is not display type. A filter row above is the only divider. Each card links to its case study; no global action, so the first card's link is the first-screen action. Cards fade when filters change.
  - Fits: studios, agencies, photographers. Not for: products.
  - Hard: thumbnails come from the user's portfolio. Until then, list projects in type with one placeholder position at most.
- **Spatial diagram** (`spatial-diagram`). One large SVG diagram, built from the real places or system, organizes the page: a flowchart, floor plan, network, or system map. Nodes, edges, legend, and hover states. Every node hover state also opens from keyboard focus (`acc-15`). Every node that holds a link is reachable by keyboard (`acc-04`). Labeled, or hidden from assistive technology beside a text legend that carries every fact. An orienting section-size heading above or beside it holds the page's one action, on the first screen. Links live in nodes. No internal dividers. Up to 5 nodes draw in once as it enters. Below 60rem it scrolls sideways in a wrapper or becomes an ordered list of its nodes.
  - Not for: replacing a narrative.
- **Multi-rail front** (`multi-rail`). Stacked sideways-scrolling rails or grids, each a different slice of a platform's content: featured, newest, by category, by creator. A short positioning line, no display type. Each rail opens with a real heading, not a label strip, and ends with a verb-led "view all" link; the first rail's link is the first-screen action. Thin rule or background change between rails. Dense, real thumbnails. No motion.
  - Fits: community platforms, marketplaces, asset libraries. Not for: single-product pages.
- **Code and preview** (`code-preview`). Interactive blocks, each a live preview above its code, under sentence-case category headings. A framework tab row MAY sit above the blocks; it scrolls sideways on narrow screens. Background changes between categories, thin rules between examples. Each code block has a copy button whose label turns into a confirmation in place, with no toast. Previews are the imagery, plus one photo band at most. Monospace only inside code. No motion.
  - Fits: design systems, component libraries. Not for: marketing pages.

## 3. Selecting a shape

0. **Material first.** List what exists: captures, figures, quotes, photos. A shape that needs material gets it real or as a requested placeholder position. Without either, choose a shape that runs on type and facts.
1. **Brief phrases.** Find the phrases that point at a shape: "data-heavy", "tell our story", "a list of links", "lots of small features", "a personal note".
2. **History (`rot-01.a`).** Read the [build log](build-record.md) and any build record on existing pages. Exclude every shape the `rot-01` row of the [rule catalog](rule-catalog.md) would flag, unless the user named it.
3. **Candidates.** Match the brief to 2 to 4 candidates. Take the one furthest from recent history. Read only that entry.
4. **State it once** in the decision summary and once in the build record.
5. **No brief phrase.** When step 1 found no phrase that points at a shape, use the domain row below and take the candidate furthest from the log.

Keep the chosen structure unless the material conflicts with it. Name any substitution and its reason in the decision summary and the build record.

Rotation against the build log (`rot-01`) keeps two briefs from producing one template in two colors.

### Domain fallback

Use this table only when step 1 finds no brief phrase that points at a shape. Map the brief's domain to three candidates. Rows mix the grid-led, document-led, poster-led, and product-led families; never swap in a close sibling of a candidate. Take the one furthest from the latest logged shape.

| Domain | Candidates |
|--------|------------|
| Audio, podcast, music | photo-led, quote-hero, letter |
| Shop, commerce | variant-grid, photo-led, modular-grid |
| Docs, CLI, SDK, API, open source | capture-tour, prose-document, code-preview |
| Platform, infrastructure, observability, B2B tooling | modular-grid, capture-tour, figure-hero |
| Agency, studio, portfolio | project-cards, diptych-rows, link-index |
| Personal, about, CV | prose-document, letter, link-index |
| Restaurant, cafe, food | photo-led, prose-document, variant-grid |
| Fashion, beauty, lookbook | photo-led (real photos), variant-grid, statement-hero |
| Fintech, banking, payments | figure-hero, capture-tour, prose-document |
| Cause, campaign, advocacy | manifesto, quote-hero, figure-hero |
| Editorial, foundry, magazine, type | editorial-serif, prose-document, typeface-demo |
| Product launch, SaaS marketing | modular-grid, capture-tour, figure-hero |
| Conference, event | statement-hero, manifesto, photo-led |
| No signal | modular-grid, prose-document, manifesto |

- Use the stated purpose to tell developer docs from developer marketing, and a one-pager from a portfolio.
- Read vague tone words such as "modern" or "clean" through the genre ([surface classes](surface-classes.md)). State the reading; do not ask another question.

## 4. Opening-line specificity

Each shape's first line has a typical level of detail. Copy the level, never the wording ([copy and honesty](copy-and-honesty.md)).

| Shapes | First line carries |
|--------|--------------------|
| modular-grid, capture-tour, diptych-rows, sticky-pane | Category and promise in five words or fewer |
| code-preview, capture-tour for a CLI | A timestamp or a real command |
| variant-grid, multi-rail, project-cards, link-index | A count of real things: items, years, clients |
| link-index for an archive | The date range it covers |
| workflow-stages | Process verbs |
| manifesto | A definition by what it refuses |
| photo-led | A caption with plate number, date, and place |
| typeface-demo, editorial-serif | The face, its weights, and its use |
| figure-hero | The user's figure paired with what it made possible |
| prose-document, letter, quote-hero, question-answer, statement-hero, spatial-diagram | One concrete fact from the brief, never a general claim |
