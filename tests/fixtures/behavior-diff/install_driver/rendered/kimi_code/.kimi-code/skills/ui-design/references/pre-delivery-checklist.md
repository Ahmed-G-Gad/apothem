<!-- SPDX-License-Identifier: MIT -->

# Pre-Delivery Checklist

Reference for the [`ui-design`](../SKILL.md) skill. Complete it before calling an interface done. Mark each item pass, fail, or not checked; for not checked, state why (no browser, no device, no time). A fail is fixed or reported, never omitted. The Return Contract carries the results.

## How to check

Prefer measurement over judgement: compute contrast ratios from token values, read target sizes from the stylesheet or the rendered page, and tab through the page. If the host provides a browser tool, use it to see the page at the widths below; if it does not, say the visual checks were not run.

## 1. Accessibility

- [ ] Text contrast is 4.5:1 or better (3:1 for large text and interface boundaries) in every shipped theme.
- [ ] No meaning relies on colour alone.
- [ ] Tab order follows reading order; every control is reachable and operable by keyboard; no trap.
- [ ] Focus is visible on every interactive element and returns to the trigger when a dialog or menu closes.
- [ ] Every icon-only control has an accessible name; images have suitable alternative text.
- [ ] One page heading, an unbroken heading ladder, and landmarks present.
- [ ] The page is usable at 200 percent zoom and at 320 px width with no horizontal page scroll.

## 2. Targets and input

- [ ] Touch targets are 44 by 44 CSS px or larger, with 8 px between neighbours.
- [ ] Nothing essential depends on hover, gesture, or right click alone.
- [ ] Pressed, hover, and disabled states are distinct.

## 3. States and content

- [ ] Default, loading, empty, error, and success states exist for every data-driven region and were rendered.
- [ ] Real content lengths were tried: longest label, shortest label, a long unbroken string, zero items, many items.
- [ ] No placeholder text remains: no lorem ipsum, no "TODO", no sample names left in shipped copy.
- [ ] Error messages say what happened and what to do next.
- [ ] Destructive actions offer undo or name what will be lost.

## 4. Layout and performance

- [ ] Checked at 320, 768, and 1280 px widths with no overflow, clipped text, or overlap.
- [ ] Images and embeds have reserved dimensions; nothing moves after load.
- [ ] The first screen shows its main content without waiting on animation or a late request.
- [ ] No text is rendered inside images; images are sized and compressed for their display size.

## 5. Typography and colour

- [ ] Only tokens from `DESIGN.md` are used; each new token is recorded there.
- [ ] Body text is 16 px or larger; running text keeps a measure under about 75 characters.
- [ ] Light and dark themes both checked, if both ship.

## 6. Motion

- [ ] Every animation has a purpose, a duration in range, and an off path under the reduced-motion preference.
- [ ] Animations touch only transform and opacity, and nothing loops for more than 5 s without a pause control.

## 7. Forms

- [ ] Every field has a persistent visible label, the right input type, and an autocomplete token where one applies.
- [ ] Errors appear beside their field, in text, with the fix; focus moves to the first invalid field on submit.
- [ ] Typed input survives a failed submit.

## 8. Navigation and data

- [ ] The current location is marked; the way back is clear; shareable state is in the URL.
- [ ] Tables align numbers right, show units once, and remain readable on a narrow screen.
- [ ] Charts have labelled axes, a zero baseline for bars, and a non-colour cue per series.

## 9. Records

- [ ] `DESIGN.md` reflects the tokens, components, and decisions this change introduced.
- [ ] Local overrides of project defaults are commented at the override site and listed in the report.
- [ ] Any lookup that returned nothing is reported as "defaults used", not as a sourced value.
- [ ] Fonts and imagery have a recorded licence or are system or project-owned.
