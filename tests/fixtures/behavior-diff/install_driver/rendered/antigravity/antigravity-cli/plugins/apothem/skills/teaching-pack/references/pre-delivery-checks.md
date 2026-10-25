<!-- SPDX-License-Identifier: MIT -->

# Pre-delivery checks

Run every check, repair what fails, and report each as pass, fail, or not checked
with the reason. A check that was not run is never reported as passed.

## 1. Basis

- The access basis is stated, and every section not opened is listed as `not read`.
- No part draws on a section marked `not read`.

## 2. Markers

- Every teaching line, walk-through step, example step, key line, and glossary entry
  carries exactly one marker.
- When the pack is a file, Grep it for content lines that carry none of the three
  markers (skipping headings, question stems, table header rows, and the pack header);
  the count must be zero.
- `[not in source]` appears nowhere except glossary glosses and prerequisite lines.

## 3. Locators, reopened rather than recalled

- Reopen the source at one locator per part, and at every locator that supports a
  number, a formula, or a quotation. Confirm the cited place says what the line says.
- Copy each formula and each figure from the source rather than from the draft, and
  compare them symbol by symbol and digit by digit.
- A locator that cannot be found in the source map is removed or replaced with a seen
  one. If the check would have passed whichever section was cited, it did not test
  anything; reopen the section.

## 4. Coverage

- Every source section is in a module, listed as `thin`, or listed under `skipped` with
  the reason; none is dropped silently.
- Every goal has a curriculum module, a quiz item, and, where a formula or algorithm
  is involved, a walk-through.
- Every quiz item names a goal, and every key line cites a locator.
- Every formula or algorithm taught has an example, or is listed under `skipped`
  with the reason.

## 5. Examples

- The arithmetic status is labelled on every example.
- Each hand-computed example is recomputed by a second route, for instance a
  different order of operations or by substituting the result back; the second
  route's outcome is noted. An example whose two routes disagree is repaired
  before delivery.
- Machine-checked examples name the calculation that was run and quote its output.

## 6. Thin parts

- Each absent part has a thin notice that states what the part needed and what the
  source offered.
- No thin part was followed by a shortened version built from outside knowledge.
- The number of `[not in source]` glossary entries is reported.

## 7. Voice and reproduction

- Claims are attributed to the document ('the authors show'), not stated as fact.
- Each symbol is defined before it is used, in the walk-through or the glossary.
- Text is paraphrased unless the exact wording is the point; quotations are marked,
  carry a locator, number at most one per section, and each is under fifteen words
  (see `rules/authoritative-referencing-quotation.md`).
- No figure, table, or long passage is reproduced.

## 8. Slides

- Under `--slides`, the outline exists, its question slides carry no answers, and
  the hand-off result is recorded.
- Without `--slides`, no outline was written.
