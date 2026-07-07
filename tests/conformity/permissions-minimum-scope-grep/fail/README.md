<!-- SPDX-License-Identifier: MIT -->

<!--
  Fail fixtures for permissions-minimum-scope-grep.

  - ci.yml — no top-level `permissions:` block; the workflow silently
    inherits the default-broad GitHub Actions permissions surface
    (drift class: missing-top-level-permissions-block).
  - release.yml — declares `permissions: write-all`, re-installing the
    over-scoped default as an explicit grant (drift class:
    overscoped-permission).
-->
