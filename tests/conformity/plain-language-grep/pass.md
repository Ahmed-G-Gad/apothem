<!-- SPDX-License-Identifier: MIT -->

# Apothem — Configuration Manager

Apothem reads a single shared profile and writes the native configuration
files each development tool expects. One source of truth, many destinations.
It is a host-agnostic harness configuration manager: one profile, many
harnesses, zero hand-maintained drift.

## What it does

Apothem manages your development-tool configuration the way a package
manager manages dependencies: declare what you want once, materialize it
everywhere it needs to go. When the upstream profile changes, every
managed surface refreshes in lockstep.

The shared profile carries cohort directories — `commands`, `rules`, `skills`, `hooks`, and `agents`. The installer writes the `agents/` directory
into each harness's native layout.

## Quick start

Run Apothem with `npx @ahmed-g-gad/apothem`, author your profile at
`~/.config/apothem/profile.yaml`, and run `apothem install` to write the
native configuration files.

```bash
apothem install
apothem verify
```

The verifier confirms every managed surface matches the profile. Drift is
reported with the exact file and line that diverged.

## Cross-references

See the [helpers overview](https://apothem.ahmedgad.com/reference/agents/) and the [reference page](https://apothem.ahmedgad.com/reference/agents/)
for the canonical inventory. Configuration knobs live in the
[host-agnostic posture](https://apothem.ahmedgad.com/concepts/ai-platform-agnosticism/) walkthrough.

[helpers]: https://apothem.ahmedgad.com/reference/agents/
[posture]: https://apothem.ahmedgad.com/concepts/ai-platform-agnosticism/ "Host-agnostic posture overview"
