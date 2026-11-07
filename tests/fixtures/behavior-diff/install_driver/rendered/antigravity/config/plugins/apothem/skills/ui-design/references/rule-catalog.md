<!-- SPDX-License-Identifier: MIT -->

# Rule Catalog

Reference for the [`ui-design`](../SKILL.md) skill. Nine categories in priority order. When two rules conflict, the rule in the higher category wins and the lower one is adjusted to fit, not discarded.

## Priority table

| Rank | Category | Question it answers | Wins over |
|------|----------|---------------------|-----------|
| 1 | Accessibility | Can everyone perceive and operate it? | All below |
| 2 | Touch and pointer targets | Can the input device hit it reliably? | 3 to 9 |
| 3 | Performance | Does it appear and respond quickly? | 4 to 9 |
| 4 | Layout and responsiveness | Does it fit every viewport and content length? | 5 to 9 |
| 5 | Typography and colour | Is it legible and consistent? | 6 to 9 |
| 6 | Motion | Does movement explain rather than distract? | 7 to 9 |
| 7 | Forms | Can input be given and corrected easily? | 8, 9 |
| 8 | Navigation | Can people tell where they are and get elsewhere? | 9 |
| 9 | Data display | Are tables, charts, and figures readable and honest? | none |

Worked conflicts:

- A compact table row of 28 px against a touch-capable surface: category 2 wins; keep rows at the target minimum where touch is supported, or give pointer-only tools a compact mode selected by the pointer media feature.
- A hero animation that delays the main heading: category 3 wins over 6; show the content first and animate after.
- A brand colour that fails contrast on its background: category 1 wins over 5; darken or lighten the token, or place the text on a surface that passes.
- An expressive entrance sequence with the reduced-motion preference set: category 1 wins; replace travel with an instant or opacity-only change.

## 1. Accessibility

- Body text contrast is at least 4.5:1 against its background; large text (24 px, or 19 px bold) and interface component boundaries and icons that carry meaning are at least 3:1. Check every theme the product ships.
- Never convey meaning by colour alone; pair it with text, an icon, a pattern, or position.
- Every interactive element has a visible focus indicator of at least 2 px with 3:1 contrast against adjacent colours. Never remove the outline without a replacement.
- Everything operable by pointer is operable by keyboard, in an order that matches the reading order. No keyboard traps; dialogs return focus to their trigger on close.
- Use native elements first: button, link, input, select, dialog. Add ARIA only where no native element expresses the role, and keep names, roles, and states accurate.
- Every icon-only control has an accessible name; every image has alternative text that serves its purpose, or empty alternative text when decorative.
- Use landmarks (header, nav, main, footer) and a single page heading followed by an unbroken heading ladder.
- Respect the reduced-motion and contrast preferences. Text must reflow and remain usable at 200 percent zoom and at a 320 px wide viewport without two-dimensional scrolling.
- Announce dynamic changes (errors, toasts, results counts) through a live region, politely unless the change blocks the task.

## 2. Touch and pointer targets

- Interactive targets are at least 44 by 44 CSS px on touch surfaces; never below 24 by 24 CSS px anywhere, spacing included.
- Leave at least 8 px between adjacent targets so a mistap does not hit its neighbour.
- A small visual can have a larger hit area through padding; the hit area is what counts.
- Do not rely on hover for essential information or actions; every hover affordance has a tap and keyboard equivalent.
- Place primary actions within thumb reach on phones; destructive actions sit apart from frequent ones.
- Gestures (swipe, long press, drag) are shortcuts, never the only path.
- Give immediate pressed-state feedback within 100 ms of input.

## 3. Performance

- Reserve space for images, embeds, and late content with explicit dimensions or aspect ratios so nothing shifts after load; cumulative layout shift stays under 0.1.
- The largest visible element on the first screen should render within 2.5 s on a mid-range phone over a typical mobile connection. Do not lazy-load that element.
- Lazy-load below-the-fold images and media; serve responsive sizes and modern formats.
- Limit web fonts to what the design uses (one or two families, few weights); load with a fallback that matches metrics to prevent text reflow.
- Avoid long main-thread tasks; keep input response under 200 ms.
- Prefer CSS for effects. Animate only transform and opacity; avoid animating layout properties.
- Show a skeleton or progress indicator for any wait over 300 ms, and stable placeholder dimensions that match the final content.

## 4. Layout and responsiveness

- Design mobile width first, then widen. Support 320 px up to large desktop with no horizontal page scroll.
- Use a spacing scale from `DESIGN.md` (for example multiples of 4 or 8 px); do not introduce one-off values.
- Use fluid layout with a maximum content width; choose breakpoints from where the content breaks, not from device names.
- Align to a consistent grid; group related items by proximity before adding dividers or boxes.
- Set a clear reading order that survives the stacked mobile layout.
- Respect safe areas on devices with notches and system bars; keep fixed headers and footers short so they do not eat the viewport.
- Test with the longest realistic label, a name with no spaces, a right-to-left language, and an empty list.
- Set a z-index scale in `DESIGN.md` (content, sticky, overlay, modal, toast) rather than ad hoc numbers.

## 5. Typography and colour

- Body text is at least 16 px with line height 1.4 to 1.6; the measure for running text is 45 to 75 characters.
- Use a modular type scale with a small number of sizes (five to seven) and no more than two typefaces. Hierarchy comes from size, weight, and spacing before colour.
- Headings are tighter than body (line height 1.1 to 1.3); never set long text in all capitals or in light weights at small sizes.
- Build colour from tokens: neutral ramp, one primary, semantic colours (success, warning, danger, info). Name tokens by role, not by hue.
- Provide light and dark themes from the same tokens when the product supports both; dark is not an inversion, so retest contrast and shadows.
- Limit saturated colour to what needs attention; keep large areas neutral.
- Use tabular figures for numbers that align in columns.
- Icons come from one family at one stroke weight; do not mix outline and filled styles without meaning.
- Prefer system or open-licensed fonts, and record the licence in `DESIGN.md` when a font is added.

## 6. Motion

- Motion must communicate: show origin, cause, or continuity. If removing it loses nothing, remove it.
- Durations: 100 to 150 ms for small state changes, 200 to 300 ms for entrances and exits, up to 500 ms for large layout transitions. Exits are shorter than entrances.
- Use ease-out for entering, ease-in for leaving, ease-in-out for movement within the screen. Avoid linear except for continuous progress.
- Never animate while the user is reading or typing in the same region. No auto-playing loops longer than 5 s without a pause control.
- Stagger lists in steps of 20 to 50 ms and cap the total below 400 ms.
- Under the reduced-motion preference, drop travel, parallax, and zoom; keep opacity changes and state feedback.
- Interruptible: a new input cancels or reverses an animation instead of queuing behind it.

## 7. Forms

- Every field has a visible, persistent label; a placeholder is a hint, never the label.
- Mark optional fields rather than required ones when most are required, and be consistent.
- Use the correct input type, autocomplete token, and input mode so the right keyboard and autofill appear.
- Validate on blur or submit, not on every keystroke; show the error next to its field in text, with the fix, and move focus to the first invalid field on submit.
- Never clear what the user typed after an error. Preserve drafts across accidental navigation where the data is costly to re-enter.
- Group related fields; use one column unless fields are short and clearly paired.
- The primary submit action is named for its result ("Save changes", not "Submit"); disable it only while the request is in flight, and show progress.
- Confirm destructive actions by naming what will be lost, or better, offer undo.
- Provide helper text before the field when the format is not obvious, and show password rules before the user types.

## 8. Navigation

- Show the current location in the navigation and in the page title; keep primary navigation to seven items or fewer.
- Use the same navigation in the same place on every screen of a product. Do not hide primary navigation behind an icon on desktop widths.
- Links look like links and say where they go; buttons perform actions, links navigate.
- Back, forward, and refresh behave as expected: state worth sharing lives in the URL, and the back button never traps the user.
- Provide a way out of every modal, step, and mode, and a visible way to cancel long flows.
- For deep structures, add breadcrumbs or an in-page contents list; offer search once content exceeds what the menu can show.
- On phones, bottom navigation suits three to five top-level destinations; keep labels visible under icons.
- A "skip to main content" link is the first focusable element on pages with repeated navigation.

## 9. Data display

- Right-align numeric columns, left-align text, and use consistent decimal places and units; show units in the header, not every cell.
- Make rows scannable: a clear header row, subtle row separation, and a sticky header for long tables. On narrow screens, restructure the table into cards or allow controlled horizontal scrolling inside the table region.
- Show sort and filter state explicitly, with counts of results shown and total.
- Truncate with an ellipsis only when the full value is reachable by tooltip, expansion, or detail view.
- Every empty table or chart explains why it is empty and what to do next; every loading one keeps its shape.
- Charts: start the axis of a bar chart at zero, label axes and units, label series directly where possible, and use a colour-blind-safe palette with a non-colour cue. Offer the underlying numbers as a table.
- Pick the chart for the question: comparison (bars), change over time (lines), part of a whole (a few segments at most), relationship (scatter).
- Show freshness for live or cached data ("Updated 2 minutes ago") and the time zone for timestamps.
- Format dates, numbers, and currencies by locale.
