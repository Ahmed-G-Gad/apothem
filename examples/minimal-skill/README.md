<!-- SPDX-License-Identifier: MIT -->

# minimal-skill

The smallest viable skill folder.

## What it demonstrates

- The folder-with-`SKILL.md` skill convention.
- The required frontmatter fields per [`skill.schema.json`](../../src/apothem/schemas/skill.schema.json): `name`, `version`, `updated`, `description`, `archetype`, `userInvocable`, `disable-model-invocation`, `allowed-tools` (with `argument-hint` optional).
- A three-section `SKILL.md` body: when to invoke, procedure, anti-patterns.

## How to use it

1. Copy this folder to `src/apothem/skills/<your-skill-name>/` in your apothem checkout (the active harness adapter materializes it into the harness's native config location on install / sync), renaming as appropriate.
2. Update the `name` and `description` frontmatter fields.
3. Replace the procedure with your skill's actual logic.
4. The skill is now available via the `Skill` tool when its detection signals match.

## Expected effect

Invoking the skill returns the canonical greeting line and confirms the skill-loading pipeline is operational.

## Layout

```text
minimal-skill/
├── SKILL.md      ← entry point with frontmatter
└── README.md     ← this file
```
