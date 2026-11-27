<!-- SPDX-License-Identifier: MIT -->

# Copy and Honesty

Reference for the [`ui-design`](../SKILL.md) skill. All scopes. It covers the words on the page, the chrome around them (labels, nav, footer), and what the page can claim. Rule ids and grades live in the [rule catalog](rule-catalog.md). A flag in this file that cites no id grades under the catch-all `cpy-00.<section>`. Control states and form behavior live in [interaction and motion](interaction-and-motion.md). Sample sections live in [page anatomy](page-anatomy.md).

## 1. Write like the owner talking

- Use the brief's own nouns, its real places, the user's figures, and the verb a customer would use ("book a table", not "secure your experience").
- Put three questions to every line. Can a reader picture it? Can it be proved false? Is it something only this business would say? A line that earns no yes is rewritten.
- A heading that a competitor can reuse word for word is rewritten around a noun only this product owns.
- Concrete beats clever. One pun per page at most.

## 2. Structure budgets

| Element | Budget |
|---------|--------|
| Headline | 7 words |
| Subhead | 12 words: what it is, who it serves, its one difference |
| Section heading | 6 words; says what the reader is about to see or get |
| Section intro | One line |
| Paragraph | Two short sentences |
| Bulleted list | 4 entries, each a three-word label plus a line of 12 words at most. A composition's rows keep that composition's own limits ([layout and composition](layout-and-composition.md), "Compositions") |
| Steps | 5 entries; more than that becomes a table; the process-steps composition keeps the stage limit of [layout and composition](layout-and-composition.md), composition 8 |
| Table | 5 rows of filler; the dense index composition and any set the user supplies keep their own limits ([layout and composition](layout-and-composition.md)) |
| Page | 450 visible words |
| Band | 80 visible words in each band. Render the full page at 1440 wide and cut it into consecutive 900 px bands from the top. Labels, captions, and table cells count |

- The headline, subhead, section heading, page, and band budgets grade under `cpy-05`; that row also names the shapes on which the page and band budgets do not fire. The other rows of the table grade as polish, as that row of the [rule catalog](rule-catalog.md) states.
- **What counts as a word.** A word is a run of letters or digits between spaces or punctuation, in text a visitor sees. Text marked `data-wordcount="skip"` is not counted. The marker is for credit lines only, such as a photo credit ([imagery and data](imagery-and-data.md), section 7).
- A set the user supplies keeps its real size. The budget governs filler, not facts.
- Category labels such as "Features", "Our story" or "Why us" are not headings.
- Read only the hero and the headings. If they carry the story, the length is right.
- Rhythm: mix short and longer lines, prefer verbs to adjectives, keep one thought per sentence, and never stack three adjectives.

## 3. Banned phrasing

The product's recorded name or term never matches any list below. A word used in its literal sense does not match either.

- **Stand-in names.** Placeholder person names and stock startup company names are placeholder text (`cpy-01`).
- **Banned words.** These words, used as praise, break the house rule `cpy-09`: `unlock`, `best-in-class`, `seamless`, `journey`, `next-generation`, `empower`, `mission-critical`, `effortless`, `world-class`, `supercharge`, `future-proof`, `elevate`, `industry-leading`, `unleash`, `robust`, `game-changer`, `reimagine`.
- **Stock cadences** (`cpy-07.a`). The "Not X. Y." rebuttal three or more times on a page; "whether you are X or Y"; "it is not just X, it is Y"; "say goodbye to"; a "quietly trusted by" line; titles built around a colon.
- **Stock openers** (`cpy-07.a`). Filler about modern teams, today's landscape, or the fast-moving world.
- **Stock button labels** (`cpy-07.a`). "Learn more", "Get started", "Book a demo", "Click here".
- **Instructions and noise** (`cpy-00.3`). "Enter your email below"; version numbers in marketing copy.
- **Dashes** (`cpy-06`). See section 9.
- A boilerplate "All rights reserved" footer line is a `warn` source under `cpy-00.3`. How it is checked and closed is in the [rule catalog](rule-catalog.md), "Grades".

## 4. Microcopy

- **Buttons** name the action with its verb: "Reserve", "Download the PDF". "Continue" is only for the second step of a flow.
- **Errors** say what went wrong, the cause when known, and the fix. No "oops", no exclamation marks.
- **Empty states** say what is missing, why it matters, and offer one action.
- **Loading** text is one short line that names the work in progress, such as "Saving your booking". The spinner, and the point where this line appears, follow [interaction and motion](interaction-and-motion.md), section 1.
- **Success** stays silent when the result is visible. Toasts are for errors and for results the user cannot see ([interaction and motion](interaction-and-motion.md)).
- **Links and headings.** A link's text, read alone or with its sentence, tells where it leads: "Read the spring menu", never a bare "here". A heading or label describes what it introduces (`acc-24`).
- **Other languages.** A phrase or passage in a language other than the page's own carries its own `lang` attribute. Proper names and technical terms need none (`acc-28`).

## 5. Punctuation

- Typographic quotes and apostrophes, and a real ellipsis glyph.
- No double hyphens, no em dashes, no en dashes (`cpy-06`). Use a comma, colon, period, or brackets.
- A range of numbers, dates, or times uses the word "to" ("9 to 5") or a hyphen with no spaces around it ("10-20").
- A non-breaking space between a number and its unit.
- Periods end standalone sentences. List items without a verb take none.

## 6. Repeated facts

- One fact (price, time, date, count) stated in 4 or more sections is a finding (`cpy-07.b`). Several mentions inside one section count once. The guard for long pages is in the `cpy-07` row of the [rule catalog](rule-catalog.md).
- A section whose last line only restates its heading is a finding (`cpy-00.6`).
- Tables and ledgers that repeat by design are exempt.
- State each fact once, where it is useful.

## 7. Announcer labels

An announcer label is a short, inert line set by a heading only to introduce it. It breaks the house rule `cpy-04`, whatever its form. The forms include a line stacked above, a line set beside, a pill, an ordinal ("01"), a category tag on a card, and a "trusted by" line over logos.

**Test.** Delete the line. If the only loss is a title for what follows, it was an announcer label.

**Allowed.** A line that holds a fact, a link target, or a name of record stays. These pass:

- Form and table text: `label`, `legend`, `th`, and `figcaption`.
- Navigation and tab labels.
- A timestamp or a byline; a unit after a number; a real file name.
- A live status chip.
- One linked announcement that leads to a real destination. It sits outside the hero, in the nav strip or above it.
- The name of a pricing plan.
- The sample notice in a sample section's `figcaption` ([page anatomy](page-anatomy.md)), since it states a fact: the content is not real.

Deletion alone is not the fix. When the heading below is figurative, promote the plain label to be the heading and drop the figure.

## 8. Twelve ways to open a section

First ask what the reader still lacks at this point. If nothing, open with nothing.

1. **Nothing.** The heading alone, with space above it.
2. **Subject-first heading.** Its first two words name the subject. This is the default.
3. **Bold run-in.** The first words of the paragraph set bold.
4. **Drop cap.** Once per page, on the first paragraph of a reading section.
5. **A divider that means something.** Rule, ornament, double rule, color edge, or a plain gap. Draw them from one divider vocabulary, and let the type of join pick the divider.
6. **One graphic number.** One per page, only when that number is the message and the user supplied it. It takes the poster-scale size listed in the display exceptions of the [`DESIGN.md` template](design-md-template.md), "Reference scale".
7. **A true ordered list** with CSS counters, for a real sequence.
8. **A caption under the content** instead of a label over it.
9. **Marginal notes** on the outer side.
10. **A background shift** whose edge does the separating.
11. **A running header or folio** along the page edge.
12. **A sticky heading** that stays while its content scrolls.

A section uses two openers at most. Besides the heading-only openers (types 1 and 2), a page uses one or two opener types. With two, adjacent sections alternate between them. With one, no two adjacent sections both carry it. Rotate the types against the `openers:` field of the log entries `rot-01` compares ([build record](build-record.md); the window is in the `rot-01` row of the [rule catalog](rule-catalog.md)).

## 9. Template punctuation and decoration text

The house rule `cpy-06` bans these patterns:

- Metadata strings joined by two or more middle dots.
- Arrows added to link or button text.
- Decorative status dots in front of labels.
- Labels shaped "WORD - fragment".
- Em dashes, en dashes, or double hyphens in copy.

Permitted: one dot inside a byline or caption, a dot that signals live status, and a separator inside a marquee. The static check fires at two dots. A single dot whose use the source does not name is left to the judgment half of `cpy-06`.

Decoration text that carries no information is a finding (`cpy-00.9`):

- Rotated vertical text.
- Scroll prompts.
- Version or beta badges in the hero.
- Weather or location strips.
- Monospace capitals strips under the hero.
- Credit captions under stand-in images.
- Tile counters such as "01 / 4".

The exception is a launch, venue, or studio spread across cities, where the text states a real fact. A real fact removed this way moves into a caption or the footer.

## 10. Navigation

The stock nav (wordmark left, links inline, button right, thin rule below; slug `stock-bar`) is flagged (`cpy-00.10`) unless the user asked for it. The `nav:` field of the [build record](build-record.md) records the style's slug either way.

Constraints:

- Except `masthead` and `side-rail`, one row, 56 to 80px high, set by the `nav-height` token and sized to the destinations the page has. No padding links.
- Links keep one weight in every state. Hover shows through color or a light background tint, never a filled primary button. Focus also shows the ring of [interaction and motion](interaction-and-motion.md), section 2 (`acc-03`).
- The current page's link carries `aria-current="page"` and a cue beyond color: an underline, a bar, or a shape change (`acc-02`).
- A tab row in the nav follows the overflow rule of [interaction and motion](interaction-and-motion.md), section 4.
- Below 60rem, links that do not fit move behind a menu.
- The logo links to the home page and has an accessible name.
- The root's scroll padding clears a sticky nav, a sticky `announcement-strip`, and a sticky bottom bar through their Frame tokens, as [layout and composition](layout-and-composition.md), "Overflow and stacking guards", sets. A focused element is then never hidden behind them (`acc-13`).
- Contact and help links keep one order relative to the rest of the page on every page of the site (`acc-18`).
- On every page a run builds, the nav keeps the same links in the same order, and a control that does the same job keeps the same name and icon (`acc-29`).

Variants, rotated against the build log, each with its `nav:` slug:

- `stock-bar`: the stock nav above, flagged (`cpy-00.10`) unless the user asked for it.
- `edge-split`: wordmark and links pushed to opposite edges.
- `floating-capsule`: a floating capsule.
- `masthead`: a large centered wordmark above a rule.
- `slab`: a heavy full-width slab.
- `search-first`: search first, with its keyboard shortcut shown.
- `announcement-strip`: an announcement strip over a bar that hides while scrolling down.
- `three-part-bar`: a three-part bar, only when four or more real destinations exist.
- `side-rail`: a side rail, used only when a sticky object justifies it.
- `mega-menu`: a full-width panel of grouped links that opens under the bar, only when the site has three or more real link groups.

## 11. Footer

The stock footer (four link columns, a social row, a copyright line; slug `stock-columns`) is flagged (`cpy-00.11`) unless the user asked for it. The `footer:` field records the style's slug either way.

- The footer is 200 to 400px tall; the colophon is exempt from that range. Its contents: the legal line, the links that exist on this page, and either the wordmark or a single closing sentence.
- The prose-document and manifesto shapes use a colophon instead (slug `colophon`): one line under a thin rule. A letter page uses `dated-signoff`.
- Contact details and help links in the footer keep the same order on every page of the site (`acc-18`).
- Footer links use body weight.

Variants, each with its `footer:` slug:

- `stock-columns`: the stock footer above, flagged (`cpy-00.11`) unless the user asked for it.
- `colophon`: the colophon above, on the prose-document and manifesto shapes.
- `oversized-wordmark`: an oversized wordmark above the links.
- `closing-sentence`: one large closing sentence with the links beneath.
- `paragraph-credits`: credits and address written as one paragraph.
- `signup-first`: sign-up first, on subscription pages only.
- `dated-signoff`: a dated sign-off, letter style.
- `sitemap-columns`: sitemap columns, only for a hub that has a real sitemap.

## 12. No invented proof

- Never invent metrics, testimonials, logo walls, customer names, awards, or case-study counts (`cpy-02`). Use the user's figure, a marked blank (section 13), or nothing.

## 13. Missing facts and unknown links

- A missing fact (venue, time, price) becomes a marked blank. It takes a muted color that still meets the `acc-01` text contrast against its ground. It carries a dashed outline, which `acc-03` allows because a blank takes no focus. Two to four words name the missing fact, such as "price to come". It imitates no content, so it is not placeholder text under `cpy-01`.
- A marked blank MUST NOT look like a link or a selected item (`cpy-00.13`). This is a baseline-subject section; how its sentences grade is in the [rule catalog](rule-catalog.md), "Grade words in topic files".
- At most 2 marked blanks per page. Each is listed at handoff ([build record](build-record.md)).
- When the category needs more facts than were given, keep blanks only for the two a visitor needs in order to act. Defer the rest to the handoff list.
- A row, column, or line whose only content would be a missing fact is deleted, not blanked.
- A section the user named but gave no content for gets three things: its heading, one sentence on what is coming, and one marked blank. Or it folds into a neighboring section. Never a stack of "coming soon" rows.
- That section's blank counts toward the limit of two. An empty picture position counts toward the picture limit instead ([imagery and data](imagery-and-data.md), section 8).
- A link with no given address points to the on-page section that best serves its purpose. The handoff lists the address needed. Never invent a route.

## 14. Forms with no endpoint

- A form with no known endpoint sets `method="post"` and no `action` address. The post method keeps typed values out of the URL and the browser history. The disabled button and the `preventDefault()` handler below keep anything from being sent; without them, the form would post to the current page.
- Its submit button ships with the `disabled` attribute, and a visible line beside it says the form has no backend yet. With the only submit button disabled, pressing Enter in a field sends nothing either.
- Script enables the button and adds a submit handler that calls `preventDefault()`. The form validates in the browser with useful messages and moves focus to the first problem field.
- On submit it says plainly that nothing was sent because the form has no backend yet. Typed input stays in place (`frm-02`). It shows no success state until it is connected.
- Faked success breaks the baseline rule `cpy-08`. That covers a "sent", "reserved", or "thank you" message when no request happened, and a confirmation of something never offered.
- The handoff lists the endpoint still needed.

## 15. Sample data, testimonials, and pricing

- **Sample data** inside a rebuilt product view uses `example.com`, the field names from the brief, and values that read as samples: round figures and generic labels such as "Project 1". Never numbers that read as claims. Stock company names and stand-in person names fall under `cpy-01`. Sample sections follow [page anatomy](page-anatomy.md).
- **Testimonials** appear only when supplied. Attribution aligns to the bottom of the block. The avatar is the real person or nothing (`cpy-02`). Pull quotes use hanging punctuation.
- **Pricing.** Mark the featured tier with its button and one word, not a card in another color. All tier buttons share one bottom line. When the featured tier stands taller, place it on explicit grid rows with its siblings. Never lift it with negative margins.

## 16. Model tics to refuse

Each is named by its symptom, and each is a finding. The detail rule sits in the linked file. A tic with no id of its own grades under `cpy-00.16`.

- Filler cards drawn as outlines only ([layout and composition](layout-and-composition.md)).
- Filler illustrations made of SVG or CSS shapes (`img-00.10`, [imagery and data](imagery-and-data.md)).
- Grain or noise spread as atmosphere (`col-00.8`, [color and surfaces](color-and-surfaces.md)).
- Stripes or grids repeated as backgrounds over empty space.
- Emoji as bullets (`img-02.a`).
- On any genre except product-minimal, the stock product look: a tight grotesk at weight 600 on paper of L 96 or lighter, one blue accent, a 1px border under a broad soft shadow ([color and surfaces](color-and-surfaces.md), section 7).
- Gradient ramps posing as material (`col-01.b`).
- A strong first screen whose third section turns into an identical card grid for unlike items (`lay-03.b`).
- A lone number as the whole hero headline, unless the user supplied it with its unit and source and the page is designed around it.
