<!-- SPDX-License-Identifier: MIT -->

# Pre-Delivery Checklist

Reference for the [`ui-design`](../SKILL.md) skill. `SKILL.md`, section "Reference loading", sets when it loads: before the hero stage, which uses its budget and its review inputs, or at Step 0 of a redesign or an audit, for the sweep in before mode (section 1). It holds the sweep, the verification budget, the inputs for the two fresh-context reviews and what to do with their verdicts, the manual passes, and the polish list. Rule ids, bands, grades, and check classes live in the [rule catalog](rule-catalog.md). This file says how each check is made and how results are reported. It does not repeat the thresholds held in the topic files.

This file is the home for the capture sizes, the width sweep and the supported width range, the measurement procedures, the verification budget, the review inputs, and the polish list. Other files cite these sections.

## 1. The sweep

The sweep runs every rule in the catalog once, grouped by check class. Prefer measurement over judgment. A value is reported only when a read, a measurement, or a tool produced it.

### Before mode

Before mode is the sweep run once on a page as found, before any edit, by a redesign or an audit ([redesign](redesign.md), section 3). It needs the files `SKILL.md`, section "Reference loading", lists for Step 0 of a redesign or audit, all loaded at Step 0. In before mode:

- It runs the static and render checks. Every rule grades as usual at the inferred scope and genre, except the rules the catalog's "Before mode" downgrade names ([rule catalog](rule-catalog.md), section "Flags and downgrades").
- It fixes nothing, removes no exception line, runs no review, and spends nothing from the budget in section 2.
- A missing build record does not stop it; the page grades as a page this skill did not build.
- Its findings, captures, and inventory go into the before-record.

### Static checks

Run these first. They need no browser.

- Read the authored stylesheets, the markup, the copy, and the utility-class strings inside component files.
- When a framework strips comments from its output, read the authored source, not the built file ([build record](build-record.md)).
- Settle every `static` rule, and the static half of every `static plus render` rule.
- Confirm the record sits where the [build record](build-record.md), section 1, places it: the build record, or on a repair of an outside page the check-only record of that file's section 2. Without it, the sweep stops until the record is written. Before mode is the one exception. A record that reads `grades: pending` is complete for this check; section 8 writes the counts.
- Check every exception line against the grounds in the [rule catalog](rule-catalog.md), section "Exception lines", and recompute each waiver's guard. Remove each rejected line and report it with its ground; its finding stays open. In before mode, report each rejected line with its ground and leave it in place, since before mode edits no file.
- Compute each contrast pair from the token values, in every shipped mode. The arithmetic needs a tool: a host shell, run through the host's own approval (`SKILL.md`, section "Agent operations"), or a general-purpose subagent the host offers that has a shell, asked only for the ratios, never `design-critic`. Such a subagent call is not a review and spends no round. With neither, the static half of `acc-01` grades `not checked` with the reason "no tool", and the report gives no ratio ([rule catalog](rule-catalog.md), section "Checks that need a computation").

### Render checks

Use the host's browser tool. A framework project needs a running server. Start one only with the approval Step 0 of `SKILL.md` obtains under the run gate in that file's section "Agent operations". Never install dependencies. Without that approval, ask the user for the running URL. When none comes, grade the render checks `not checked` with the reason "no app". With no browser tool, the reason is "no browser". When the browser cannot apply an emulation a row below needs, that row grades `not checked` with the reason "no tool" ([rule catalog](rule-catalog.md), section "Grades").

Save every capture as a PNG file in the page's capture folder, which `SKILL.md`, section "Output Surface", names. Name each file by view and size, such as `first-1440x900.png` or `sweep-961.png`, for the first shipped mode. A second mode adds its name before the extension, such as `first-1440x900-dark.png`. A recapture overwrites the earlier file of the same name. When the host cannot save a capture as a file, the reviews take the source route in section 3.

Take these captures, in every shipped mode:

| View | Sizes |
|------|-------|
| First screen | 1280x800, 1440x900, 1920x1080, and 375x812 |
| Full page | 1440 wide and 375 wide |
| Width sweep | 320, 375, 639, 641, 959, 961, 1280, 1440, 1920 |
| Zoom | First screen at 1280x800 with the browser at the zoom level `acc-09` names, named `zoom-1280x800.png` |

The supported width range runs from 320 to 1920 px, the ends of the width sweep. The sweep covers the narrowest supported width, a phone, and one pixel on each side of the 40rem and 60rem breakpoints at the default root size. It ends with three desktop widths. A second mode, such as dark, repeats the captures with `data-mode="dark"` set on the root, or with the color-scheme preference emulated.

Each measurement below comes from a tool, and the report names the tool per row. One route is the host's browser tool reading page geometry on the live page: element boxes, computed styles, and scroll sizes, at the viewport size and mode of the capture the row names. The other is an image tool the host offers that measures pixel positions and areas on the saved PNG. An estimate by eye from a capture is not a measurement. With neither route, the row grades `not checked` with the reason "no tool" ([rule catalog](rule-catalog.md), section "Checks that need a computation"). The capture stays the reviewer's evidence either way. Each row runs once per shipped mode, on that mode's captures.

Each threshold lives in the section the last column names; this table says only how to measure.

| Check | Rule | How to measure | Threshold home |
|-------|------|----------------|----------------|
| Fold fit | `hro-01.a`, `hro-01.b` | On `first-1280x800.png`, find the headline, supporting line, primary action, and the visual's focal point. Measure the gap from the lowest hero element to the fold | [hero](hero.md), sections 3 and 4 |
| Dead band | `hro-01.c` | On `first-1440x900.png`, measure the empty space below the lowest hero element, to the fold or to the hero's bottom edge, whichever comes first | [hero](hero.md), section 4 |
| Accent share | `col-01.a` | On `first-1280x800.png`, add the accent areas the threshold home counts, then divide by the viewport area | [color and surfaces](color-and-surfaces.md), section 2 |
| Contrast | `acc-01` | Sample each rendered text and non-text pair on its computed ground, with any texture or overlay in place, in every shipped mode | [rule catalog](rule-catalog.md), `acc-01` |
| Overlap | `lay-05` | At each sweep width, look for a line of text drawn under another element (section 7) | [rule catalog](rule-catalog.md), `lay-05` |
| Words per band | `cpy-05` | On the 1440-wide full-page capture, cut consecutive bands from the top, each of the height the threshold home sets, and count the visible words in each band. Skip text the threshold home marks as not counted | [copy and honesty](copy-and-honesty.md), section 2 |
| Section width | `lay-07.a` | On the 1440-wide capture, measure the widest row of each section body below the hero in grid columns | [layout and composition](layout-and-composition.md), "Width and mass" |
| Heading size | `lay-07.b` | On the 1440-wide capture, take the rendered size of each section heading below the hero, then the median | [layout and composition](layout-and-composition.md), "The heading group" |
| Photo share | `img-03.a` | On the 1440-wide capture, add the area of the photos under the hero, product images left out, then divide by the area under the hero | [imagery and data](imagery-and-data.md), section 5 |
| Photo neighbors | `img-03.b` | On the full-page capture, mark each photo-led section and check that no two touch | [imagery and data](imagery-and-data.md), section 5 |
| Horizontal scroll | `lay-01` | At every sweep width, compare the document's scroll width with the viewport width | [rule catalog](rule-catalog.md), `lay-01` |
| Content extremes | `lay-08` | Fill each field with the values the threshold home lists, at the widths it names | [layout and composition](layout-and-composition.md), "Overflow and stacking guards" |
| Text spacing | `acc-14` | At 375 and 1440 wide, apply the spacing overrides of `acc-14` with a user style sheet, then look for clipped or overlapping text and `nowrap` labels | [rule catalog](rule-catalog.md), `acc-14` |
| Keyboard pass | `acc-04`, `acc-21` | At 375 and 1440 wide, tab through every control from the top. Record the order, any trap, the skip link, and where focus lands when each dialog closes | [rule catalog](rule-catalog.md), `acc-04`, `acc-21` |
| Focus visible | `acc-03` | During the keyboard pass, capture the ring on each control type and sample it against every color it touches | [rule catalog](rule-catalog.md), `acc-03` |
| Focus not obscured | `acc-13` | During the keyboard pass, check that no focused element is entirely hidden by sticky or fixed chrome, a banner, or a toast | [rule catalog](rule-catalog.md), `acc-13` |
| Forced colors | `acc-03` | At 1440 wide with `forced-colors: active` emulated, tab through the page. Every focus change shows, and no field or control shows a ring at rest | [rule catalog](rule-catalog.md), `acc-03` |
| Targets | `tgt-01`, `tgt-04` | Measure each target's box and its `::after` extension or label, then run the spacing test for any target under the `tgt-01` size. Repeat under emulated `(pointer: coarse)` | [rule catalog](rule-catalog.md), `tgt-01` and `tgt-04` |
| Zoom | `acc-09` | On the zoom capture, scroll the page. Text grows, nothing clips or overlaps, and the page scrolls in one direction only | [rule catalog](rule-catalog.md), `acc-09` |
| Failed submit | `frm-02` | Type into every field, submit with at least one invalid value, then check the error text beside each field, the kept input, and where focus moves | [rule catalog](rule-catalog.md), `frm-02` |
| Layout shift | `prf-01`, `img-00.12` | Reload the page with the network throttled, then compare the first frame with the settled page. Nothing above the fold moves. At each sweep width, name the largest paint and whether it loads lazily | [rule catalog](rule-catalog.md), `prf-01`; [imagery and data](imagery-and-data.md), section 12 |
| Reduced motion | `acc-08` | Capture the first screen and one reveal with `prefers-reduced-motion: reduce` emulated. No travel, parallax, or zoom remains | [interaction and motion](interaction-and-motion.md), section 13.7 |
| Color alone | `acc-02` | Capture the full page in grayscale. Every status, series, and selected state still reads | [rule catalog](rule-catalog.md), `acc-02` |
| Flashing | `acc-16` | Watch every animation, blink, and video segment, and read their cycle lengths in the source. No cycle alternates light and dark faster than `acc-16` allows | [rule catalog](rule-catalog.md), `acc-16` |
| Auto motion | `acc-11` | List every element that moves or updates on its own: loops, autoplaying video, carousels, tickers, and feeds. Read each one's total run time in the source. For each one past the `acc-11` limit, use its pause control, then hover it and focus it, then repeat with `prefers-reduced-motion: reduce` emulated. Check muting and the poster on autoplaying video | [rule catalog](rule-catalog.md), `acc-11` |
| Hover and focus content | `acc-15` | Open each tooltip, menu, or popover by hover and again by keyboard focus. Press Escape, and move the pointer onto it | [rule catalog](rule-catalog.md), `acc-15` |

At each sweep width, also look for controls that wrap, image tracks and display headings that overflow, radio-based tabs that jump, and sticky elements that stack on each other. Each finding cites the rule its topic file gives it. The page MUST work across the supported range (`lay-01`). It MUST NOT depend on hover alone (`acc-15`), or on a path-based or multipoint gesture alone (`tgt-02`).

Then look by eye for what the measurements miss:

- Desktop sidebars and filters fold into a menu or a disclosure on narrow screens.
- Section headings stack into one column on a phone.
- Every override that a direction adds has a matching narrow-screen rule.

### With no browser tool

Follow the [rule catalog](rule-catalog.md), section "Hosts with no browser". Do not drive a desktop browser by hand to stand in for the render pass.

## 2. Verification budget

This budget is the only one. [Hero](hero.md), section 9, cites it and does not restate it.

1. One inspection per stage: the static checks, then the render checks. A page has two stages, the hero stage ([hero](hero.md), section 9) and the full page. Component scope, app scope, a restyle or polish redesign, and a repair of an outside page have the full page alone.
2. One fix batch per stage for everything its inspection found.
3. One confirmation pass per stage that reruns only the checks its fixes touched.
4. Each review, hero and finish, adds one review round. A verdict with findings also adds one fix batch and one fresh set of captures. A `ship` verdict with no findings closes that review with no fix batch and no recapture.
5. A review gets a second round only when its verdict was `rebuild` or a finding cited a baseline id. A `recapture` verdict retakes the captures and does not count as a round. A second `recapture` verdict on the same review counts as its round.
6. Nothing runs past this budget without telling the user why and what remains open.

## 3. Fresh-context reviews

The thread that built a page is its weakest critic. Two reviews therefore run in a context that carries none of the build conversation:

- **Hero review.** After the nav and hero are built and pass their checks, before anything below the fold is written ([hero](hero.md), section 9). It runs only where the catalog's hero stage runs ([rule catalog](rule-catalog.md), section "Flags and downgrades").
- **Finish review.** After the full page has had its sweep and its fix batch.

Component and app scope have no hero stage. They run the finish review alone and write `hero not run (scope)` in the record's `review:` field. A redesign at `depth: restyle` or `depth: polish` also has no hero stage and writes `hero not run (depth)`, and a repair of an outside page runs only its one finish review. The budget in section 2 then counts one review.

Each review runs through the [`design-critic`](../../../agents/design-critic.md) subagent in review mode, in the foreground, because the build waits on the verdict. The reviewer follows [review protocols](review-protocols.md). The builder MUST NOT load that file: it passes only the inputs below, so it cannot write toward the questions. The input lists below are the only home of each review's inputs.

Every review's inputs open with a mode line: `review: hero`, `review: finish`, or `review: finish (outside page)`. Two absolute paths follow it: the installed `review-protocols.md` and the installed `rule-catalog.md`. Build both from the base directory the host reports when it loads the skill, never from the project's working directory. The builder passes the protocol's path without reading the file.

When the host reports no base directory, ask the user once for the skill's installed folder, and keep the answer in the pre-flight cache. Until a folder is known, run each review by the same-thread route below and record `via: same-thread`.

Captures reach the reviewer as the absolute paths of the PNG files saved in section 1. A subagent cannot see images that stay in the builder's context. When the host cannot save captures, pass the source instead and record `input: source-only` for that review.

When the host has no subagents, or no `design-critic` agent, or no folder is known, the building thread loads the review protocols only at the review point, after its fix batch. It looks at the captures afresh, answers the questions, and records `via: same-thread` for that review in the record's `review:` field.

### Hero review inputs

- The mode line `review: hero`.
- The absolute paths of `review-protocols.md` and `rule-catalog.md`.
- The absolute paths of the first-screen captures from section 1, when they exist.
- The hero source, in every case.
- The build record as it stands.
- The build log entries that `rot-01` compares ([rule catalog](rule-catalog.md), section "Habit"), copied as written from `design-log.md`, or `log: none` when the log has none. The reviewer compares the screen with their fingerprint and chrome fields.
- The Direction, Material, and Signature rows of the decision summary. On a custom run, the idea sentence and the `look` row take the place of the Direction row.
- `DESIGN.md`, when one exists.
- For a redesign: the plan's Kept row ([redesign](redesign.md), section 4).

### Finish review inputs

- The mode line `review: finish`.
- The absolute paths of `review-protocols.md` and `rule-catalog.md`.
- The absolute paths of the first-screen, full-page, and zoom captures from section 1, never the sweep captures. With no captures, none.
- The page source.
- The build record, with the hero review findings and their statuses, or `hero not run (scope)` or `hero not run (depth)`.
- At page scope, the same build log entries as the hero review inputs. Component and app scope are not logged and pass none.
- The Direction rows of the decision summary, or on a custom run the idea sentence and the `look` row.
- `DESIGN.md`, when one exists.
- For a redesign: the absolute path of the before-record, the absolute paths of its captures when they exist, and the plan's Kept row ([redesign](redesign.md), section 4).

### Inputs for a page this skill did not build

A repair of an outside page ([redesign](redesign.md), section 8) runs one finish review in its variant for such pages ([review protocols](review-protocols.md), section 5). It counts as the finish review in the budget in section 2.

- The mode line `review: finish (outside page)`.
- The absolute paths of `review-protocols.md` and `rule-catalog.md`.
- The absolute paths of the captures from section 1, when captures exist.
- The page source, in every case.
- The check-only record as it stands, written before the sweep ([build record](build-record.md), section 2), and the inferred genre.
- `DESIGN.md`, when one exists.

### Acting on a verdict

The reviewer's reply opens with one verdict word, and each finding after it cites a rule id or the word `taste`. The verdict words are defined in the [review protocols](review-protocols.md), section 2; the builder acts on the word alone. A `(source-only)` after the word sets that review's `input:` to `source-only`. Act within the budget in section 2:

- On `recapture`, retake the captures and run the review again.
- On `ship` with no findings, close the review. Run no fix batch and retake no captures.
- On `rebuild`, `fix`, or `ship` with findings, fix the findings that are real in one batch. Retake the same captures, and give every finding a status with a reason: `resolved`, `partial`, or `unresolved`.
- A finish reply, in either variant, MAY end with one `keep` line ([review protocols](review-protocols.md), section 2). Check every fix in the batch against it. A fix that weakens what the line names is reworked or reverted, and the report says which.
- Send the new captures back for a second round only when the verdict was `rebuild` or a finding cited a baseline id. A `taste` finding never earns a second round and never blocks.

Write the outcomes into the record's `review:` field, hero review first, each verdict followed by its own `via:` and `input:` ([build record](build-record.md), section 1). A review read from source alone records `input: source-only`. A review still pending is left out of the field. A review skipped for good is written `not run (<reason>)` and reported the same way. Never record a pass that did not happen.

A reply whose first line is `error: <reason>` is not a verdict. Fix the inputs it names and send the review again. The resend does not count as a round.

## 4. Manual passes

### Screen by screen

At 1440x900, scroll one viewport at a time. Ask of each screen whether it holds enough to earn its height. A screen with only a heading and one line needs one of three changes: a larger visual, the line rewritten as a statement, or a merge with its neighbor.

### Squint test

Blur the full-page capture until no word can be read. Each section SHOULD still show a silhouette of its own, and the page SHOULD alternate heavy and light sections. Both are polish, `pol-00.chk-4`.

## 5. Polish list

Every item here is polish, clause `pol-00.chk-list-<n>` by its number. The checklist's own uncited SHOULDs use `pol-00.chk-<section>` instead. None blocks shipping. A fix, or an acknowledgment line after the build record, closes each one ([rule catalog](rule-catalog.md), section "Exception lines"). Checks that belong to the baseline or the habit band are graded under their own ids and do not appear here.

Item numbers are ids, so a retired item keeps its number and is never reused. Retired items grade under their home file's own id:

| Retired item | Home |
|--------------|------|
| 1. Curly quotes and one ellipsis character | [copy and honesty](copy-and-honesty.md), section 5 |
| 2. Balanced wrapping on display headings | [typography](typography.md), section 12 |
| 6. Browser surfaces styled from tokens | [color and surfaces](color-and-surfaces.md), section 7 |
| 8. Running text weights | [typography](typography.md), section 5 |
| 9. A single item stranded on a grid's last row | [layout and composition](layout-and-composition.md), "Grids" |
| 10. Hyphenation under justified text | [typography](typography.md), section 8 |
| 11. A hairline border under a broad soft shadow | [color and surfaces](color-and-surfaces.md), section 7 |

The current items:

| Item | Check |
|------|-------|
| 3 | No animation-file player where CSS or SVG does the job. |
| 4 | Highlight bands sit behind the lowercase letters, not on the baseline; underlines are 2 px or thinner and offset 0.25em or less. |
| 5 | In a flex row whose items differ in height, items are centered on the cross axis. |
| 7 | At 1440 wide, no text runs under 16 characters per line for 4 or more lines. |
| 12 | No block of 40 words or more shown on desktop and hidden on phones, navigation aside. |
| 13 | On a phone, each table follows the phone rule of [layout and composition](layout-and-composition.md), "Tables": its first view shows the columns that rule keeps visible. |
| 14 | At 375 and 1280, no heading of three lines or more has a line, other than its last, under 12 characters. |
| 15 | Each document has a one-sentence meta description. |

## 6. Document hygiene

Read each document's root element, `<title>`, landmarks, and heading outline against `acc-07` in the [rule catalog](rule-catalog.md). The catalog's section "Flags and downgrades" narrows the check at component scope.

## 7. No text under other elements

`lay-05` is a render check. At each sweep width, look for a line of text drawn beneath an opaque box, an image, or other text, and cite the element pair. With no browser, or no page to open, it grades `not checked` with the reason "no browser" or "no app".

## 8. Reporting

Report one count for each row of the Grades table in the [rule catalog](rule-catalog.md), section "Grades", eleven counts in that table's order, which is the order of the record's `grades:` field. Count `fail` and `habit-open` apart, as the catalog's shipping rule requires.

For each check, state how it was made: static read, render measurement with the tool that measured it, tool computation, or judgment. A check that did not run is `not checked`, with one reason from the catalog's `not checked` reasons table. A clause that a shape, posture, or genre exemption keeps from firing is not a skip: it produces no entry.

This report is the last step of the run, after every review has closed or been written `not run (<reason>)`. Only here are the counts written: they replace `grades: pending` in the build record, or in the check-only record on a repair or an audit, and they go into the Return Contract. No earlier step writes a count.

The catalog's shipping rule decides whether the page ships. The Return Contract's `checklist` row lists each `not checked` item with its reason.
