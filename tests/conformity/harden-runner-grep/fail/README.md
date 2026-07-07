<!-- SPDX-License-Identifier: MIT -->

# harden-runner-grep — FAIL fixtures

Non-conformant workflow fixtures exercising each drift class:

- `ci.yml` — job `not-first` places `actions/checkout@v4` ahead of
  `step-security/harden-runner@v2` (drift class
  `harden-runner-not-first-step`). Job `bad-policy` declares
  `egress-policy: log`, outside the closed `{block, audit}` taxonomy
  (drift class `egress-policy-too-permissive`).
- `release.yml` — workflow has zero `step-security/harden-runner` steps
  across its single job (drift class `harden-runner-action-absent`).

The validator MUST exit non-zero against this directory's
`.github/workflows/` overlay and report one finding per drift instance.
