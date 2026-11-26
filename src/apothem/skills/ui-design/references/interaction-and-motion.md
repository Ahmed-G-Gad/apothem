<!-- SPDX-License-Identifier: MIT -->

# Interaction and Motion

Reference for the [`ui-design`](../SKILL.md) skill. All scopes; component scope loads this file on its own (see [surface classes](surface-classes.md)). It covers control states, forms, overlays, feedback, and motion. Rule ids and grades live in the [rule catalog](rule-catalog.md). A flag in this file that cites no id grades under the catch-all `mot-00.<section>`. Color values for states come from [color and surfaces](color-and-surfaces.md). State copy follows [copy and honesty](copy-and-honesty.md).

## 1. States per control

Which states a control, a link, a field, or a data region needs is set only in the `lay-02` row of the [rule catalog](rule-catalog.md). This section gives the look of each state that row asks for. A missing state leaves the component unfinished (`lay-02`). Generated interfaces style the default state and skip the rest, so check the others first. Text inputs, textareas, selects, and comboboxes take the field recipes in section 5 instead.

| State | Recipe |
|-------|--------|
| Default | The resting look, from tokens. |
| Hover | One cue only, inside `@media (hover: hover)`. See section 13.9. |
| Focus-visible | The ring from section 2, shown at once. |
| Active | A button takes the 1px downward shift of section 4. Any other control takes that shift or one darker step, never both. |
| Disabled | The native `disabled` attribute, plus `cursor: not-allowed`, plus opacity 0.55. All three apply. A control that stays focusable takes `aria-disabled="true"` in place of the attribute and fades its label and fill through token colors or opacity on an inner element, never `opacity` on the focus-bearing element. Its ring keeps full strength and meets `acc-03`. |
| Loading (busy) | After a 150 to 300ms delay, a spinner appears beside the label. Once shown, it stays at least 300ms. After 2s, a short text line says what is happening; its words follow [copy and honesty](copy-and-honesty.md), section 4. The label remains legible and the control keeps its width, with `cursor: progress`. The busy state is announced through a polite live region, or through visually hidden label text such as "Saving" (`acc-10`). `aria-busy="true"` goes only on the region whose content is being updated, never on the button. |
| Error | Color, a text message, and `aria-invalid="true"`. Never color alone (`acc-02`). |
| Success | Only on a control whose request has an outcome the page reports (`lay-02`). Shown only after a real server response, as an icon at most, with no toast. The icon has an accessible name (`acc-06`), and the outcome goes to a polite live region (`acc-10`). When no request was made, it never appears (`cpy-08`). |

## 2. Focus ring

- Every interactive element has a `:focus-visible` style. An outline MUST NOT be removed without a replacement (`acc-03`).
- The ring is a 2px solid line in the `focus` color. On buttons and links it sits 2px outside the element.
- On fields the ring sits 2px inside (`outline-offset: -2px`), so neighboring fields never collide with it. Every field uses this one inset offset.
- The ring meets the `acc-03` contrast against every color it touches. A ring set 2px outside touches only the backdrop, so an accent-filled button's own fill is not one of those colors. The inset field ring paints over the field's `rule-hair` border. Its outer edge touches the backdrop around the field, and its inner edge touches the field fill, so it meets that contrast against both. A ring that misses that contrast against any color it touches fails `acc-03`.
- The ring is drawn with `outline`. No focusable or interactive element carries an outline at rest (`acc-03`). How a `box-shadow` ring pairs with the outline is set in that row of the [rule catalog](rule-catalog.md).
- The ring appears at once. It is never animated or faded in.
- The ring targets SC 2.4.7 and SC 1.4.11 (`acc-03`). The skill makes no claim to the focus-appearance area of SC 2.4.13.

## 3. Hit area

Every pointer target meets the WCAG floor of `tgt-01`. A stand-alone target also meets the stricter house hit area of `tgt-04`. Both sizes, the spacing test, what counts as the hit area, and the `tgt-04` scope and exemptions live in those rows of the [rule catalog](rule-catalog.md). Below, `H` is the `tgt-04` size for the pointer in use: the fine-pointer size, or the coarse size under `(pointer: coarse)`.

A target that `tgt-04` exempts takes no `::after` extension. A link inside running text is one: an extension would cover the lines above and below it. It still meets `tgt-01`.

A control that looks small keeps its look and gains an invisible `::after`, positioned absolutely inside a parent set to `position: relative`. Derive the inset per control and per axis. For a control `s` px tall, the block inset is `min(0px, (s - H) / 2)`, with each `H` written as its own declaration inside its pointer query. The inline inset follows the same formula with the control's width. A control already `H` or larger in an axis takes no inset in that axis.

Native checkboxes and radios are replaced elements and take no `::after`. Their hit area comes from the associated `<label>`, sized to `H` in both axes, or from a wrapping element that carries the `::after`. A click on the label activates the input, so the label counts as the target. A text input, textarea, or select renders no `::after` either; section 5 gives its route. A range input counts its own box alone (`tgt-04`): its box stands at least `H` in the cross axis, with the track and thumb styled through their pseudo-elements.

Expanded areas MUST NOT overlap. The gap between two neighboring controls is at least the sum of their two extensions. On a `scope: app` screen, a dense row or toolbar where full-size areas would overlap shrinks the extensions until they meet. The `tgt-04` row holds the guard a waiver for that region meets.

## 4. Buttons and hierarchy

**Recipe.** `display: inline-flex` with a `gap` for the icon. `white-space: nowrap`. `transition` names only `background-color` and `transform`. A 1px shift when pressed. The ring from section 2. Disabled and loading as in section 1. Every `<button>` states its `type`. A button acts on `click`, which fires on release, never on `pointerdown` or `mousedown`, so a press dragged off the button does nothing (`acc-26`). The quiet secondary is transparent, with a border in the `field-edge` token, never the hairline rule color. Its visible label identifies it, so `acc-01` asks no boundary contrast of that border; the `field-edge` token keeps the outline in view anyway.

**Hierarchy.**

- A page has one filled primary action, and each dialog has its own. The same action, with the same label and target, repeated lower on the page counts once (`lay-06.a`).
- Two filled buttons never sit side by side (`lay-06.a`).
- The filled primary uses one recipe across the page (`lay-06.b`).
- Secondaries are outlined or text-only and never louder than the primary. Nav actions are quieter than hero actions.
- Delete takes secondary styling unless it is the only action on the page.
- Two button sizes at most, at least 6px apart in height.

| Context | Control height | Field height | Hit area |
|---------|----------------|--------------|----------|
| Marketing page | 44 to 52px | 48 to 52px | the control itself, at `H` or larger. Under `(pointer: coarse)`, a control shorter than the coarse `H` adds the `::after` extension from section 3 (`tgt-04`) |
| App screen | 32 to 40px | 36 to 40px | `H` under either pointer (`tgt-04`): a control through the `::after` extension from section 3, a field through the route in section 5 |

The field-height column sets the range of the `field-height` token in each context. The token's default value lives in the [`DESIGN.md` template](design-md-template.md), "Reference scale".

Button labels and main nav links MUST stay on one line at every width in the supported range ([pre-delivery checklist](pre-delivery-checklist.md), section 1). Footer links and breadcrumbs SHOULD stay on one line. A footer link or breadcrumb with no shorter form wraps to two lines at most. A tab row stays on one line; when its tabs overflow, the row scrolls sideways.

Under the text-spacing overrides that the `acc-14` row sets, a `nowrap` label still fits, or its row reflows. It never clips or overlaps.

An `aria-label` on a control that shows visible text contains that visible text (`acc-06`).

## 5. Fields

Text inputs, textareas, selects, and comboboxes take the states the `lay-02` row sets for a field. The table gives the look of each one; loading and success apply only when that row asks for them. Fields keep one border width in every state. A state changes the background, border color, outline, or shadow. Border width, padding, and height are never animated, so nothing jitters.

| State | Look |
|-------|------|
| Default | A `rule-hair` border in the `field-edge` color, on paper. |
| Hover | One step raised background. |
| Focus-visible | Inset ring from section 2; the border MAY darken. |
| Filled | Same as default, value in ink. |
| Disabled | As section 1. |
| Error | Error-colored border, error icon, message in the helper line. |
| Success | Only after a real check. Cleared on the next edit. |
| Loading | Spinner in the inline-end zone. The field stays editable. |

- Field edges use the `field-edge` token. The edge is the only cue that identifies a field, so it meets the `acc-01` non-text contrast against paper. The hairline rule color never does, so a field never borrows it.
- A field shows no outline at rest. `:focus-visible` sets the solid 2px outline at offset -2px; a field that also draws a `box-shadow` ring sets a transparent outline beside it. Forced-colors mode then still shows the focus (`acc-03`).
- A field and the button beside it share one height, the `field-height` token, inside the field-height range of section 4. An app field reaches `tgt-04` through its `<label>` sized to `H` or through a wrapping element that carries the `::after` of section 3; a text input, textarea, or select renders no `::after`. The field border is `rule-hair` wide, and vertical padding is `calc((var(--field-height) - 1lh - 2 * var(--rule-hair)) / 2)`. The rendered height then equals the token, and every part derives from tokens (`tok-01`).
- Keep an inline-end zone of `space-6`, set with `padding-inline-end`, for the clear, error, or spinner icon.
- The label sits `space-2` to `space-3` above the field. Helper text sits `space-2` below, in a line reserved with `min-height: 1lh` (`prf-01`). An error replaces the helper text; it never adds a line.
- Field text is `text-base` or larger on mobile, so the browser does not zoom on focus.
- Every field has a `name`, an `autocomplete` value, a fitting `type` and `inputmode`, and a persistent visible `<label>` tied to it by `for` and `id` or by wrapping it (`frm-01`). A field that asks for information about the user names its purpose with the matching `autocomplete` token, such as `email` or `postal-code` (`acc-22`).
- A single-field form is `width: min(20rem, 100%)`. The input and the button never share one border.

## 6. Form behavior

- Every field has a visible `<label>` above it, tied to the field by `for` and `id` or by wrapping it. Checkboxes, radios, and switches carry it beside the input (`frm-01`). A placeholder never replaces a label, and it never carries the only format hint. A format, such as `12 Mar 2026`, goes in the persistent helper line (`frm-01`). A placeholder MAY repeat it, never an instruction.
- Validation timing follows section 11, "Validation".
- Focus alone changes nothing on the page. A changed value opens no page, submits no form, and moves no focus, unless text beside the field says so first (`acc-25`).
- An error says what failed, why, and how to fix it. It is linked to the field with `aria-describedby` and sets `aria-invalid` (`frm-02`).
- A required field carries the native `required` attribute and a visible word, not a lone asterisk. When custom messages replace the browser's, the form sets `novalidate`. `aria-required="true"` is for custom widgets only (`acc-05`).
- A value the user already entered in the same process is filled in or offered for selection on a later step. The form never asks for it again (`acc-19`).
- A sign-in or sign-up step sets no puzzle, recall, or transcription test without an alternative step or a help mechanism. Credential fields carry their `autocomplete` value (`username`, `current-password`, `new-password`, `one-time-code`), and no field blocks paste, so password managers work (`acc-20`).
- Submit stays enabled until the request starts, except on a form with no endpoint ([copy and honesty](copy-and-honesty.md), section 14). While the request is in flight, submit carries `aria-disabled="true"` and script ignores repeat activations; the native `disabled` attribute serves the no-endpoint form only. A failed submit keeps the typed input and moves focus to the first invalid field (`frm-02`).

## 7. Native-first controls

Native elements come with keyboard and screen-reader support built in (`acc-05`).

- **Textarea.** Vertical resize only, with a minimum height of `6rem`.
- **Select.** Keep the native element and draw the chevron on a wrapper. A fully custom select is allowed only if it matches the native one for keyboard and screen-reader use.
- **Checkbox and radio.** Use the native inputs, styled with `accent-color` and CSS state. Script never toggles them. A switch follows the checkbox contract.
- **Range.** The thumb takes focus, and the input's own box meets `tgt-04` as section 3 sets.
- **File input.** Styled through its `<label>`.
- **Combobox.** The listbox opens downward over content without pushing it, reflects `aria-expanded`, cycles with the arrow keys, confirms with Enter, and closes with Escape.
- **Segmented choice.** Radio inputs stay in document flow at 1px size, so a click never jumps the scroll. The adjacent label shows the checked state and the focus ring, and it measures at least `H` in both axes (`tgt-04`). It uses the body face and sentence case.
- **Horizontal scroller.** A grid with `grid-auto-flow: column`, columns of `minmax(16rem, 22%)`, and scroll snapping. Its padding equals the gutter, so the next item is visibly cut at the edge. It sets `overscroll-behavior-x: contain`. It takes `tabindex="0"`, `role="region"`, and an `aria-label` or `aria-labelledby`, so arrow keys scroll it and screen readers name it. It shows the focus ring.
- **Tab switcher.** A `role="tablist"` where arrow keys update `aria-selected`, `tabindex`, and the `hidden` attribute. Without script, every panel shows one after another (`prf-02`). A pinned visual column beside it uses `position: sticky` and is released below 60rem. Layout detail lives in [layout and composition](layout-and-composition.md).

## 8. Page-level access

- **Skip link.** The first focusable element moves focus to `<main>` (`acc-21`, which marks the skip link Beyond WCAG). It stays off-screen until focused, then shows above the page on the `z-tip` layer, `z-index: var(--z-tip)`.
- **Decorative graphics.** Every ornamental SVG, canvas, or CSS drawing is either `aria-hidden="true"` or labeled. Image alternatives follow [imagery and data](imagery-and-data.md).
- **Keyboard.** Everything works by keyboard, in reading order, with no trap (`acc-04`). Nothing is reachable by hover alone (`acc-15`).
- **Gestures.** An action done with a swipe, a pinch, or another path-based or multipoint gesture also works with a single tap or click (`tgt-02`).

## 9. Overlays

**Modal dialog.**

- Use the native `<dialog>` opened with `showModal()`. It brings a focus trap, Escape, and a backdrop.
- When custom positioning is added, keep the dialog centered: `position: fixed; inset: 0; margin: auto; max-height: min(85dvh, 42rem); height: fit-content`. Without these lines it can snap into a corner.
- Everything behind it is inert. It closes on Escape, on a backdrop click, and through a visible close button. The backdrop click comes from `closedby="any"` where the browser supports it. Elsewhere, a click handler on the dialog closes it when `event.target === dialog`.
- While it is open, a status message or toast about its work renders inside the dialog, since everything outside is inert (`acc-10`).
- Set `autofocus` on the first field, or on the least destructive action in a confirmation. Without it, `showModal()` focuses the first focusable element, which is the close button in many dialogs. A dialog of long text focuses its heading, which carries `tabindex="-1"`. On close, focus returns to the trigger (`acc-04`).
- An overlay that is not a dialog is centered with a fixed grid container.

**Popovers, menus, tooltips.**

- Use the native Popover API for light dismissal, stacking, and Escape.
- Position with CSS anchor positioning where supported, otherwise with fixed coordinates from the trigger's `getBoundingClientRect()`.
- Flip when within 16px of a viewport edge.
- Never nest one inside an ancestor that clips overflow.

## 10. Undo, loading, and empty

- **Undo before confirm.** A reversible action happens at once and offers undo in a toast. Undo stays available while that toast is visible, and the toast stays until the user dismisses it (section 11, `acc-17`). An irreversible action, such as deleting an account or dropping a table, keeps a confirmation step (`acc-30`). That step asks the user to type the name of what will be destroyed. The confirmation field has a visible label and accepts paste.
- **Loading.** Use skeletons when the incoming content has a predictable shape: lists, cards, tables. Spinners appear only inside controls, beside the label, as section 1 describes. Reserve the space either way (`prf-01`).
- **Empty.** Three lines: what is absent, why it matters, and one action. Never a bare "No results".
- **Disabled in view.** A disabled control where the user is looking says why it is disabled.

## 11. Microinteractions

Duration tokens are defined in section 13.3.

- **Button.** Hover is one color change. Press shifts 1px down until the pointer lifts. The focus ring follows section 2.
- **Input.** The focus ring follows section 2; the border MAY darken without changing width. The label stays above the field. Do not use a floating label that starts as a placeholder.
- **Validation.** A field validates on blur once the user has touched it, then on each keystroke, and never on the first keystroke. The error swaps into the reserved helper line (`prf-01`).
- **Toast.** One corner, with `role="status"`, or `role="alert"` for an error (`acc-10`). It never takes focus, and it never covers a focused element (`acc-13`). The toast region is a named landmark, such as `<section aria-label="Notifications">`, or a stated shortcut moves focus to it, so the keyboard can reach it. Stacks in one direction without displacing anything. Enters over `long`, or over `short` on an app screen.
- **Toast lifetime.** A toast that carries an action, such as undo or retry, stays until dismissed. An information toast whose message exists nowhere else also stays until dismissed, unless the message also lands in a persistent place such as a status line or a history list (`acc-17`). An information toast whose message persists elsewhere lingers 4 to 6 seconds. Every toast pauses while hovered or focused, and exits at 65% of the entrance time. An error toast carries one retry and never dismisses itself. While a modal is open, the toast renders inside the dialog (`acc-10`).
- **Modal.** The backdrop fades while the panel scales from 0.96 to 1 over `long`, or over `short` on an app screen, with ease-out. It closes faster, ease-in.
- **Menu.** Opens over `short` and closes faster. Up to 8 items MAY stagger by 30ms, never on an app screen. Flips within 16px of an edge.
- **Tooltip.** On hover it waits 800 to 1000ms, then fades in over `short`. On keyboard focus it appears at once, with no delay and no fade. Moving the pointer onto the tooltip keeps it open, and Escape closes it. It stays open until the pointer and focus leave or Escape is pressed, and it never times out (`acc-15`). The hover delay SHOULD exceed the focus delay, which is zero.
- **Tabs.** The indicator moves with `translateX` and `scaleX`, never by animating `width`. The outgoing panel fades over `micro` before the next appears.
- **Accordion.** Animate `grid-template-rows` from `0fr` to `1fr`, never `height`.
- **Number tick-up.** Only real figures. On data load, run 400 to 800ms from the prior value (from zero the first time), ease-out on the number, locale-formatted. The motion character of section 13.4 never scales this range. Assistive technology hears only the end value, through a polite live region (`acc-10`). Under reduced motion the end value shows at once.
- **Copy to clipboard.** The label changes to a confirmation word for 2.5 seconds, and the same word goes to a polite live region (`acc-10`). No toast.
- **Drag to reorder.** The handle shows on hover or focus, and the cursor goes from `grab` to `grabbing`. A half-opacity copy of the row tracks the pointer. A 1px accent rule shows where it will land. On release the item snaps into place over `short`, with no spring. Beside the handle, Move up and Move down buttons, or a row menu with a position choice, make the same move by single clicks or taps (`tgt-03`, WCAG 2.5.7). Arrow keys also move a focused row, and a live region announces each move. The keyboard path adds to the pointer path and never replaces it.
- **Live search.** Query 250ms after the last keystroke. Until results arrive, a spinner shows in the field's inline-end zone of `space-6`, set with `padding-inline-end` (section 5), and a polite live region says "Searching" (`acc-10`). The border MAY also sit one step darker beside the spinner, never the only cue (`acc-02`). Matches are wrapped in `<mark>`. The match count is announced once typing pauses, not on each key.
- **Command palette.** Cmd-K on macOS, Ctrl-K elsewhere, opens it with no delay. A `/` shortcut MAY also open it, when it fires only while focus is outside a text field and a setting can turn it off (`acc-12`). The input keeps focus throughout. A highlight slides between rows with `transform` over `micro`, and the rows themselves stay still. Enter chooses; Escape dismisses. The first opening MAY fade the rows in. Filtering never animates rows.

## 12. Feedback honesty

- **Silent success.** When the outcome is already visible, there is no toast. Toasts are for errors and for outcomes the interface cannot show.
- **Optimistic update.** Change the UI at once and send the request in the background, silent on success. On failure, revert over `short`. Then raise an error toast with a retry that stays until the user responds.

## 13. Motion

### 13.1 Motion needs a job

Each animation clarifies, directs attention, or confirms. Ask what an instant change would lose. If the answer is nothing, delete the animation. Default to the still version; generated pages carry more motion than they need.

### 13.2 Properties and easing

- Animate `transform` and `opacity`. Blur and other filters, `box-shadow`, `mask`, and `clip-path` are acceptable only when they render smoothly on that element alone.
- Banned: `transition: all`, and animation of layout properties such as `width`, `height`, `top`, and `left` (`mot-00.13.2`). Animating `margin` or `padding` is flagged unless the outer height stays constant.
- One layout animation is permitted: `grid-template-rows` from `0fr` to `1fr` on a disclosure panel, as the accordion in section 11 uses. It collapses the panel to its content height with no height measured in script.
- Arrivals decelerate (`ease-out`). Departures accelerate (`ease-in`). Two-way toggles use `ease-in-out`. The browser's default `ease` is not used. `linear` is kept for progress bars and scrubbing.
- UI state never bounces or overshoots. A playful direction MAY use a spring on its main action and one moment of character, under a waiver line that meets the material guard (`scl-00.genre-registers`), with the device named in `declared:`.

The curves follow one rule. `ease-out` spends most of its change early and lands without overshoot. `ease-in` is `ease-out` played backward: swap the two control points and subtract each value from 1. `ease-in-out` is symmetric about its midpoint.

| Token | Curve |
|-------|-------|
| `ease-out` | `cubic-bezier(0.2, 0.8, 0.25, 1)` |
| `ease-in` | `cubic-bezier(0.75, 0, 0.8, 0.2)` |
| `ease-in-out` | `cubic-bezier(0.6, 0, 0.4, 1)` |

### 13.3 Durations and stagger

| Token | Value | Use |
|-------|-------|-----|
| `micro` | 120ms | presses, ticks, color changes |
| `short` | 220ms | hover, tooltips, menus |
| `long` | 420ms | modals, drawers, accordions, reveals |

- An exit lasts 60 to 75% of its entrance.
- Stagger rows 30 to 50ms apart and blocks 60 to 100ms apart. Total stagger is 500ms at most, played once.
- A page-load reveal holds the tighter total in section 13.6.
- App screens use `micro` and `short` only, never in sequence ([surface classes](surface-classes.md)). Toasts and modals follow the same limit there (section 11).

### 13.4 Motion character

The genre sets a default character: read it from the Character column of the Dials table in [surface classes](surface-classes.md). The value is one of still, severe, brisk, or calm. The direction's Motion line MAY name another, and `DESIGN.md` carries it when one exists. The character scales every duration token.

| Character | Feel | Scale |
|-----------|------|-------|
| Still | Nothing moves. A typing caret MAY blink; it stops blinking before the `acc-11` time limit has passed since it started, then holds solid. | no motion |
| Severe | Quick and snapping. No spring. | x0.7 to 0.75 |
| Brisk | Technical, like an instrument. | x0.85 to 0.9 |
| Calm | Gentle. | x1.0 to 1.3 |

### 13.5 Primitive budget

A page uses three motion primitives at most. A typical set is a reveal, a hover cue, and one working loop like a counter or a marquee. A marquee follows the loop rules in section 13.8. A still character uses functional state changes only.

### 13.6 One page-load reveal

- A page has one entrance choreography at most (`mot-01.a`). It is staggered in document order through an index custom property and runs once. Its total, the last item's delay plus that item's scaled duration, is 800ms or less. There is no floor, so a single item at a severe or brisk scale passes. The stagger ceiling comes from that 800ms limit alone: the last delay is 800ms minus the last item's scaled duration. With `long` at x1.0 that leaves 380ms or less; at x1.3, 254ms or less. The 500ms stagger cap of section 13.3 still holds. On the hero, that total grades under `hro-00.8`. It runs only when the theme allows motion; a still character skips it.
- Trigger it with `IntersectionObserver`. Use a passive, throttled scroll listener only when scroll direction matters.
- Content shows with script off (`prf-02`). Hide elements only under a class that script adds. Otherwise animate from a visible state with a self-running CSS animation or `@starting-style`. Content that is hidden at rest and needs script to appear fails `prf-02`.
- Under reduced motion the reveal shows its end state at once, with no delay, and screenshots are taken that way.

### 13.7 Reduced motion is a state

Every motion recipe states its reduced-motion form (`acc-08`). Spatial movement that answers a user action becomes an opacity crossfade of 150ms or less. That element carries `.motion-essential`, so the global rule below leaves it alone, and `.motion-crossfade`, which sets its reduced form. A page-load reveal shows its end state at once (section 13.6). Functional state changes still happen. One global rule neutralizes the rest. It zeroes the delays too, so a staggered reveal with a backwards fill does not sit invisible for the length of its stagger:

```css
@media (prefers-reduced-motion: reduce) {
  *:not(.motion-essential, .motion-essential *),
  *:not(.motion-essential, .motion-essential *)::before,
  *:not(.motion-essential, .motion-essential *)::after {
    animation-delay: 0s !important;
    transition-delay: 0s !important;
    animation-duration: 1ms !important;
    transition-duration: 1ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
  }
}
```

Essential motion, such as a loader or a fade of 150ms or less, opts out with `.motion-essential`. The global rule skips those elements and their descendants, so each one writes its own reduced form in the same query. A crossfade element also carries `.motion-crossfade`. That class limits transitions to opacity and cancels keyframe animations, so a transform jumps to its end value with no travel. The `min()` holds the fade at 150ms even when the character scale of section 13.4 lengthens `micro`:

```css
@media (prefers-reduced-motion: reduce) {
  .motion-crossfade {
    animation-name: none;
    transition-property: opacity;
    transition-duration: min(var(--micro), 150ms);
    transition-timing-function: var(--ease-out);
  }
}
```

The rule never sets `transform: none`. No hidden or positioned state, such as a closed drawer or a tab indicator, depends on a transform the reduced form removes. A loader carries `.motion-essential` alone and keeps its rotation. The crossfade rule never touches it.

### 13.8 Forbidden devices and loops

These MUST NOT appear (`mot-00.13.8`):

- Parallax.
- Custom cursors or cursor followers.
- A marquee that keeps moving on hover or focus.
- `will-change` applied across a class.
- Pulsing dots.
- A caret that still blinks past the `acc-11` time limit.
- An infinite loop. Four exceptions exist: a loader; one marquee; one small loop whose cycle is 4 seconds or less; and one ambient loop whose cycle is 8 seconds or more. Every exception except the loader meets the `acc-11` conditions below.

Motion that starts on its own and runs past the `acc-11` time limit in total follows that row. The total counts every repeat, so any loop that repeats past the limit qualifies, whatever its cycle length. Examples are marquees, small and ambient loops, and videos that loop. Only a loader is exempt, while its load runs. Such motion waits for script before it starts. It halts when it leaves the viewport, and it does not run under reduced motion. It pauses while the pointer or focus is on it. A visible play and pause button controls it, which is what SC 2.2.2 asks for; without script or under reduced motion, that button is hidden. Content that rotates on its own with no pause control fails `acc-11` through SC 2.2.2. Content that keeps rotating under hover or focus fails `acc-11` through the house extension the row marks Beyond WCAG. Content that updates on its own beside other content, such as a ticker, a feed, or a refreshing score, carries the control the `acc-11` row asks for.

Nothing on the page flashes past the `acc-16` limit, and the skill does not use the below-threshold exception. A blink, a strobe, or a fast color swap counts as a flash.

### 13.9 Hover discipline

- One hover cue per element, and it raises contrast: a color step, or for a control whose color is fixed, a 1px lift over `micro`.
- The cue sits on the wrapping link or card, not on its image. Images never zoom or spin on hover (`img-00.10`).
- Elements that do nothing do not respond (`mot-01.b`). The same lift on every card is flagged (`mot-00.13.9`). It does not fire on a playful page when every lifted card is a link.
- Every hover affordance also responds to focus (`acc-15`).

### 13.10 Scroll-linked motion

Off by default. A page MAY carry one scroll pattern, and it counts toward the primitive budget. A second scroll-driven pattern on the same page fires `mot-01.c`.

- It applies to structure: a pinned section, one display element, a slim progress line, or figures. Never to prose.
- It never replaces the load reveal, and no element gets both.
- Base CSS shows the finished layout. The effect is wrapped in two guards: a `@supports (animation-timeline: view())` block, and a media query that requires `prefers-reduced-motion: no-preference` and a minimum width. Pinned steps and the sticky diptych require `not (width < 60rem)`. The headline wipe and the progress spine require `not (width < 40rem)`.
- Declare `animation-timeline` and `animation-range` after the `animation` shorthand, which resets them. Scrubbing uses `linear`.

| Pattern | Recipe |
|---------|--------|
| Pinned steps | A track of 280svh defines a named `view-timeline`. Inside, a sticky pane holds a heading and an ordered list; its top offset clears any banner plus spacing. Step text rests in a token color that meets the `acc-01` text contrast against the pane and shifts to ink as its step arrives. Non-text marks that carry meaning meet the `acc-01` non-text contrast at rest. A mark that brightens from opacity 0.2 falls short of it, so it is decorative and its meaning is also in text. Each step rises from an 8px offset over `contain` 5 to 30%, 30 to 55%, and 55 to 80%. A stuck pane cannot drive its own view timelines, so the track supplies one. |
| Headline wipe | One statement heading mid-page, never the hero `h1`. `clip-path` from `inset(0 100% 0 0)` with `translateX(-0.25em)`, scrubbed by its own view timeline from `entry 20%` to `cover 45%`. |
| Progress spine | A fixed 2px vertical rule at `inset-inline-start: max(1rem, 2vw)`, so a right-to-left page puts it on the right. Its accent fill, one of the accent's signal uses in [color and surfaces](color-and-surfaces.md), section 2, scales on `scaleY` with root scroll progress, `linear`. Shown only under `not (width < 40rem)`. |
| Sticky diptych | Two columns, `minmax(0, 5fr)` and `minmax(0, 7fr)`. One stays pinned under the nav. The other scrolls large 16:10 figures, each at least 440px tall, fading from opacity 0.3 and lifting from 12px over `entry 0%` to `60%`. One static column below 60rem. |

**Fallback.** Script can run where scroll timelines are unsupported. The only fallback then is one `IntersectionObserver` reveal with `rootMargin: "0px 0px -20% 0px"`, over `long` with `ease-out`, run once. No scroll listeners, no polyfills. Elements are hidden for the reveal only under a class the script adds, so a page without script shows everything (`prf-02`).
