<!-- SPDX-License-Identifier: MIT -->

# Rule Catalog

Reference for the [`ui-design`](../SKILL.md) skill. This file governs every check. It sets the band of each rule, the grade of each finding, the way each check is made, and the way an exception is written down. The detail of a rule lives in the file named in its row. This file does not repeat that detail.

**One home per value.** Every number, threshold, size, duration, ratio, token value, and exemption list has exactly one home file. Any other file cites that home by file and section instead of restating the value. This file is the home for grades, bands, guards, ids, check classes, the `not checked` reasons, downgrade lists, the baseline, baseline-subject, and material-guard section lists, and the exception-line syntax. It is also the home for the WCAG thresholds in the baseline rows and the state sets of `lay-02`. It holds the `tgt-04` house target with its hit-area definition, scope, and exemptions, the `typ-01` house limits, the `tok-01` token-derived forms and optical-adjustment marker, and the rotation and bookkeeping thresholds. Every other value lives in the file named in the row's Detail column.

## Bands

The skill holds its work to a banded floor. Every rule belongs to exactly one band. The band decides two things: whether the rule can be set aside, and whether a finding against it blocks shipping. The baseline is the strictest band.

| Band | Holds | Can it be set aside? | Blocks shipping? |
|------|-------|----------------------|------------------|
| baseline | Accessibility, correctness, honesty, token discipline, and the house rules | Never | Yes, as `fail`; `rds-02` alone grades `warn` and blocks until it closes |
| habit | Defaults a model picks without a reason | Only by a waiver for one clause | Yes, as `habit-open` |
| polish | Craft details | No; a fix or an acknowledgment closes each one | No |
| bookkeeping | Repetition against earlier builds | Not needed | No; it never touches the verdict |

The house rules are five stylistic checks moved into the baseline. Each one marks a page as machine-made at a glance: announcer labels (`cpy-04`), the word budget (`cpy-05`), template punctuation (`cpy-06`), banned buzzwords (`cpy-09`), and tracked small labels (`typ-01`). A house rule binds as firmly as a contrast threshold.

## Grades

Each finding gets one grade. The table lists the eleven grades in the order the `grades:` field of the [build record](build-record.md) counts them. That field carries exactly one count per row, under the row's name.

| Grade | Meaning | Closes when |
|-------|---------|-------------|
| `fail` | A baseline rule is broken | The page is fixed |
| `habit-open` | A habit clause fired and no accepted waiver covers it | The page is fixed or a waiver is accepted |
| `warn` | A check suspects a breach and cannot settle it on its own | By one of three routes, named per source below: a fix; an accepted dismissal; or, for a `judgment` check, an accepted confirmation line. For `rds-02` only, an accepted drop line also closes it |
| `waived` | A habit clause is set aside; the report shows the reason | Already closed |
| `dismissed` | A `warn` was judged false; the report shows the reason | Already closed |
| `confirmed` | A `judgment` `warn` that the user confirmed in chat, recorded by a confirmation line with the user's words | Already closed |
| `dropped` | An `rds-02` loss kept on purpose and recorded by a drop line; the report shows the reason | Already closed |
| `acknowledged` | A polish finding was seen and kept; the report shows the reason | Already closed |
| `open polish` | A polish finding not yet fixed or acknowledged | A fix or an acknowledgment line. It never blocks |
| `not checked` | The check did not run here, for one of the reasons below | Never; it stays listed and does not block |
| `note` | Information only | Never needs closing |

**`not checked` reasons.** Each `not checked` item names exactly one of these reasons:

| Reason | When |
|--------|------|
| no browser | The host offers no browser tool |
| no app | The host has a browser, but no page can be opened: no server ran under the run gate and the user supplied no running URL |
| no tool | The check needs a computation and has no route ("Checks that need a computation"). Or it measures a position, size, or area, and the host offers neither the browser's page geometry nor an image tool ([pre-delivery checklist](pre-delivery-checklist.md), section 1). Or it needs an emulation the browser cannot apply, such as forced colors, `(pointer: coarse)`, network throttling, reduced motion, a user style sheet, or a grayscale or blur filter |
| fast mode | `mode: fast` skips the band |
| scope | Component or app scope skips the rule |
| custom | A custom direction skips the rule |
| before mode | Before mode skips the rule (section "Flags and downgrades") |

**Shipping rule.** A page MUST NOT ship while any `fail`, `habit-open`, or open `warn` remains. Open polish findings and `not checked` items do not block, and the report lists every one of them. The report counts `fail` and `habit-open` apart, so "zero fails" never hides an open habit finding.

**Exemptions are not skips.** When a row exempts a shape, a posture, or a genre, the clause does not fire there. It produces no finding and no `not checked` entry.

**`warn` is for suspicions only.** A check that settles its breach grades `fail`, `habit-open`, `note`, or polish, never `warn`. The full list of `warn` sources:

| Source | Check | Closes by |
|--------|-------|-----------|
| `rds-02`, a lost content item | static | A fix (restore), or a drop line |
| `img-00.12`, a lazy-loaded hero video or first image | static plus render | A fix, or a dismissal stating the item is not the largest paint at any sweep width |
| `cpy-00.3`, a boilerplate "All rights reserved" line | judgment | A fix, or a confirmation line: the owner wants the line kept |
| A topic sentence worded "warns" or `warn` with no row above, under its file's catch-all | as the sentence needs | A fix or a dismissal; a confirmation line only when the check is `judgment` |

A measured soft limit is not a `warn` source. The accent band of `col-01.a` grades `habit-open`.

## Grade words in topic files

The topic files state rules in prose, and most sentences name no id. This table maps their wording to a grade and an id, so no rule in them is left ungoverned.

| Wording in a topic file | Grade | Id when the sentence cites none |
|-------------------------|-------|---------------------------------|
| The sentence cites a rule id | The grade that id's band gives | The cited id |
| "fail", "fails", "hard failure", "defect" | `fail`, but only beside a baseline id. Without one, the wording is a defect in the topic file, and the rule grades as the next row | None |
| MUST, MUST NOT, "flag", "flags", "flagged", "banned", "refused", "is a finding" | `habit-open` | The file's catch-all, `<code>-00.<section>` |
| "warns", `warn` | `warn` | The file's catch-all, `<code>-00.<section>` |
| SHOULD, "never", "always", or a plain instruction | `open polish`, except in the sections the two tables below list | `pol-00.<code>-<section>` |
| `note` | `note` | None |

**A cited id decides.** A sentence that cites a rule id takes that id's grade, whatever its wording. "Flag an `h2` ... (`pol-01`)" grades as `pol-01`, polish, not as a catch-all flag. The wording rows apply only to a sentence that cites no id. One exception holds: inside a section the two tables below list, a cited id of a lower band never lowers the grade. In a baseline section that means any id outside the baseline band; in a baseline-subject section, a polish or bookkeeping id. Such a sentence grades as its table row says, and the citation is a defect in the topic file.

**Baseline sections.** Every sentence in the sections below grades at the baseline band: `fail` under the listed id. A procedure sentence is the one exception: it is not a page check (list below). Its wording does not matter: MUST, "never", "always", and a plain instruction all grade the same. A sentence there that cites its own baseline id takes that id instead. A baseline section holds no SHOULD and no advice, such as an "aim for" value, so no sentence in it grades as polish or `note`.

| File | Section | Id |
|------|---------|----|
| [color and surfaces](color-and-surfaces.md) | 3. Contrast | `acc-01` |
| [copy and honesty](copy-and-honesty.md) | 12. No invented proof | `cpy-02` |
| [copy and honesty](copy-and-honesty.md) | 14. Forms with no endpoint | `cpy-08` |

**Baseline-subject sections.** The sections below treat a baseline subject: honesty, focus, forms, page access, overflow, both color modes, sources and licenses, or tokens. Every sentence there that cites no id grades `habit-open` under the file's catch-all, with the guard "none", whatever its wording. A procedure sentence is the one exception, as in the baseline sections. It never drops to polish and can never be waived. A sentence there that cites its own baseline or habit id takes that id; a cited catch-all clause there also has the guard "none". These sections hold no SHOULD and no advice, so no sentence in them grades as polish or `note`.

| File | Section | Catch-all clause |
|------|---------|------------------|
| [interaction and motion](interaction-and-motion.md) | 2. Focus ring | `mot-00.2` |
| [interaction and motion](interaction-and-motion.md) | 6. Form behavior | `mot-00.6` |
| [interaction and motion](interaction-and-motion.md) | 8. Page-level access | `mot-00.8` |
| [interaction and motion](interaction-and-motion.md) | 12. Feedback honesty | `mot-00.12` |
| [layout and composition](layout-and-composition.md) | Overflow and stacking guards | `lay-00.overflow-and-stacking-guards` |
| [color and surfaces](color-and-surfaces.md) | 6. Dark mode, "Check both modes" | `col-00.6` |
| [copy and honesty](copy-and-honesty.md) | 13. Missing facts and unknown links | `cpy-00.13` |
| [imagery and data](imagery-and-data.md) | 1. Where pictures come from, "Openly licensed photographs" and "Pictures never stand in for facts or people" | `img-00.1` |
| [`DESIGN.md` template](design-md-template.md) | 2. Token sheet, "Rules" | `tok-00.2` |

Outside the two tables, a sentence grades by its citation, then by its wording, and nothing else. A topic file that states a baseline requirement outside them cites the baseline id.

- A sentence about procedure is not a page check, whatever its wording and in every section, the two tables above included. Procedure covers the order of steps, how scope, genre, shape, and direction are chosen, what the handoff lists, and which section governs. It also covers how to measure, which tool a value comes from, and how a fetch is made and which addresses it can reach. The report names any breach of it.
- A catch-all sentence that states its own exception ("unless ...") does not fire while the exception holds. An exception that holds only because `declared:`, the recorded direction, or `DESIGN.md` names a device is not such an exception: the sentence fires, and only an accepted waiver line that meets the material guard (section "Habit") closes it.
- A sentence that cites a lettered clause takes that clause's catalog row as written. The clause fires whenever its condition holds. Its guard takes effect only through an accepted waiver line, never as an "unless" or "otherwise" in a topic file.
- The section part of a clause is the section number. A numbered subsection uses its full number, for example `mot-00.13.8` and `pol-00.mot-13.5`. An unnumbered subsection takes the number of the section it sits in. A file with unnumbered sections uses the heading in kebab case, for example `lay-00.section-gaps`.
- The guard of a catch-all clause follows the sentence the waiver quotes, not the clause id alone. One id can cover sentences in different subsections, and each sentence takes the guard its own subsection gives (section "Habit"). A sentence that cites a catch-all clause owned by another section or file points to the owning section: its grade, its guard, and any `warn` route are the owning sentence's, and a waiver quotes the owning sentence.

Each topic file has one file code. Its catch-all habit rule is `<code>-00`. The checklist's own uncited SHOULDs use `pol-00.chk-<section>`; its polish list uses `pol-00.chk-list-<n>`, so the two never share an id.

| Code | File | Code | File |
|------|------|------|------|
| `lay` | [layout and composition](layout-and-composition.md) | `col` | [color and surfaces](color-and-surfaces.md) |
| `hro` | [hero](hero.md) | `mot` | [interaction and motion](interaction-and-motion.md) |
| `pag` | [page anatomy](page-anatomy.md) | `img` | [imagery and data](imagery-and-data.md) |
| `shp` | [page shapes](page-shapes.md) | `cpy` | [copy and honesty](copy-and-honesty.md) |
| `typ` | [typography](typography.md) | `dir` | [direction and themes](direction-and-themes.md) |
| `scl` | [surface classes](surface-classes.md) | `tok` | [`DESIGN.md` template](design-md-template.md) |
| `rds` | [redesign](redesign.md) | `chk` | [pre-delivery checklist](pre-delivery-checklist.md) |

Two references carry procedure and record format only, so they have no file code: the [build record](build-record.md) and the [review protocols](review-protocols.md). Every MUST in them is a procedure MUST, and they hold no SHOULD. A rule id they cite grades as its own row says.

## Check classes

The `check` column in the index says how a rule is settled.

| Class | Settled by |
|-------|------------|
| static | Reading CSS and markup, including utility-class strings inside components |
| static plus render | A static read, then a measurement in a rendered browser |
| static plus judgment | A static read, then a reading of the captures or the source for the cases the static read names as open |
| render | A rendered browser only |
| render or judgment | A rendered browser when one is present; otherwise a reading of the source |
| judgment | A reviewer's reading of the captures, or of the source when nothing renders |

After the static pass, only `judgment` rules and the judgment half of `static plus judgment` and `render or judgment` rules are walked by hand. Nothing the static pass settled is checked again by hand. The [pre-delivery checklist](pre-delivery-checklist.md) says how each check is made and records how it ran.

### Hosts with no browser

The skill's own tools include no browser. When the host offers none:

- Static checks and judgment checks run, and they gate shipping as usual.
- Render checks grade `not checked`, with the reason "no browser". They do not block.
- A `static plus render` rule is graded on its static half. Its render half is `not checked`.
- A `render or judgment` rule is judged from the source, and the report says so.
- The report labels the delivery "render not verified". The Return Contract's `checklist` row lists every `not checked` item.

Do not drive a desktop browser by hand to stand in for the render pass.

A host with a browser follows the same list with the reason "no app" when no page can be opened: no server ran under the run gate, and the user supplied no running URL. When the browser runs but cannot apply an emulation a render row needs, only that row grades `not checked`, with the reason "no tool".

### Checks that need a computation

Some static checks need arithmetic the skill's own tools cannot do, such as a contrast ratio computed from OKLCH token values. The [pre-delivery checklist](pre-delivery-checklist.md), section 1, names the routes for such a computation. When no route is available, the check grades `not checked` with the reason "no tool", and the report gives no number for it.

The same routes serve every color conversion and gamut fit a reference asks for, such as a brand hex converted to OKLCH, or a chroma lowered until the value sits in sRGB. With no route, the skill asks the user for the converted value, or keeps the value in the form it arrived in and names it unconverted in the report. It never converts by hand.

A measurement of a position, a size, or an area follows the same rule. It comes from the browser's page geometry or from an image tool the host offers ([pre-delivery checklist](pre-delivery-checklist.md), section 1). An estimate by eye from a capture is not a measurement: with neither tool, the check grades `not checked` with the reason "no tool".

### Running project code

No reference starts a development server, runs a project script or check, or launches a simulator on its own authority. Each such step runs only under the run gate in `SKILL.md`, section "Agent operations", which Step 0 applies; every reference that names such a step cites that gate and Step 0. A capture made with any tool other than the host's browser is host-conditional, and the reference that asks for it names it as such. Examples are a web view's debugging port, the operating system's screenshot tool, and a simulator. When the host lacks the tool, the needed screens go into the material request.

## Precedence

When guidance disagrees, the higher level wins. The lower level is adjusted to fit, not dropped.

1. The user's explicit words, and the baseline. When the two conflict, the baseline holds. The skill names the conflict and offers the nearest option that passes.
2. The direction: the project's `DESIGN.md`, a captured brand, or the chosen candidate. A direction supplies material: palette balance, typographic voice, surfaces, and what it can render without photographs. It never sets content or section order. See [direction and themes](direction-and-themes.md) and the [`DESIGN.md` template](design-md-template.md).
3. Shape, genre, and craft defaults, from [page shapes](page-shapes.md), [page anatomy](page-anatomy.md), and the topic files.

Inside one band, a conflict breaks by the fixed category order below. The [surface class](surface-classes.md) changes the effort each category gets, never the order.

| Rank | Category | Rank | Category | Rank | Category |
|------|----------|------|----------|------|----------|
| 1 | Accessibility | 4 | Layout and responsiveness | 7 | Forms |
| 2 | Touch and pointer targets | 5 | Typography and color | 8 | Navigation |
| 3 | Performance | 6 | Motion | 9 | Data display |

Example: a brand color that fails contrast is a direction value against a baseline rule, so level 1 wins. The token is darkened, or the text moves to a surface that passes.

## Rule index

Ids are stable. A rule that moves band keeps its id. A deleted rule's id is retired and never reused, so older [build records](build-record.md) still decode. Retired ids: `pol-00.chk-list-1`, `-2`, `-6`, `-8`, `-9`, `-10`, and `-11`. Each of those polish items now grades under its home file's own id; the [pre-delivery checklist](pre-delivery-checklist.md), section 5, maps each one.

### Baseline

The accessibility rows (`acc-01` to `acc-30`, `tgt-01` to `tgt-03`, and the SC citations in `img-01`, `frm-01`, and `frm-02`) cover the WCAG 2.2 level A and AA success criteria (SC) that the interfaces this skill builds touch. Each row cites its SC by number. Three criteria are out of scope. Live captions (SC 1.2.4) and motion actuation (SC 2.5.4) cover content and input the skill never builds. Multiple ways to find a page (SC 2.4.5) belongs to a site's structure, which the user owns. A row that asks for more than WCAG AA labels that part "Beyond WCAG". The stricter house pointer target is the habit rule `tgt-04`.

| Id | Rule | Check | Detail |
|----|------|-------|--------|
| acc-01 | Contrast holds in every shipped theme, at WCAG AA or at the host's or brief's stated target, whichever is stricter. The AA ratios follow; a stricter stated target, such as AAA, replaces them. Text that is not large needs 4.5:1 (SC 1.4.3). That covers labels, captions, button text, placeholder, helper, and muted text, and marked blanks ([copy and honesty](copy-and-honesty.md), section 13). Large text needs 3:1. Large means 18 pt (24 px) or more, or 14 pt (18.66 px) or more at weight 700 or heavier. Non-text needs 3:1 against adjacent colors (SC 1.4.11). That covers meaningful icons, focus indicators, and the chart marks and data series needed to read a chart. A chart mark whose value a direct text label also states is exempt. It also covers a control boundary that is the only visual cue identifying the control, such as a field edge. A button whose visible label identifies it needs no 3:1 boundary. The SC exceptions hold: pure decoration, logotypes, and a disabled control, so the ratios bind enabled states only. A focusable disabled control is never exempt from `acc-03`. A perceptual-contrast figure is advisory and never replaces the ratio | static plus render | [color and surfaces](color-and-surfaces.md) |
| acc-02 | No meaning carried by color alone (SC 1.4.1) | render or judgment | [color and surfaces](color-and-surfaces.md) |
| acc-03 | Every interactive element shows a visible focus indicator (SC 2.4.7). The indicator reaches 3:1 against every color it touches (SC 1.4.11). A ring set outside the element touches the backdrop. A 2 px ring set inside at an offset of -2 px paints over the element's border, so it touches the backdrop outside the element and the element's fill inside; it meets 3:1 against both. Beyond WCAG: the indicator stays visible in forced-colors mode, so it is drawn with `outline`, which forced colors repaint. No focusable or interactive element carries a visible or transparent outline at rest, since forced colors would paint it and a resting ring would read as focus. An element that takes no focus, such as a picture frame or a marked blank, MAY draw its edge with `outline`. A `box-shadow` ring is paired with a transparent `outline` on `:focus-visible` only. The skill does not claim the AAA focus-appearance area of SC 2.4.13 | static plus render | [interaction and motion](interaction-and-motion.md) |
| acc-04 | Everything works by keyboard, in reading order, with no trap (SC 2.1.1, 2.1.2, 2.4.3). Beyond WCAG, dialogs return focus to their trigger | render | [interaction and motion](interaction-and-motion.md) |
| acc-05 | Native elements first; ARIA names, roles, and states are accurate (SC 4.1.2) | static | [interaction and motion](interaction-and-motion.md) |
| acc-06 | Icon-only controls have accessible names, and images have fitting alternative text (SC 1.1.1, 4.1.2). A control with visible text has an accessible name that contains that text (SC 2.5.3) | static plus render | [imagery and data](imagery-and-data.md) |
| acc-07 | `lang` on the root element (SC 3.1.1), a page title in the page's own words (SC 2.4.2), and landmarks (SC 1.3.1). Beyond WCAG: one page heading, and heading levels in order with none skipped | static | [pre-delivery checklist](pre-delivery-checklist.md) |
| acc-08 | Beyond WCAG AA: the reduced-motion preference removes travel, parallax, and zoom (relates to SC 2.3.3, AAA) | static | [interaction and motion](interaction-and-motion.md) |
| acc-09 | Usable at 200 percent zoom (SC 1.4.4), and at 320 px wide with no two-way scrolling (SC 1.4.10). The SC exception holds: a part that needs a two-dimensional layout for its use or meaning, such as a data table, a map, or a diagram, MAY scroll inside its own container while the content around it reflows. A rail or carousel passes when each of its items fits a 320 px viewport. Beyond WCAG: every fluid `clamp()` type size keeps its maximum at 2.5 times its minimum or less, and its middle term carries a rem part, so text grows under zoom | static plus render | [layout and composition](layout-and-composition.md) |
| acc-10 | Status messages and other dynamic changes are announced through a live region (SC 4.1.3). Beyond WCAG: while a modal dialog is open, everything outside it is inert, so a status message or toast about the dialog's work renders inside the dialog | static | [interaction and motion](interaction-and-motion.md) |
| acc-11 | Moving, blinking, or scrolling content that starts on its own, runs longer than 5 seconds in total, and shows beside other content has a visible control that pauses, stops, or hides it (SC 2.2.2). The total counts every repeat, so a short loop that repeats past 5 seconds is covered. A loading indicator is exempt while its load runs and the content beside it cannot be used. Content that updates on its own, such as a live ticker, a feed, or a refreshing score, shown beside other content, has a control to pause, stop, or hide it, or to set its update rate (SC 2.2.2). Audio that plays on its own for more than 3 seconds has a control to pause or stop it, or to set its volume apart from the system volume (SC 1.4.2). Beyond WCAG: such motion also pauses on hover and focus, and media that plays on its own is muted and has a poster | static plus render | [interaction and motion](interaction-and-motion.md) |
| acc-12 | A keyboard shortcut made of one printable character, with no modifier key, can be turned off or remapped, or fires only while its component has focus (SC 2.1.4) | static | [interaction and motion](interaction-and-motion.md) |
| acc-13 | An element that takes keyboard focus is never entirely hidden by author content: a sticky header, a sticky bottom bar, a banner, or a toast (SC 2.4.11). Beyond WCAG: `scroll-padding-top` and `scroll-padding-bottom` match the sticky chrome | static plus render | [layout and composition](layout-and-composition.md) |
| acc-14 | Set line height to 1.5 times the font size, paragraph spacing to 2 times, letter spacing to 0.12 times, and word spacing to 0.16 times. No content or function is lost: nothing clips or overlaps (SC 1.4.12). A label set to `nowrap` fits, or its row reflows | render | [layout and composition](layout-and-composition.md) |
| acc-15 | Content that appears on hover or focus, such as a tooltip or a menu, closes on Escape without a pointer or focus move (SC 1.4.13). It stays open while the pointer moves onto it, and until hover and focus leave or the user dismisses it. Nothing essential depends on hover: every hover affordance also works from keyboard focus (SC 2.1.1). Beyond WCAG, it also works by a tap | render or judgment | [interaction and motion](interaction-and-motion.md) |
| acc-16 | Nothing flashes more than three times in any one-second period (SC 2.3.1). Beyond WCAG, the skill does not use the below-threshold exception of that SC | static plus render | [interaction and motion](interaction-and-motion.md) |
| acc-17 | No time limit set by the content runs out unless the user can turn it off, adjust it, or extend it (SC 2.2.1). The SC exceptions hold: real-time events, essential limits, and limits over 20 hours. A toast whose message or action exists nowhere else on the page stays until the user dismisses it | render or judgment | [interaction and motion](interaction-and-motion.md) |
| acc-18 | Help that repeats across the pages of one site, such as contact details, a contact link, or a help link, sits in the same order relative to the other page content on each page (SC 3.2.6). Checked when one run builds or redesigns two pages or more | judgment | [copy and honesty](copy-and-honesty.md) |
| acc-19 | Information the user already entered in the same process is filled in or offered for selection, not asked for again (SC 3.3.7). The SC exceptions hold: re-entry that is essential, that security requires, or whose earlier value is no longer valid | render or judgment | [interaction and motion](interaction-and-motion.md) |
| acc-20 | A sign-in or sign-up step asks for no cognitive function test, such as recalling, transcribing, or solving, unless an alternative step without one exists or a mechanism helps the user complete it (SC 3.3.8). The SC exceptions hold: a test that asks the user to recognize objects, and one that asks the user to identify non-text content the user supplied to the site. Credential fields carry their `autocomplete` value and never block paste, so password managers work | static plus render | [interaction and motion](interaction-and-motion.md) |
| acc-21 | Repeated blocks can be bypassed (SC 2.4.1). Beyond WCAG: the SC also accepts landmarks or headings, but this row requires a skip link. It is the first focusable element, and it moves focus to the main content | static plus render | [interaction and motion](interaction-and-motion.md) |
| acc-22 | A field that collects information about the user carries the `autocomplete` value that names its purpose (SC 1.3.5) | static | [interaction and motion](interaction-and-motion.md) |
| acc-23 | Prerecorded audio in a video has captions (SC 1.2.2). Prerecorded video with sound that shows information its audio does not carry has audio description (SC 1.2.3, 1.2.5). Prerecorded video with no sound has a text alternative or an audio track, and prerecorded audio alone has a transcript (SC 1.2.1). A loop that carries no information is decoration and is exempt | judgment | [imagery and data](imagery-and-data.md) |
| acc-24 | Each link's text, alone or with its sentence, names its destination (SC 2.4.4). Headings and labels describe their topic or purpose (SC 2.4.6) | judgment | [copy and honesty](copy-and-honesty.md) |
| acc-25 | Focus alone never changes the context (SC 3.2.1). Changing a field's value opens no new page, submits nothing, and moves no focus, unless the field says so in advance (SC 3.2.2) | render or judgment | [interaction and motion](interaction-and-motion.md) |
| acc-26 | A single-pointer action fires on release, or it can be aborted before release or undone after (SC 2.5.2). The SC exception holds: an action whose down event is essential, such as a piano key | static plus render | [interaction and motion](interaction-and-motion.md) |
| acc-27 | The source order matches the reading order the layout shows (SC 1.3.2). No instruction depends on shape, size, place on screen, or sound alone (SC 1.3.3). Content works in portrait and in landscape, unless one orientation is essential (SC 1.3.4) | render or judgment | [layout and composition](layout-and-composition.md) |
| acc-28 | A passage in a language other than the page's own carries its own `lang` attribute (SC 3.1.2). Proper names and technical terms are exempt | static | [copy and honesty](copy-and-honesty.md) |
| acc-29 | Across the pages of one run, shared navigation keeps its order (SC 3.2.3), and a control with the same function keeps the same name and icon (SC 3.2.4). Checked when one run builds or redesigns two pages or more | judgment | [copy and honesty](copy-and-honesty.md) |
| acc-30 | Three kinds of submission need a safeguard: one that makes a legal or financial commitment, one that changes or deletes the user's stored data, and one that submits the user's test responses. Each can be reversed, is checked with a chance to correct it, or asks for confirmation (SC 3.3.4) | render or judgment | [interaction and motion](interaction-and-motion.md) |
| tgt-01 | Pointer targets measure at least 24 x 24 CSS px (SC 2.5.8). An undersized target passes when a circle 24 px in diameter, centered on its bounding box, intersects no other target and no other undersized target's circle. The SC exceptions hold: an equivalent control that passes, a target inside a line of text, a size the browser sets, and a size that is essential | static plus render | [interaction and motion](interaction-and-motion.md) |
| tgt-02 | Every action done with a path-based or multipoint gesture, such as a swipe or a pinch, also works with a single pointer and no path (SC 2.5.1). Hover dependence is `acc-15`, and keyboard reach is `acc-04`, not this row | render or judgment | [interaction and motion](interaction-and-motion.md) |
| tgt-03 | Every action done by dragging also works by single clicks or taps with no drag, such as move buttons or a position menu (SC 2.5.7). Keyboard support alone does not meet it. Dragging that is essential, or that the browser provides, is exempt | render or judgment | [interaction and motion](interaction-and-motion.md) |
| prf-01 | Space is reserved for late content; nothing shifts after load | static plus render | [imagery and data](imagery-and-data.md) |
| prf-02 | Content shows with script off. A reveal starts from a visible state, or hides content only under a class that script adds | static plus render | [interaction and motion](interaction-and-motion.md) |
| lay-01 | No horizontal page scroll at any width of the supported range in the [pre-delivery checklist](pre-delivery-checklist.md), section 1 | render | [layout and composition](layout-and-composition.md) |
| lay-02 | Every state a control needs exists and was seen. These state sets live only here. A control that changes local state alone, such as a toggle, checkbox, switch, or disclosure, has five: default, hover, focus-visible, active, and disabled. A control that sends a request, meaning it submits or fetches, adds loading and error. It adds success only when its action has an outcome the page reports, and that state shows only after a real response (`cpy-08`); a form with no endpoint has no success state. A text input, textarea, select, or combobox has six: default, hover, focus-visible, filled, disabled, and error. It adds loading and success only when it runs a check whose result the page reports. A link has four: default, hover, focus-visible, and active. Each data region has loading, empty, error, and populated | render or judgment | [interaction and motion](interaction-and-motion.md) |
| lay-05 | No text is drawn under an opaque box, an image, or other text. Sticky and fixed chrome is excepted | render | [layout and composition](layout-and-composition.md) |
| lay-08 | The layout holds under the content extremes the detail section sets, at the widths it names: nothing clips, overlaps, or collapses | render or judgment | [layout and composition](layout-and-composition.md), section "Overflow and stacking guards" |
| frm-01 | Every field has a persistent visible label (SC 3.3.2), programmatically associated so the field's accessible name contains the visible text (SC 1.3.1, 4.1.2, 2.5.3). Beyond WCAG: the label is a `<label>` tied to its field by `for` and `id`, or by wrapping the field, and a format hint sits in the persistent helper line, never only in a placeholder | static | [interaction and motion](interaction-and-motion.md) |
| frm-02 | An error is identified in text beside its field (SC 3.3.1) and says how to fix it (SC 3.3.3). Beyond WCAG: typed input survives a failed submit | render | [interaction and motion](interaction-and-motion.md) |
| img-01 | No text rendered inside images (SC 1.4.5). Logotypes are exempt | judgment | [imagery and data](imagery-and-data.md) |
| dat-01 | Bar axes always start at zero. A zoomed axis is allowed on line charts and dot plots only, labeled with its start value. Axes and units are labeled; each series has a cue besides color | render or judgment | [imagery and data](imagery-and-data.md) |
| tok-01 | Every color, font family, padding, margin, gap, and `z-index` value comes from a declared token, and no undeclared token is referenced. The token-derived forms are listed below this table. A literal px length inside one of them does not count as token-derived. A page MAY carry three off-scale optical adjustments. Each one is a literal on a declaration that ends with the marker comment `/* optical: <what it corrects> */`. The static check counts marked literals only: an unmarked off-scale literal fails, and so does a fourth marked one | static | [`DESIGN.md` template](design-md-template.md) |
| cpy-01 | No placeholder text in a delivered page, stand-in person names and stock company names included | static | [copy and honesty](copy-and-honesty.md) |
| cpy-02 | No invented figures, quotes, customers, logos, awards, or brand values. No stranger's photo or generated avatar poses as a customer, colleague, or reviewer | judgment | [copy and honesty](copy-and-honesty.md) |
| cpy-03 | Fonts and images have a recorded license, or are system or project-owned. An empty lookup is reported as defaults used | judgment | [copy and honesty](copy-and-honesty.md) |
| cpy-04 | House rule: no announcer label, meaning a short line by a heading that only names or hypes it. The allowed lines are in the detail file | judgment | [copy and honesty](copy-and-honesty.md), section 7 |
| cpy-05 | House rule: each page stays within five word budgets of the detail section: the headline, the subhead, each section heading, the page total, and the per-band count. All but the band count are counted from the source; the band count is measured in a render. The page total and the band count do not fire on the prose-document, letter, and question-answer shapes ([page shapes](page-shapes.md), section 2), whose running prose sets the length; their other three budgets still bind. The other rows of that section's table grade as open polish, `pol-00.cpy-2` | static plus render | [copy and honesty](copy-and-honesty.md), section 2 |
| cpy-06 | House rule: no template punctuation. The banned patterns and their permitted uses are in the detail section. The static read settles each pattern; a single dot whose use the source does not name is the case left to judgment | static plus judgment | [copy and honesty](copy-and-honesty.md), section 9 |
| cpy-08 | No faked success: no sent, reserved, or thank-you message and no success styling unless a real request succeeded, and no confirmation of something never offered | render or judgment | [copy and honesty](copy-and-honesty.md) |
| cpy-09 | House rule: no word from the banned-buzzword list used as praise. The product's recorded name or term, and a literal sense, do not match | judgment | [copy and honesty](copy-and-honesty.md), section 3 |
| typ-01 | House rule: no tracked small labels, meaning text at 15 px or smaller that is set in capitals or small capitals, or that is tracked above 0.03em. Two exceptions: the wordmark; and, on a page whose display type is set in capitals, controls in capitals tracked at 0.04em or less | static | [typography](typography.md) |
| rds-01 | A redesign keeps all wiring: links, forms, fields, event handlers, routes, test hooks, scripts, data and analytics calls, and every selector or id that code reads | static | [redesign](redesign.md) |
| rds-02 | A redesign keeps facts, headings, figures, images, and ids that no code reads. A loss grades `warn`, never `fail`. Restoring the item closes it, and so does a drop line that records why the page no longer carries it | static | [redesign](redesign.md) |

**Token-derived forms (`tok-01`).** These count as coming from a token:

- a `calc()`, `min()`, `max()`, or `clamp()` built only from tokens, plain numbers, and the units em, ch, lh, and percent;
- a `color-mix()` built only from tokens, `transparent`, and percentages;
- relative color syntax whose origin color is a token, with channel keywords, plain numbers, and percentages;
- the `env()` safe-area insets, such as `env(safe-area-inset-left)`, alone or inside the functions above;
- the keywords `currentColor`, `transparent`, and `auto`, a bare `0`, and the CSS-wide keywords such as `inherit`;
- the descriptors of an `@font-face` rule, such as a fallback face's `local()` source, which declare a face that a token then names.

### Habit

Each habit rule has lettered clauses. A waiver names one clause, for example `lay-03.b`, and MUST meet that clause's guard. A guard of "none" means the clause can never be waived; the page is fixed instead. Several guards read the `declared:` field of the build record or the check-only record ([build record](build-record.md), sections 1 and 2), and `DESIGN.md`'s `Declared` section when one exists. Naming a device in either place never closes a finding by itself: only an accepted waiver line does.

**The material guard.** A catch-all clause `<code>-00` has one guard: the device is named in `declared:` as the direction's material, together with the default it replaces. That guard serves only a visual material choice, and only a sentence in a section the table below lists. Every other catch-all sentence has the guard "none" and is fixed, never waived. That covers every technical, honesty, accessibility, and correctness sentence, every sentence in a baseline-subject section (section "Grade words in topic files"), and `tok-00.1` (section "Scope of taste"). Naming such a device in `declared:` never waives it.

| File | Sections whose catch-all sentences take the material guard |
|------|-------------------------------------------------------------|
| [color and surfaces](color-and-surfaces.md) | 1, except "Pure black and white"; 2; 4, "Glow and wash" only; 5; 7; 8, except "The budget" |
| [typography](typography.md) | 2, except "Sourcing order"; 3; 4; 9, "Monospace has to earn its place" only; 10 |
| [interaction and motion](interaction-and-motion.md) | 13.9 |
| [imagery and data](imagery-and-data.md) | 7, "One photo treatment per theme" and "Frame" only; 11, "Icons" only |
| [layout and composition](layout-and-composition.md) | "Page-wide invariants" |
| [direction and themes](direction-and-themes.md) | 6, "Exhausted looks" only |
| [surface classes](surface-classes.md) | "Genre registers"; "Dials" |

No other section takes it. The files page anatomy, page shapes, hero, copy and honesty, redesign, the `DESIGN.md` template, and the pre-delivery checklist have no section that does. Examples of sentences with the guard "none" outside a baseline-subject section: `transition: all` (`mot-00.13.2`), pixel breakpoints and device sniffing (`lay-00.banned-practices`), a hero sized in plain `vh` (`hro-00.5`), and the body-text floor (`typ-00.8`).

A clause that depends on a number, a limit, or an exemption list cites the section of its detail file that holds it.

| Id | Clauses | Guard (the evidence a waiver needs) | Check | Detail |
|----|---------|-------------------------------------|-------|--------|
| lay-03 | a. Every section centered on one axis. b. Identical card grids for unlike content | a. The page has one message and one action. b. The items match in kind and weight | render or judgment | [layout and composition](layout-and-composition.md) |
| lay-04 | a. A split hero: copy on one side, a picture on the other. The clause fires on every split hero. b. A first screen with no single primary action | a. The picture is the brief's strongest real asset, named in `signature:`. b. The page's job is reading, not acting | judgment | [hero](hero.md) |
| lay-06 | a. Two filled buttons side by side, or more than one filled primary action per page or per dialog. Repeats count as the detail file's section 4, "Hierarchy", says. b. More than one primary-button recipe on a page | a. None. b. None | static plus render | [interaction and motion](interaction-and-motion.md) |
| lay-07 | a. Below the hero, a section body narrower than the width floor in "Width and mass", where it is not a single statement. The exempt shapes and bodies are that section's. b. The median section heading below the hero renders under the floor in "The heading group". The exempt shapes are that section's | a. None. b. None | render | [layout and composition](layout-and-composition.md) |
| hro-01 | a. A fold-fit element sits below the fold at the size section 3 names. Clause a covers every posture, `custom` included. b. The lowest hero element ends farther above the fold than "Fold proximity" in section 4 allows, on the postures it names. c. The empty band below the lowest hero element exceeds "Dead band" in section 4, on the postures it names | a. None. b. None. c. None | render | [hero](hero.md) |
| typ-02 | a. Gradient-filled text. b. More type families than section 1 of the detail file lets a page carry without a finding. A page past that section's running-family limit grades once, under `typ-00.1`, and not under this clause | a. One hue (stops within 40 degrees), built from tokens, passing `acc-01`. b. Each family beyond the running limit is a single-job outlier named in `declared:`, and the total stays within the waivable ceiling in section 1 | static | [typography](typography.md) |
| typ-03 | a. A lone italic word inside an upright heading. b. One word or phrase in a heading picked out by color, weight, highlight, or underline | a. None. b. In the hero only, once, with the device and the word named in `declared:` | static plus render | [typography](typography.md) |
| col-01 | a. Accent area at the fold past the aim in section 2, "Accent footprint". The clause grades `habit-open` in two bands: the middle band, from the aim up to the limit, and the upper band, past the limit. That section sets the aim, the limit, the fold size, and the areas that do not count. b. A gradient background with no source in the tokens | a. Middle band: the accent area past the aim marks a signal use that section 2 lists, or `declared:` names the accent's job and its area allowance. Upper band: the area past the limit marks a signal use that section 2 lists. b. The gradient is named as material in `declared:` | static plus render | [color and surfaces](color-and-surfaces.md) |
| col-02 | a. One container recipe boxes content where the containment ladder calls for a varied step. A recipe is one radius, shadow, and border together. The static measure, and what never fires it alone, are in section 7. b. Frosted or translucent panels over a plain background | a. The direction sets one surface treatment, named in `declared:`. b. Something sits behind the panel to show through | static | [color and surfaces](color-and-surfaces.md) |
| col-03 | a. A purple-to-blue or purple-to-pink gradient, or cyan on a dark ground. b. A color token at 0 or 100 percent lightness, outside the exemption in section 1 | a. The hues come from a captured or supplied brand spec. b. The value is named in `declared:` and passes `acc-01` | static | [color and surfaces](color-and-surfaces.md) |
| mot-01 | a. More than one entrance choreography on a page, or an entrance on every section. The clause counts choreographies; the hero entrance's duration is `hro-00.8`. b. Hover lift on cards that do nothing. c. More than one scroll-driven pattern on a page | a. The user set the motion dial to `expressive`, recorded in `motion:`. A genre default does not meet it. b. None: a lift promises a click. c. None | static | [interaction and motion](interaction-and-motion.md) |
| img-02 | a. Emoji used as icons, or icons from more than one family on a page, outside the brand-mark allowance in section 11. b. Abstract filler art where a product view belongs. c. An icon in a colored disc or tile, or one icon over each heading in a row of equal columns | a. For emoji only: the voice named in `declared:` allows emoji. Mixed families have no guard. b. No product view exists yet, and the build record says so. c. None | static plus render | [imagery and data](imagery-and-data.md) |
| img-03 | a. Photos under the hero cover more than the share limit in section 5, "Page share", when that section's picture-count condition holds. b. Two photo-led sections next to each other | a. None. b. None | render | [imagery and data](imagery-and-data.md) |
| img-04 | a. More empty picture positions on a page than section 8 allows. b. An empty picture position missing from the material request | a. None. b. None | static plus render | [imagery and data](imagery-and-data.md) |
| cpy-07 | a. Stock cadences, openers, and stock button labels from the lists in section 3. b. One fact stated in more sections than section 6 allows | a. The phrase is the product's recorded name or term. b. The page has eight sections or more, counting hero and footer, and the repeat sits in a section that ends in the page's primary action | static plus render | [copy and honesty](copy-and-honesty.md) |
| rot-01 | a. The `shape:` slug equals that of one of the latest three logged builds. b. The `fingerprint:` shares more than 3 of its 6 axis values with any of the latest three logged builds. A value written `none (forced)` never counts as shared. The pages of one multi-page redesign are not compared with each other under b | a and b. The user asked for that shape, or that page, by name | static | [build record](build-record.md) |
| tgt-04 | House target, stricter than WCAG 2.5.8. a. A pointer target whose hit area measures under 44 x 44 CSS px. The hit area is the element's box, plus a `::after` extension on the element or on an element that wraps it, plus the associated `<label>` of a native form control; spacing does not count. Parts that do not touch are measured one at a time, so a label set apart from its field by a gap counts only when it alone reaches the size. A text input, textarea, or select renders no `::after`, so it reaches the size through its label or a wrapping element. A range input counts its own box alone, since a label click sets no value. b. Under `(pointer: coarse)`, a hit area under 48 x 48. Scope: stand-alone targets on every scope, marketing pages included. These are buttons, icon buttons, nav, menu, and footer links, tabs, and form controls with their labels. Exempt, as in `tgt-01`: a target inside a line or block of running text, and an unstyled target whose size the browser sets. Also exempt: a target with an equivalent control on the same page that meets this row. `tgt-01` still applies to every exempt target. A control MAY stand shorter than its hit area, at the heights section 4 of the detail file allows | a and b. On a `scope: app` screen, the control repeats in a dense row or toolbar where hit areas of that size would overlap. It meets `tgt-01`, and `declared:` names the region | static plus render | [interaction and motion](interaction-and-motion.md) |
| `<code>-00` | `<section>`. Any rule in that topic file worded MUST, MUST NOT, "flag", "flags", "flagged", "banned", "refused", or "is a finding" that cites no id of its own | The material guard, for a sentence in a section the material-guard table lists. Guard "none" for every other sentence (see above) | as the rule needs | The file for `<code>` |

In the Clauses column, a bare section number points into that row's Detail file.

### Polish

| Id | Rule | Check | Detail |
|----|------|-------|--------|
| pol-00 | Open guidance. Clause `<code>-<section>`: any SHOULD, "never", "always", or plain instruction in a topic file that cites no id; for the checklist this is `chk-<section>`. Clause `chk-list-<n>`: item n of the checklist's polish list | as the item needs | The file for `<code>`; the [pre-delivery checklist](pre-delivery-checklist.md) |
| pol-01 | Spacing follows the ladder tiers, and a heading sits closer to what it introduces than to what precedes it | static plus render | [layout and composition](layout-and-composition.md) |
| pol-02 | Running text keeps the measure the detail file sets, in section 8 | render | [typography](typography.md) |
| pol-03 | No single-word last line in a heading | render | [typography](typography.md) |
| pol-04 | Numbers that align in columns, and display numbers, use tabular figures | static | [typography](typography.md) |
| pol-05 | Icons within the page's one family share one stroke weight and one style. Mixing families is `img-02.a`, not this rule | judgment | [imagery and data](imagery-and-data.md) |
| pol-06 | Icons, quotes, and large type align optically at edges | judgment | [layout and composition](layout-and-composition.md) |

### Bookkeeping

Each row compares fields of this build's log entry with the same fields of the latest three earlier entries in the [build log](build-record.md). A match is a `note`. An entry that lacks the field, such as one written before the field existed, never matches.

| Id | Note | Fields compared | Check |
|----|------|-----------------|-------|
| rep-01 | The palette matches: paper lightness within 3 points, and the accents either both neutral (chroma under 0.05) or within 15 degrees of hue | `palette:` | static |
| rep-02 | The type pairing matches: the display family and the body family both share their family-name prefix with one logged build | `faces:` | static |
| rep-03 | The hero posture, nav, footer, and opening section all equal one logged build's values | `hero:`, `nav:`, `footer:`, `opening:` | static |

Every rotation and repetition check reads only stored fields. `rot-01.a` compares `shape:`. `rot-01.b` compares `fingerprint:` axis by axis. The display-face rule of [direction and themes](direction-and-themes.md), section 6 (`dir-00.6`), compares `faces:`. The accent-hue check in that section compares `palette:`. Candidate directions compare the axes code in `direction:`. Opener types compare `openers:`, and photo ids compare `photos:`.

## Exception lines

Waivers, dismissals, confirmations, acknowledgments, and drops are single comment lines. They sit at the position the [build record](build-record.md), section 1, gives them. A line outside that position is not read, and the finding it names stays open. When the lines do not fit, fix findings instead of adding lines. Write one line per clause or finding, in exactly this form:

```css
/* waive <id>.<clause> | guard: <evidence the guard is met> | reason: <why, for this page> */
/* ack <finding-id> | reason: <why the polish item stays as it is> */
/* dismiss <finding-id> | reason: <why the suspected breach is not there> */
/* confirm <finding-id> | user: "<the user's words in chat>" | reason: <what the user confirmed> */
/* drop rds-02@<where> | reason: <why this page no longer carries the item> */
```

A finding id is `<id>[.<clause>]@<where>`. The `where` part is a selector, a section name, or `file:line`. Examples: `pol-03@#menu h2`, `col-01.a@hero`, `lay-00.section-gaps@#visit`.

The check pass computes each waiver's guard again on its own; the written evidence does not stand in for that. A waiver is rejected when:

- it targets a baseline rule;
- it names a whole rule instead of one clause;
- it repeats another waiver for the same clause. For a catch-all clause, two waivers count as the same only when they quote the same flagged sentence, and the guard field MUST quote it;
- its reason is boilerplate, such as "intentional", "design choice", or "matches the brand";
- its reason is under 24 characters;
- its reason is copied from another waiver, in this build or an earlier one;
- its reason shares no word, beyond common short words, with the page's own text or brief;
- the recomputed guard is not met.

A dismissal, a confirmation, an acknowledgment, or a drop is rejected on the duplicate, boilerplate, length, and copied-reason grounds. A dismissal MAY close a `warn` on a baseline rule. It states that the breach is not there; it does not set the rule aside.

A confirmation closes a `warn` whose check is `judgment`, and nothing else. It records that the user, asked in chat, confirmed the item stays. It is also rejected when the finding is not a `judgment` `warn`, when the `user:` field does not quote the user's own words, or when the run is headless. A headless run leaves such a `warn` open and names it in the report.

A drop serves `rds-02` alone, and only in a redesign. A repair counts as one: there `rds-01` and `rds-02` compare against the page as found ([redesign](redesign.md), section 8). It records a real loss that the redesign made on purpose, such as a heading the new structure no longer needs. The loss grades `dropped`. A drop line naming any other id is rejected.

The check pass removes every rejected line from the stylesheet before a review runs, and the report names each removed line with its ground. Its finding stays open. Every line still in position when a review runs has therefore passed these grounds, and the reviewer treats each well-formed line there as accepted ([review protocols](review-protocols.md), section 1).

Before mode removes nothing, because it edits no file. It reports each rejected line with its ground and leaves it in place, and the finding that line names stays open. No review runs in before mode, so no reviewer reads such a line.

### House style

When a build has more than three accepted waivers, or the same clause is waived in three logged page builds in a row, the exception has become a house style. The report MUST say so and propose the `DESIGN.md` entry that makes it the project default. The run-of-three count reads the `waivers:` field of the build log, so it counts logged page builds only. A component or app build is not logged, so only the more-than-three count applies to it, read from its own record.

After the user approves the entry, the skill adds it to the matching section of `DESIGN.md` and changes nothing else. When no `DESIGN.md` exists, the proposal says that approving it creates the file. A component build never creates one: its proposal goes into the closing report alone ([template](design-md-template.md), section 1). The approval then counts as the user's request to write `DESIGN.md` ([template](design-md-template.md), section 1), and the skill writes it from the token sheet with that one entry. From then on, the clause no longer fires for the project.

## Flags and downgrades

The `scope:`, `copy:`, `depth:`, `mode:`, and `direction:` fields of the build record, and the same fields of the check-only record, change grading as listed here. The arguments `--scope`, `--verbatim`, `--redesign`, `--fast`, and `--custom` set those fields (`SKILL.md`, "Workflow"). The hero stage limits which checks run. The report names every downgrade it applied. These lists are complete, and this section is their only home; any other file cites it. When a run carries several flags, such as `--custom` and `--fast`, every list that matches applies. No downgrade lowers a sentence in a baseline or baseline-subject section (section "Grade words in topic files").

Five routes change how a baseline rule grades. Verbatim copy touches `cpy-05`, `cpy-06`, and `cpy-09`. A redesign at any depth, a repair, an audit, and before mode touch `cpy-05`. Component scope touches `cpy-05` and narrows `acc-07` to heading order. App scope touches `cpy-05`. The hero stage holds the page total of `cpy-05` for the full page. No other route weakens a baseline rule. A shape exemption inside a row, such as the prose shapes of `cpy-05`, is not a route: the clause does not fire there (section "Grades").

Apart from those five routes, a host with no browser grades render checks `not checked`, as section "Hosts with no browser" states. A missing computation grades `not checked` the same way, as section "Checks that need a computation" states. Neither changes the band of any rule.

- **Verbatim copy** (`copy: verbatim`). The user's exact words are source material, not model output. `cpy-05`, `cpy-06`, `cpy-07`, and `cpy-09` grade as `note`. `cpy-01` to `cpy-04` and `cpy-08` keep their band.
- **Redesign, any depth** (`depth: full`, `restyle`, or `polish` in the build record; `depth: repair` or `depth: audit` in the check-only record; and before mode). `cpy-05` grades as `note`, because the page's existing copy sets the length. A repair does not cut copy to the budget; it reports a long page as a structural finding ([redesign](redesign.md), section 8). This is the one statement of that route.
- **Redesign that keeps the layout** (`depth: restyle` or `depth: polish`). These grade as `note`: `lay-03`, `lay-04`, `lay-07`, `hro-01`, `rot-01`, `pol-01`, `pol-06`, and the catch-alls `lay-00` (not `lay-00.overflow-and-stacking-guards`), `pag-00`, and `shp-00`. At `depth: polish`, the scale section of the typography file (`typ-00.6`) also grades as `note`. Baseline layout rules (`lay-01`, `lay-02`, `lay-05`, `lay-08`) keep their band. The page already exists and its layout stays, so the run skips both the hero stage and its review. The pass edits the whole page, runs the sweep, and runs the finish review alone; the record writes `hero not run (depth)`.
- **Page-only layout sections.** These headings of [layout and composition](layout-and-composition.md) govern a page's sections. They have nothing to check on an app screen or in one component.
  - Canvas and spacing: "Two layers per section", "Section gaps", "Space is earned by mass", and "Density budget".
  - Section rules: "Content first", "Skeletons", "The heading group", "Width and mass", "Balance and height", "Containment ladder", and "Stat rows".
  - Compositions: "Compositions" and "Stacking order per composition".

  At app and component scope, every uncited clause in them grades `not checked`, reason "scope": the catch-all `lay-00.<heading>` and the polish clause `pol-00.lay-<heading>`. A sentence there that cites its own id grades under that id's row and the lists below.
- **Component scope** (`scope: component`). Rules with nothing to check in one component grade `not checked`. The reason is "scope". They are `cpy-05`, `lay-03`, `lay-04`, `lay-07`, `hro-01`, `img-03`, `img-04`, `rot-01`, `rep-01` to `rep-03`, and the fold measure `col-01.a`. The catch-alls are `hro-00`, `pag-00`, `shp-00`, the stock-chrome clauses `cpy-00.10` and `cpy-00.11`, the page-only layout sections above, and three more layout headings: `lay-00.one-container`, `lay-00.twelve-columns`, and `lay-00.page-wide-invariants`, with their `pol-00.lay-<heading>` clauses. Of `acc-07`, only heading order inside the component is checked. `cpy-04` still applies. A component has no hero stage and no hero review; it runs the finish review alone.
- **App scope** (`scope: app`). Page rules grade `not checked`, reason "scope": `lay-04`, `lay-07`, `hro-01`, `rot-01`, `rep-01` to `rep-03`, `cpy-05`, `img-03`, and `mot-01.a`. The catch-alls are `hro-00`, `pag-00`, `shp-00`, `cpy-00.10`, `cpy-00.11`, and the page-only layout sections above. Every other layout heading grades as usual. Of "The canvas", that means "One container" and "Twelve columns"; "Page-wide invariants" also grades as usual. `cpy-04` still applies. An app screen has no hero stage and no hero review; it runs the finish review alone.
- **Custom direction** (`direction:` source `custom`). The run switches off page shapes, the composition guide, and the genre defaults ([direction and themes](direction-and-themes.md), section 6). These grade `not checked`, reason "custom": `shp-00`, `lay-00.compositions`, `lay-00.stacking-order-per-composition`, `scl-00.genre-routing`, `scl-00.genre-registers`, and `scl-00.dials` from [surface classes](surface-classes.md). Every baseline rule, every lettered habit clause, and every other catch-all clause keep their band. `col-01.a` reads its aim and limit from the genre row that matches the record's `genre:` field, which a custom run still writes. A custom direction keeps the reference type scale, the space scale, and the width tokens, so `typ-00.6` keeps its band.
- **Before mode** (a redesign or an audit, on the page as found; [pre-delivery checklist](pre-delivery-checklist.md), section 1, "Before mode", defines it). The page grades at its inferred scope and genre ([redesign](redesign.md), section 8), with that scope's downgrades. No direction or build was chosen for the page as found, so these grade `not checked`, reason "before mode": `rot-01`, `rep-01` to `rep-03`, and the catch-all `dir-00`. `cpy-05` grades `note` under "Redesign, any depth". Every other rule grades as usual.
- **Hero stage** ([hero](hero.md), section 9). It runs only at page scope, in a new build or a redesign at `depth: full`. Only checks that the first screen can settle run. Whole-page rules wait for the full page: the page total of `cpy-05`, `lay-03`, `lay-07`, `img-03`, `img-04`, `rot-01`, and the polish and bookkeeping bands.
- **Fast mode** (`mode: fast`). Fast mode skips polish and bookkeeping, which grade `not checked` with the reason "fast mode". For the baseline and habit bands, static, render and judgment checks all run. Fast mode changes no other grade and no part of the shipping rule.

No other input changes a grade. A genre tie on a page this skill did not build resolves to product-minimal, and every habit rule grades against that genre as usual.

## Scope of taste

The skill decides how an interface looks and reads. It does not:

- write copy from nothing; it edits and arranges the user's material and marks gaps with `TODO(clarify)`;
- choose a brand identity, a name, or a logo;
- push a style the user never chose. The skill proposes a direction in the decision summary, and the user confirms it before the build. A headless or fast run states the direction, proceeds, and says so;
- build application logic. When asked to wire up behavior, it does so, and applies these rules to the surface that renders it.

Its output follows one contract. Tokens are defined in one place and named by role. The framework's own conventions are kept. The build record sits where the [build record](build-record.md), section 1, places it, and no further comments are needed. An edit that does not invoke the skill stays inside the project's own system.

**Local overrides of `DESIGN.md`.** A page or section that needs a value other than the one `DESIGN.md` sets gets a `Variants` entry. The skill proposes the entry, and adds it to `DESIGN.md` only after the user approves it. The code then reads the variant's token. A page-local override of a `DESIGN.md` value MUST NOT be written; it grades `tok-00.1`, with the guard "none", because tokens are a baseline subject. A `Variants` entry exists only beside a `DESIGN.md`. With none, there is nothing to vary: the build changes the value in its own token sheet. The rule `rules/code-craft-ui.md`, section 4, sets a different rule for edits made outside the skill: there, a local override is allowed when a comment names the value it replaces and the reason. That rule never applies inside a skill run.
