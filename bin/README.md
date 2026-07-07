<!-- SPDX-License-Identifier: MIT -->

# bin/

The npm launcher for the apothem CLI.

## Contents

| File | Purpose |
| --- | --- |
| `apothem.mjs` | Node shim behind the package's `bin` entry. Locates a Python 3.10+ interpreter, wires `PYTHONPATH` to the self-contained source tree (vendored dependencies first, then the engine), verifies the `click` and `rich` prerequisites, and executes `python -m apothem` with the caller's arguments. |

## How it is consumed

The root `package.json` maps the `apothem` command to `bin/apothem.mjs`, so
`npx @ahmed-g-gad/apothem <command>` (or `npx github:ahmed-g-gad/apothem`)
runs the bundled engine without any package installation beyond the npm
fetch itself.

## Conventions

- Node 18+ syntax, ES modules only (`.mjs`).
- The shim stays dependency-free: only `node:` built-ins.
- Interpreter probing order: `APOTHEM_PYTHON`, `python3`, `python`, `py -3`.
- Exit codes mirror the engine's exit codes; shim-level failures exit 1
  with a single actionable message on stderr.

## Working in this folder

- The interpreter probe and the missing-dependency message mirror
  `scripts/installer/install.sh`. When one side changes, change both in the
  same change-set so the shim and the installer stay in lockstep.
- The `bin` mapping lives in the root `package.json`. Renaming `apothem.mjs`
  requires updating that mapping and the npm `files` allowlist together.
- There is no Node test harness in this repository — shim behavior is
  exercised indirectly through the engine's CLI tests. Validate changes with
  `node bin/apothem.mjs --version`.
