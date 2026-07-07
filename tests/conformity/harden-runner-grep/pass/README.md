<!-- SPDX-License-Identifier: MIT -->

# harden-runner-grep — PASS fixtures

Conformant workflow fixtures. Every job in `ci.yml` opens with
`step-security/harden-runner@v2` (pinned to `@v2.10` or the floating
`@v2` major) as `steps[0]`, with a `with:` block declaring
`egress-policy: block` or `egress-policy: audit` — both members of the
closed conformant taxonomy.

The validator (`src/apothem/conformity/harden_runner_grep.py`) MUST exit
0 against this directory's `.github/workflows/` overlay.
