<!-- SPDX-License-Identifier: MIT -->

# minimal-output-style

The smallest viable output-style definition.

## What it demonstrates

- The flat `.md` output-style convention — one file per style, kebab-case filename.
- The required frontmatter fields per [`output-style.schema.json`](../../src/apothem/schemas/output-style.schema.json): `name` and `description` (the schema admits `id`, `applies-to`, `version`, and `last-reviewed` as optional extensions; the shipped styles carry only the two required fields).
- A supplement-not-replacement body: a posture that layers on the `default.md` baseline without weakening any behavioral mandate, preserving every conformity-bearing marker.

## How to use it

1. Copy `sample-output-style.md` to `src/apothem/output-styles/<your-style>.md` in your apothem checkout (the active harness adapter materializes it into the harness's native config location on install / sync). The filename (without `.md`) is the kebab-case style id.
2. Update the `name` and `description` frontmatter fields.
3. Replace the posture body with your style's actual conventions, and register the new style in the output-styles index.
4. Select the style from any session via `/output-style`.

## Expected effect

Selecting the style applies its presentation register on top of the inherited baseline and confirms the output-style-loading pipeline is operational.

## Layout

```text
minimal-output-style/
├── sample-output-style.md   ← output-style definition with frontmatter
└── README.md                ← this file
```
