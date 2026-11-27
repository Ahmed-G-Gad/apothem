<!-- SPDX-License-Identifier: MIT -->

# Review Protocols

Reference for the [`ui-design`](../SKILL.md) skill, read by the reviewer only. The [`design-critic`](../../../agents/design-critic.md) subagent loads this file in review mode for the hero review and the finish review. The building thread MUST NOT load it while it builds. When a review takes the same-thread route ([pre-delivery checklist](pre-delivery-checklist.md), section 3), the building thread loads it only at the review point, after its fix batch, and the build record says `via: same-thread` for that review. The builder's side, meaning the inputs, the verification budget, and what happens after a verdict, lives in the [pre-delivery checklist](pre-delivery-checklist.md).

This file holds procedure only, so it has no file code in the [rule catalog](rule-catalog.md). Its MUSTs bind the reviewer and are not page checks. It is the home for the verdict words, the reply format, the finding caps, and the turn limit.

## 1. Rules for both reviews

- Change no file. Read for 10 turns at most.
- The first input line names the mode: `review: hero`, `review: finish`, or `review: finish (outside page)`. Run the section that line names. With no mode line, reply `error: no mode line` and review nothing.
- Read this file and the rule catalog at the absolute paths the invoker passed. Do not resolve them from the project's working directory. When a passed path is not absolute, or does not open, reply `error: <the path> does not open` and review nothing.
- Beside the passed `rule-catalog.md`, in the same folder, sit the files its file-code table names. The reviewer MAY open those topic files, and only to grade a cited rule: a rule or section that a finding cites, or that a question of its mode names, such as the headline budget of hero question 1. The reviewer MAY also open `build-record.md` there, for the record, log, and fingerprint formats that `rot-01` and hero question 7 read. Open no other skill file.
- Captures arrive as the absolute paths of the image files that the [pre-delivery checklist](pre-delivery-checklist.md), section 1, saves. Read those files first. Open the source only to locate or quote a finding. A same-thread review reads the captures it took.
- With no captures, read the source and write the first line as `<verdict> (source-only)` (section 2).
- Grade against the [rule catalog](rule-catalog.md). Cite a rule id for each finding. Use `taste` only when no rule applies; a `taste` finding never blocks.
- Measure targets against `tgt-01`, then against `tgt-04`, as their catalog rows state. Measure contrast against `acc-01` as its row states.
- Treat every well-formed exception line in the record position as accepted: the check pass removed each rejected line before the review ([rule catalog](rule-catalog.md), section "Exception lines"). Two faults show on the line itself, and such a line is not accepted: a waiver that targets a baseline rule, and a waiver that names a whole rule instead of one clause. Report the finding such a line names.
- Do not report again a finding that an accepted waiver, dismissal, confirmation, acknowledgment, or drop line after the build record already closes. Do not report a clause that `DESIGN.md` made a project default under the catalog's house-style route.
- A device named in `declared:`, or in `DESIGN.md`'s `Declared` section, with no accepted waiver line is still a finding. Report it under its clause; it grades `habit-open`.
- Report a number only when a tool produced it: the invoker's measurement, or a measuring tool the reviewer has. A size or area read by eye from a capture is not a number. Call such a property unmeasured.

## 2. Reply format

The first word is the verdict. The first line holds the verdict alone, or `<verdict> (source-only)` when no captures came:

| Verdict | When |
|---------|------|
| `recapture` | Captures are missing, blank, of the wrong page, or at a size other than the one their file name states. Not available with no captures |
| `rebuild` | The screen misses the stated direction or idea entirely. Not available for a page this skill did not build |
| `fix` | Findings follow |
| `ship` | Nothing material remains |

One finding per line follows, worst first:

```text
<verdict>
<rule id or taste> | <where: selector, section, or file:line> | <what is wrong, in one line>
keep | <where: selector, section, or file:line> | <what the fixes MUST NOT weaken, in one line>
```

The `keep` line is optional. Only a finish review writes it, in either variant (sections 4 and 5), at most once, as the last line. It does not count toward the finding cap. These lines are the whole reply. Review mode adds no disclosure ledger, summary, or closing note, and any gate or checklist the reviewer runs for itself adds nothing. The two input errors in section 1 replace the verdict. Such a reply is the single line `error: <reason>`, with no findings.

The hero review returns at most 5 findings. The finish review returns at most 8, or 5 at polish depth and for a page this skill did not build.

## 3. Hero review

Runs only where the catalog's hero stage runs: at page scope, in a new build or a redesign at `depth: full` ([rule catalog](rule-catalog.md), section "Flags and downgrades"). Component and app scope, a redesign at `restyle` or `polish` depth, and a repair of an outside page have no hero review.

Inputs: everything the invoker passed after the mode line `review: hero` and the two paths. On a custom run, the idea sentence and the `look` row stand in for the Direction row.

Questions:

1. Would the headline still be true on a competitor's page? Does it keep to the headline budget in [copy and honesty](copy-and-honesty.md), section 2?
2. Does the hero meet the vertical balance its posture takes in [hero](hero.md), section 4, with no dead band under its lowest element (`hro-01`)?
3. Does the visual show the real subject, beside or behind the text, at the size [hero](hero.md), section 6, sets? When the shape keeps pictures off the first screen, does type fill it instead?
4. Which template tells show? Look for the stock centered stack that [hero](hero.md), section 5, names, or a pill or small label set over the headline. Look for a soft decorative shape behind the heading, or a flat tinted rectangle where a picture belongs. Look for an illustration drawn in code, a row of tally marks, or two filled buttons (`lay-06.a`).
5. Is the signature on this screen? Imagine the picture removed. When the screen's message survives unchanged, the picture is not doing its job.
6. Does the typography carry the direction?
7. Does the screen look finished? Does it differ from the build log entries passed in the inputs, by their fingerprint, hero, nav, and footer fields? With `log: none`, ask only whether the screen looks finished.

Variants:

- **Custom direction.** Replace question 7 with: is this the screen a model would predictably produce?
- **Redesign.** Do not critique content the plan's Kept row names, which the inputs carry.

## 4. Finish review

Inputs: everything the invoker passed after the mode line `review: finish` and the two paths. On a custom run, the idea sentence and the `look` row stand in for the Direction rows. At component and app scope, the record shows `hero not run (scope)`; at `restyle` or `polish` depth, `hero not run (depth)`.

Questions:

1. Step through the page one screen at a time. A screen with nothing large enough to earn its height outranks any small detail.
2. Which headings would stay true on a competitor's site?
3. Does the stated direction describe this page? Name the largest gap.
4. If something has to survive the fixes, name it in the one `keep` line of section 2.

Variants:

- **Custom direction.** First write down the page's subject and its memorable element. Then judge whether the page feels seen before, whether any part has no job, and whether the idea fades after the hero.
- **Redesign.** Also name what the previous page did better, read from the before-record and its captures in the inputs. Leave out what the Kept row already carries over. Each such point is a finding cited `taste` or by the rule it bears on.
- **Polish depth.** Ask only whether anything still looks machine-made.
- **Components and app screens** ([surface classes](surface-classes.md)). Judge hierarchy, even density, controls and tables at phone width, and whether every state exists.

## 5. Pages this skill did not build

A repair of an outside page ([redesign](redesign.md), section 8) runs the finish review in this variant, under the mode line `review: finish (outside page)`. It is the polish-depth question set applied to a page with no build record.

Inputs: everything the invoker passed after the mode line and the two paths. The page source comes in every case. With captures, open the source only to locate or quote a finding, as in the other reviews. There is no decision summary and no `DESIGN.md` unless the project has one.

- Ask one question: does anything still look machine-made?
- Grade each finding against the rule catalog, as in section 1.
- `rebuild` is not available, because the repair does not restructure. Instead, cite a structural finding at its `file:line` and propose the repair in a single sentence.
- Return findings up to the cap in section 2, in its reply format. If something has to survive the fixes, name it in the one `keep` line.
