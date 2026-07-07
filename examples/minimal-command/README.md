<!-- SPDX-License-Identifier: MIT -->

# minimal-command

The smallest viable slash-command definition.

## What it demonstrates

- A flat command-definition file with the canonical sections (Role, Instructions, Inputs, Workflow, Output, Critical rules).
- The required frontmatter fields per [`command.schema.json`](../../src/apothem/schemas/command.schema.json): `name`, `version`, `updated`, `description`, `argument-hint`, `disable-model-invocation`, `portability`, `allowed-tools`.
- An empty Inputs table (the command takes no arguments).

## How to use it

1. Copy `sample-command.md` to `src/apothem/commands/<your-command>.md` in your apothem checkout (the active harness adapter materializes it into the harness's native config location on install / sync). The filename (without `.md`) becomes the slash-command name.
2. Update the `name` and `description` frontmatter fields.
3. Replace the body sections with your command's actual specification.
4. Invoke from any session via `/<your-command>`.

## Expected effect

Invoking `/hello` returns the canonical greeting line and confirms the slash-command-loading pipeline is operational.

## Layout

```text
minimal-command/
├── sample-command.md   ← command definition with frontmatter
└── README.md           ← this file
```
