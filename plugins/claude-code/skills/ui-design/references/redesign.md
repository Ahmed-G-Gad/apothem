<!-- SPDX-License-Identifier: MIT -->

# Redesign

Reference for the [`ui-design`](../SKILL.md) skill. This file covers changing pages that already exist: a redesign, a restyle, a polish pass, an audit, or a fix to a page this skill did not build. A redesign lands as one reviewable diff that keeps everything the page does. Rule ids come from the [rule catalog](rule-catalog.md). This file's catch-all is `rds-00`.

## 1. Preservation contract

These hold at every depth. Two baseline rules grade them: `rds-01` for wiring and `rds-02` for content. Their [rule catalog](rule-catalog.md) rows set each grade and how a loss closes.

- **Wiring (`rds-01`).** Keep every link, form, field, event handler, route, test hook, and script. Keep every data or analytics call, and every selector or id that code reads.
- **Wiring edits.** Change the markup of a component only inside that component's own file. Never rename a prop. Never drop an attribute that a script or a test reads.
- **Content (`rds-02`).** Keep the page's facts and claims as they stand: names, prices, dates, and quotes included. Keep its headings, figures, images, and the ids no code reads. A lost item is restored, or a drop line records why the page no longer carries it (section 6).
- **Claims.** Existing figures, quotes, and logos carry over, and the handoff lists them for the user to verify. Add nothing new unless the user supplies it or a rule demands it, such as a focus ring or a pause control on a loop.
- **Files.** Delete a file, a route, or a component tree only when the `Files` row the user approved (section 4) lists it. Never edit a test to make it pass.
- **Working tree.** Start from a clean git working tree. When the host offers a shell, check the tree. Otherwise ask the user to confirm that it is clean. If it is dirty, ask the user to stash or commit. The skill MUST NOT stash or commit on the user's behalf.
- **Brand.** Keep a real brand, read from project files. A brand value recalled from memory breaks `cpy-02`. Framework defaults and looks the catalog flags are not brand.
- **Words.** Reword only lines that break the [copy rules](copy-and-honesty.md), and list each with its before and after. Never touch legal or consent wording.
- **Missing states.** When the code has no state for empty, error, or loading, list the gap for the owner. Do not build behavior the code does not have.

## 2. Depths

Pick one depth and write it in the build record's `depth:` field ([build record](build-record.md)). Depths never blend inside one pass.

| Depth | Kept | Replaced | When |
|-------|------|----------|------|
| `full` | Content and wiring | System and composition | The default |
| `restyle` | Layout | Color, type, radii, shadows, motion, controls | Only on an explicit request, such as "keep the layout" or "reskin" |
| `polish` | System and layout | Flagged tells, contrast, states, motion, and the token values the baseline or `col-03.b` flags | Only on an explicit request |

- If a polish pass finds the concept itself is wrong, it stops and recommends `full`. It does not perform one.
- At `full` depth on app screens, recompose each screen inside its existing shell.
- Starting over from nothing is a new build (`depth: new`), placed beside the old files. It is not a redesign.
- A page this skill did not build takes none of these depths. Its repair (section 8) writes `depth: repair` in the check-only record ([build record](build-record.md), section 2).
- Each depth changes the grades the rule catalog lists and decides whether the pass has a hero stage. The [rule catalog](rule-catalog.md), section "Flags and downgrades", lists both.

## 3. Before-record

Before any edit:

1. Run the pre-flight scan (SKILL Step 0) on the project: framework, stylesheets, `DESIGN.md` when present, and the [build log](build-record.md).
2. List the pages in scope. One row each: route, file, and kind (page or app screen).
3. Run the check pass in before mode on each page, as the [pre-delivery checklist](pre-delivery-checklist.md), section 1, "Before mode", defines it. The [rule catalog](rule-catalog.md), section "Flags and downgrades", "Before mode", sets how that pass grades. The files this pass loads at Step 0 are listed in `SKILL.md`, section "Reference loading". Save the findings, the screenshots, and a structured inventory in `<project-root>/.apothem/ui-design/`, which stays out of version control ([build record](build-record.md)). Screenshots need a browser on the host. Starting the project's app for them runs only under the run gate in `SKILL.md`, section "Agent operations", with the approval Step 0 obtained. When no screenshot can be taken, the before-record lists the screens to capture, and render checks grade `not checked` with the reason the [rule catalog](rule-catalog.md), section "Grades", names for the case. A host that cannot write files prints the before-record in the reply instead. The inventory lists links, forms, fields, inline handlers, test hooks, script tags, selectors that scripts query, ids, headings, figures, and images.
4. Look at the screenshots, or at the source when there are none, before reading the findings. Then write a four-line assessment:
   - **Purpose:** the audience and the action the page asks of them.
   - **Keep:** the parts that already do their job and carry over. Name one at minimum.
   - **Generated:** the worst tells of a machine-made page.
   - **Broken:** what does not work.

**Audit only.** A request for an audit stops here. Report the findings grouped by band, each cited as `file:line`, each with the lightest depth that would fix it. Change no project source files. The audit's check-only record goes inside the before-record, with the audit values the [build record](build-record.md), section 2, sets, among them `review: finish not run (audit)`. The before-record is the only file an audit writes, and a read-only host prints it instead.

## 4. Intake and plan

A redesign replaces the normal intake with three questions:

1. What has to stay?
2. What is wrong, in the user's words, and how should it feel?
3. Is there new material: copy, photos, figures?

The user MAY skip the questions and go ahead with `full`.

The [decision summary](build-record.md) opens with these rows, before the usual ones:

| Row | Content |
|-----|---------|
| Depth | The depth and the page count |
| Before | The inventory counts and a one-line verdict |
| Kept | What carries over unchanged |
| Files | Files to edit, create and delete |

The user MUST see the `Files` row before anything is removed. Seed the direction in [direction and themes](direction-and-themes.md) from a plain-noun account of the page's purpose, never from its existing copy.

## 5. Editing existing stylesheets

Edits to a project's stylesheets are append-only in shape.

- List the files to change before changing them.
- Place a new `@import` straight after the last existing `@import`. Never after a rule or a utility-framework directive: CSS ignores a late `@import` without an error.
- Reuse the token names the project already defines. Add a token only when none fits, and declare it in the token sheet ([template](design-md-template.md)). When `DESIGN.md` exists, it stays as it is, and the closing report proposes the new token as an entry for the user to approve.
- Never remove a route or a component tree unless the `Files` row the user approved (section 4) lists it.

## 6. Regression sweep

After the build, run the check pass again and compare it with the before-record.

| Lost item | Rule |
|-----------|------|
| Link, form, field, handler, route, test hook, script, data or analytics call, or a selector or id that code reads | `rds-01` |
| Fact, heading, figure, image, or an id no code reads | `rds-02` |

Each rule's [rule catalog](rule-catalog.md) row sets its grade.

- Restore each lost item. For a content item, a drop line MAY record the loss instead, for example `/* drop rds-02@#pricing h2 | reason: <why this page no longer carries it> */`. A dismissal never records a drop: it states only that a suspected breach is absent ([rule catalog](rule-catalog.md), section "Exception lines").
- Record reworded and removed lines in the handoff table below.
- When the host offers a file-write tool, build a side-by-side before and after comparison page in `<project-root>/.apothem/ui-design/` from the two sets of screenshots, which need a browser. Otherwise the `Comparison` row reads `not built (<reason>)`, such as no browser or no file write.
- Run the project's own type check, build, and tests only under the run gate in `SKILL.md`, section "Agent operations", with the approval Step 0 obtained for each exact command. Otherwise ask the user to run them and report the results. List each one the user does not report in the `Checks` row as not run. If any of them breaks, the work is not done.

The downgrades for each depth are listed only in the [rule catalog](rule-catalog.md), section "Flags and downgrades", under the two redesign entries. Apply those and no others.

Hand off with one table:

| Row | Content |
|-----|---------|
| Depth | Depth and pages |
| Counts | Inventory counts before and after |
| Retained | Ratios for links, fields, handlers, headings and figures, such as `links 42/42` |
| Changed | What changed |
| Dropped | Each item graded `dropped`, with the reason from its drop line |
| Claims | Figures, quotes and logos left as found, for the user to verify |
| Reworded | Each reworded line, before and after |
| Checks | The project's type check, build, and tests, each with its result, or `not run (<reason>)`, such as no shell or not approved |
| Comparison | The path to the comparison page, or `not built (<reason>)` |

## 7. Several pages

When a restyle or a full redesign covers several pages:

- Freeze the system once scaffolding is done. Write it to `DESIGN.md` when none exists ([template](design-md-template.md)); an existing one is the system and is not overwritten. Every page shares the direction, typography, and accent. Pages differ only in shape.
- Rotation between the pages of one run follows the `rot-01` row of the [rule catalog](rule-catalog.md), which states how its clauses compare pages of one multi-page redesign.
- One stylesheet records which [hero](hero.md) posture each route uses.
- Build shared components and chrome first. Then build pages in order of traffic, and sweep each page before starting the next.
- Beyond three pages, delegate each page to its own general-purpose subagent, one page at a time. Each one receives the absolute path of `SKILL.md` and of every reference file of this skill except `references/review-protocols.md`, which a building thread MUST NOT load, and the brief states that exclusion. It also receives `DESIGN.md`, the build log path, its page's rows of the decision summary, the folder and exact commands the parent's Step 0 approved, and nothing else to choose. The brief says to run no command beyond them. It also says that the parent runs the design-critic reviews and holds the verification budget, so the subagent sends no review of its own. The subagent starts at Step 6 with the parent's decisions, skips Step 0 approval, Step 1 intake, and the Step 5 wait, and writes its page's build record and log entry. At `depth: full`, the subagent returns after the hero stage's checks; the parent runs the hero review, then delegates the rest of the page. When the host's subagents cannot write files, the parent builds the pages itself, in order.

## 8. Pages this skill did not build

When fixing a page built by the project or by another generator:

1. Infer the scope (page, app, or component) and the genre from [surface classes](surface-classes.md), and say both. A tie between two genres resolves as [surface classes](surface-classes.md), section "Genre routing", states. The [rule catalog](rule-catalog.md), section "Flags and downgrades", sets how the page grades at that scope and genre, in before mode and after it.
2. Write the check-only record ([build record](build-record.md), section 2) with `depth: repair`, `grades: pending`, and no `review:` field. It goes in the file and at the position that the [build record](build-record.md), section 1, sets. The sweep needs it in place. Before the first edit, list the page's wiring and content items in the form of the section 3 inventory; `rds-01` and `rds-02` compare against that list, and a drop line is allowed.
3. Repair in place only the surface layer: tokens, color, typography, motion, states, and contrast. Single-element repairs are also in scope: merge an announcer label into its heading, add focus styling, replace a gradient with a flat fill, tint a flat gray.
4. Do not restructure. Report structural findings instead: hero and fold, page shape, section rhythm, repeated compositions, chrome, word budget. Cite each at its `file:line` and propose the repair in one sentence. The user decides. A long page is one of these findings; `cpy-05` grades as the catalog's "Redesign, any depth" route sets.
5. Run the sweep and its fix batch.
6. Run the finish review in its variant for pages this skill did not build, with the check-only record as it stands. [Review protocols](review-protocols.md), section 5, sets its question and the verdicts it can return. The [pre-delivery checklist](pre-delivery-checklist.md), section 2, counts it in the budget.
7. Fill the record's `review:` field with the review's outcome. The run's last report, [pre-delivery checklist](pre-delivery-checklist.md), section 8, replaces `pending` with the counts.
