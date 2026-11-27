<!-- SPDX-License-Identifier: MIT -->

# Build Record

Reference for the [`ui-design`](../SKILL.md) skill. `SKILL.md`, section "Reference loading", sets when it loads: shape and direction choices read the build log, and the before-record of an audit holds a check-only record (section 2). A build leaves two written traces: a record at the top of the stylesheet, and an entry in the project's build log. Later sessions, linters, and reviewers read these instead of rebuilding past decisions from memory. Both survive context compaction; memory does not.

This file holds procedure and record format only, so it has no file code in the [rule catalog](rule-catalog.md). Its MUSTs are procedure MUSTs. A rule id it cites grades as the catalog row says. This file is the home for the record and log formats, the record's position in the stylesheet, and the self-critique scale.

## 1. The stylesheet record

The build record MUST be the first comment in the page's own authored stylesheet: the project stylesheet the build writes for the page, never the token sheet or the base sheet ([template](design-md-template.md), section 3). Only a license or header comment that the project's own convention requires MAY sit above it. The self-critique comment follows the record, then any exception lines: waivers, acknowledgments, dismissals, confirmations, and drops. All of them MUST sit inside the first 40 lines of the file. A line below line 40 is not read, and its finding stays open ([rule catalog](rule-catalog.md), section "Exception lines"). When the build writes no stylesheet, as with utility classes or CSS-in-JS, the record and these lines open the component's own source file instead, in that language's comment syntax, and every check reads them there.

The skill writes the token sheet, the base sheet, and this record before the nav and hero, because the hero stage runs static checks that read it. When the project already has a token file, the skill extends that file instead, as the [template](design-md-template.md), section 3, says. The sweep in the [pre-delivery checklist](pre-delivery-checklist.md) does not start until the record exists.

The first write holds every field the plan settles, with `grades: pending` and no `review:` field. Grades are written at the end of the run, never before the checks: the reporting step of the checklist, section 8, replaces `pending` with the eleven counts. Each review's outcome joins `review:` when that review closes.

```css
/* build-record v2 | scope: <page | component | app> | genre: <genre> | shape: <slug or coined name>
   | copy: <edited | verbatim> | depth: <new | full | restyle | polish> | mode: <standard | fast>
   | direction: <source>; <axes code>; <colorway or default>; <mood phrase> | motion: <dial value>, <user-set | default>
   | hero: <posture slug> | nav: <variant slug> | footer: <variant slug> | color: <posture>
   | palette: <light | dark | light and dark>; paper <L C H>; ink <L C H>; accent <L C H>
   | faces: display <family>; body <family>; outlier <family or none>
   | fingerprint: <six axis values, joined by " / "> | signature: <the one memorable move>
   | declared: <each outlier face or declared device, with its one job; or none>
   | comp: <none | approved n of m; <largest gap and how it closed | not verified (no browser | no app)>>
   | imagery: <photo count and sources; treatment; sample ids and positions>
   | review: hero <verdict | not run (scope) | not run (depth)> (via: <subagent | same-thread>; input: <captures | source-only>), finish <verdict> (via: <subagent | same-thread>; input: <captures | source-only>)
   | grades: <pending | fail n, habit-open n, warn n, waived n, dismissed n, confirmed n, dropped n, acknowledged n, open polish n, not checked n, note n> */
/* self-critique: pov 4, hierarchy 4, execution 3, specificity 4, restraint 5, variety 4
   | lowest: execution | change: <what was changed because of it> */
/* waive col-01.a | guard: <evidence the guard is met> | reason: <why, for this page> */
/* ack pol-03@#menu h2 | reason: <why the polish item stays> */
/* dismiss img-00.12@.hero video | reason: <why the suspected breach is not there> */
/* confirm cpy-00.3@footer | user: "<the user's words in chat>" | reason: <what the user confirmed> */
/* drop rds-02@#pricing h2 | reason: <why this page no longer carries the item> */
```

- The five exception lines follow the one syntax in the [rule catalog](rule-catalog.md), section "Exception lines". A line in any other form is rejected. A drop line appears only in a redesign or a repair. A confirmation line closes only a `judgment` `warn`, and only after the user confirmed in chat.
- `hero` takes a posture slug from the posture table in [hero](hero.md), section 2. `nav` and `footer` take a variant slug that [copy and honesty](copy-and-honesty.md), section 10 or 11, names, in its variant list or its prose, such as `colophon`. A posture or variant that those sections do not name is written `custom`. `rep-03` compares these slugs exactly.
- At component or app scope, a field with nothing to record is written `none (scope)`. That covers `shape`, `hero`, `nav`, `footer`, and `fingerprint`, and `imagery` when the build shows no picture.
- `palette` first names the modes the page ships. Then it holds the paper, ink, and accent tokens of the first mode as OKLCH lightness, chroma, and hue, for example `paper 97 0.006 250`. The first mode is light, or dark for a direction that is dark by design. An ink accent is written as the ink's values.
- `faces` holds the family names of the display, body, and outlier faces. A font substitution writes the face the page loads, and the log's `why:` line names the wanted one.
- `rep-01` compares `palette`, and `rep-02` compares `faces`. The display-face rule and the accent-hue check in [direction and themes](direction-and-themes.md), section 6, read the same two fields ([rule catalog](rule-catalog.md), section "Bookkeeping").
- `fingerprint` lists the six axis values of [page shapes](page-shapes.md) in order, joined by ` / `. `|` separates fields alone, so no field value contains it. A `none` that the material or the direction forces is written `none (forced)`; only that form is left out of the `rot-01.b` count. A custom run chooses no shape: `shape` holds a coined kebab-case name, and `fingerprint` names the page's own value on each of the six axes in plain words.
- Field values name the choice. They do not argue for it. Reasons go in the `why:` line of the build log entry (section 5). `DESIGN.md` holds no reasons. Component and app scope are not logged, so they put their reasons in the closing report instead.
- A font substitution ([typography](typography.md)) names the wanted face and its substitute on the log entry's `why:` line. Component and app scope name it in the closing report.
- `scope`, `copy`, `depth`, `mode`, and a `custom` direction source drive the downgrades in the rule catalog, section "Flags and downgrades". A new build writes `depth: new`.
- `direction` names its source: `DESIGN.md`, a brand spec, a direction the user named, candidate n of 3, or `custom`. Then it names the axes code, its three axes joined by ` / `, the colorway the page used (`default` when the direction has one), and the mood phrase ([direction and themes](direction-and-themes.md)).
- `review` records each review's verdict with its own two facts, because the hero and finish reviews can differ. `via` says who reviewed: the subagent, or the building thread on the same-thread route ([pre-delivery checklist](pre-delivery-checklist.md), section 3). `input` says what was read: captures, or the source alone when no capture could be passed. Both can apply at once, for example `finish fix (via: same-thread; input: source-only)`.
- Component and app scope run no hero review and write `hero not run (scope)`, with no `via` or `input` for it. A redesign at `depth: restyle` or `depth: polish` writes `hero not run (depth)` the same way ([rule catalog](rule-catalog.md), section "Flags and downgrades").
- A review still pending, because the build has not reached it, is left out of the field. A review skipped for good is written `not run (<reason>)`, for example `finish not run (budget spent)`, with no `via` or `input`.
- A v2 record written with one shared `via:` and `input:` after both verdicts is read as applying to both reviews. The next build rewrites it in the per-review form.
- A v2 record written before `palette` and `faces` existed, or with a `type:` field in place of `faces`, is read as written. The next build writes the current form.
- `motion` records the motion dial ([surface classes](surface-classes.md)) and whether the user set it. Only a user-set `expressive` meets the guard of `mot-01.a`.
- `declared` lists every outlier face with its one job. It also lists every device the direction adopts as material: a heading emphasis, a texture, an emoji voice, a single surface treatment, or a pure white or black token. Habit guards read `declared:`, and `DESIGN.md`'s `Declared` section when one exists. A name here closes no finding by itself: each habit finding still needs an accepted waiver line. A catch-all sentence takes a waiver through this field only when the catalog's material guard covers its section; no other catch-all sentence can be waived this way ([rule catalog](rule-catalog.md), section "Habit").
- `comp` records the comp outcome and the reproduction check, or `none`.
- Genre and scope follow [surface classes](surface-classes.md). Color posture follows [color and surfaces](color-and-surfaces.md).
- `review` and `grades` come only from checks that ran (section 7). Until the run's last report, `grades` reads `pending`. The final form carries exactly one count per row of the rule catalog's Grades table, eleven in all, named and ordered as that table lists them. A record written before `note` was counted is read as written.
- A page that needs a value other than one `DESIGN.md` sets uses a `Variants` entry the user approved, never a page-local override ([rule catalog](rule-catalog.md), section "Scope of taste").
- Some frameworks strip comments from the CSS they emit. The record then lives in the authored source file, and checks MUST read that file, not the built output.
- A rebuild rewrites the record. It does not stack a second one.
- A version 1 record is read as written. Its fields are `theme`, a count-style `review`, and the literal legacy key spelled `colour`, which older records carry in that British form. The next build replaces it with version 2, whose key is `color`.

## 2. Check-only record

When the skill audits any page, or repairs a page it did not build, it writes a check-only record instead:

```css
/* check-record v2 | date: <YYYY-MM-DD> | scope: <scope> | genre: <inferred> | depth: <repair | audit>
   | copy: <edited | verbatim | none (audit)> | mode: <standard | fast> | motion: <dial value>, <user-set | default>
   | signature: <the page's one memorable move, or none> | declared: <each device the page uses as material, with its one job; or none>
   | fixed: <rule ids> | findings: <structural findings printed> | builder: <project, outside generator, or earlier build>
   | review: finish <verdict> (via: <subagent | same-thread>; input: <captures | source-only>)
   | grades: <pending | fail n, habit-open n, warn n, waived n, dismissed n, confirmed n, dropped n, acknowledged n, open polish n, not checked n, note n> */
/* original: <the earlier build's record fields, unchanged> */
```

- `depth`, `copy`, and `mode` drive the downgrades in the [rule catalog](rule-catalog.md), section "Flags and downgrades", as in the build record. A repair writes `depth: repair`; an audit writes `depth: audit` and `copy: none (audit)`, since it edits no copy. A check-only record has no `direction:` field, because no direction was chosen.
- `motion`, `signature`, and `declared` carry what the habit guards read, as section 1 defines them. On an outside page, `declared:` names only a device that `DESIGN.md`, a brand spec, or the user's own words in chat confirm as material. Otherwise it reads `none`, and no guard that reads it can be met.
- A repair writes this record before its sweep, because the sweep does not start until a record exists ([pre-delivery checklist](pre-delivery-checklist.md), section 1). The first write carries `grades: pending` and no `review:` field. The finish review's outcome joins `review:` when it closes, and the run's last report writes the counts.
- An earlier check-only record without `depth`, `copy`, `mode`, `motion`, `signature`, or `declared` is read as written. A guard that needs a missing field is not met. The next repair writes the current form.
- `grades` carries every grade count, as in the build record. An earlier check-only record with a `fails:` field instead is read as written; the next repair replaces that field with `grades`.
- Where the record goes depends on the job. A repair changes the page's stylesheet, so it writes the record there, in the position section 1 gives the build record.
- An audit changes no project source file. Its check-only record goes inside the before-record ([redesign](redesign.md), section 3), with `fixed: none` and `review: finish not run (audit)`. A read-only host prints it with the before-record instead.
- The `original` line appears only when an earlier build of this skill made the page. Its fields stay exactly as found.
- `review` records the one finish review that a repair runs, in its variant for pages this skill did not build ([review protocols](review-protocols.md), section 5).
- A check-only record has no self-critique line. No plan existed, so nothing is scored.
- Never label an outside page as built by this skill.

## 3. Self-critique

At Step 5, before the decision summary, score the planned page from 1 to 5 on six axes. The plan is scored, not finished code.

| Axis | A 3 means | A 5 means |
|------|-----------|-----------|
| Point of view | It has a tone. | It makes a claim a reader can dispute. |
| Hierarchy | It needs a second read. | It stays legible when blurred. |
| Execution | A few details are loose. | It is clean on the first check. |
| Specificity | It suits the category. | It fits only this product. |
| Restraint | One ornament too many. | Something liked was given up. |
| Variety | It sits exactly at the `rot-01.b` limit against the closest of the logged builds that `rot-01` compares. | It shares one axis value or none with each of them. |

- Variety reads the `fingerprint:` field of the log entries that `rot-01` compares ([rule catalog](rule-catalog.md), section "Habit"). Component and app scope are not logged, so they score Variety as `n/a (scope)`, and it sends nothing back. A first build with no log entries scores it 5.
- Any score under 3 sends the plan back for revision. Score again after the change.
- Record the scores, the lowest axis, and the change made for it.
- If every axis scores 5, state what was removed to get there.
- Do not invent a weakness to fill the slot. An honest 4 with no change is a valid record.

## 4. Decision summary

After planning, print one compact block, once. It proposes the plan and its direction. The build waits until the user confirms or redirects them. A headless or fast run does not wait: it states the plan, proceeds, and says that it did not wait.

| Row | Content |
|-----|---------|
| Shape | The page shape and where it came from ([page shapes](page-shapes.md)) |
| Direction | Its source, its place among the candidates, a short description, and what it steers away from ([direction and themes](direction-and-themes.md)) |
| Chrome | Nav and footer |
| Hero | Posture, column spans, and visual size |
| Signature | The one memorable move |
| Sections | The section list, in order |
| Material | Real, pictures, or absent ([page anatomy](page-anatomy.md)) |
| Sweep | Not run, running, or done |

- On a custom run, the Shape and Direction rows become an idea sentence and a `look` row, as [direction and themes](direction-and-themes.md), section 6, says.
- Add one short line offering to freeze the system into `DESIGN.md`. Omit it for a component, or when the file already exists.
- At the end, print only the rows that changed, plus the final grade counts.
- State the plan once. Do not narrate it again.

## 5. Build log

The build log is `design-log.md`. It sits beside `DESIGN.md`, or at the project root when no `DESIGN.md` exists. When `DESIGN.md` is first written outside the root, move `design-log.md` beside it in the same change. The log belongs to the project and is committed with it. It never lives in `.apothem/` or in a harness configuration directory.

The skill's working state is separate. It lives in `<project-root>/.apothem/ui-design/`, under the file names `SKILL.md`, section "Output Surface", gives. That folder stays out of version control. When the project's `.gitignore` does not cover `.apothem/`, ask the user before adding the line. When they decline, or the run is headless, leave `.gitignore` unchanged and name the folder in the closing report.

Newest entry first. Every entry carries the same fields:

```markdown
## <YYYY-MM-DD> <page name>
shape: <slug> | direction: <source>; <axes code>; <colorway or default>; <mood phrase> | fingerprint: <six axis values, joined by " / ">
palette: <modes>; paper <L C H>; ink <L C H>; accent <L C H> | faces: display <family>; body <family>; outlier <family or none>
hero: <posture slug> | nav: <variant slug> | footer: <variant slug> | opening: <first section> | sections: <in order> | openers: <opener types used>
signature: <the one memorable move> | photos: <ids> | imagery: <treatment, samples> | waivers: <clause ids>
why: <one clause per choice a later session would question> | prompt: <the request, one line>
```

- `shape`, `direction`, `fingerprint`, `palette`, `faces`, `hero`, `nav`, and `footer` copy the build record's values exactly, so the checks in the [rule catalog](rule-catalog.md), section "Bookkeeping", compare like with like.
- `sections` lists the page's sections in order. A deck page ends it with its two deviations in the short form of [page anatomy](page-anatomy.md), "Two required deviations".
- `openers` lists the section opener types the page used ([copy and honesty](copy-and-honesty.md)), so the next page can rotate them.
- Log pages only. Components and app screens are not logged and do not rotate. An audit of any page, and a repair of a page this skill did not build, are not logged either. Each page of a multi-page redesign gets its own entry.
- An entry written before a field existed is read as written. A check that needs the missing field skips that entry. An entry with `type:` in place of `faces:` is read as `faces:`.
- Judge new work against the log, not against memory.

### Rotation

Rotation is one habit rule, `rot-01`, plus three bookkeeping notes. Their clauses, limits, and guard are in the [rule catalog](rule-catalog.md), sections "Habit" and "Bookkeeping". Rotation is done by hand against the log entries those rows compare. No random picker is used.

- Read those entries before choosing the shape and the direction.
- Compare the planned `shape:` and `fingerprint:` with those entries under `rot-01`, before the decision summary.
- The guard of `rot-01` is a request by name. The log's `prompt:` line records that request.
- After the build, compare the entry's `palette:`, `faces:`, and chrome fields under `rep-01` to `rep-03`. They never block.

### Neighbor-prompt test

Picture a second brief from the same category. If that brief would end with the same set of structural choices, this page is generic. Change one choice and name it in the decision summary.

## 6. Handoff material request

Every build ends with a material list:

- Each placeholder position, with its dimensions and intended content.
- Each stand-in image and rebuilt product sample, with its place, its dimensions, and what the replacement is to show.
- Each openly licensed photo, with the facts [imagery and data](imagery-and-data.md), section 1, records for it.
- Then one line naming the single item whose arrival would improve the page most.

## 7. Honesty rules

- Never report a count for checks that did not run. A check that did not run is `not checked`, with its reason.
- After context compaction, re-read the stylesheet record and the build log before the next decision. Do not reconstruct them.
- If a reference file will not load, name it and continue on the baseline in the [rule catalog](rule-catalog.md).
- A named tool is optional; the check it serves is not. If the tool is missing, run the check another way and say how, or grade it as the rule catalog directs.
- Run tool calls in parallel only where the host runs them reliably.
