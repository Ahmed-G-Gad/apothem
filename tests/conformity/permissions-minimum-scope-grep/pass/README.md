<!-- SPDX-License-Identifier: MIT -->

<!--
  Pass fixtures for permissions-minimum-scope-grep.

  - ci.yml — minimum-scope `permissions: { contents: read }` block; the
    canonical least-privilege shape for a read-only test runner.
  - release.yml — `permissions: { contents: write, id-token: write }`
    paired with a `softprops/action-gh-release` step; the
    contents-write grant is justified by an observable push-style
    step so the undocumented-elevation advisory does not fire.
-->
