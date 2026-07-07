<!-- SPDX-License-Identifier: MIT -->

<!--
  Drift fixtures for `oidc-trusted-publishing-grep`.

  - `publish-pypi.yml` omits the `id-token: write` permission, pins
    `pypa/gh-action-pypi-publish@v1.5.0` (below the v1.10 OIDC floor),
    and still references `secrets.PYPI_API_TOKEN`. Expected drift
    classes: `missing-id-token-permission`,
    `action-version-too-old`, `legacy-token-secret-reference`.
  - `packaging-npm.yml` omits the `id-token: write` permission,
    publishes on an obsolete Node runtime without the npm CLI 11.5.1+
    floor, and references `secrets.NPM_TOKEN`. Expected drift classes:
    `missing-id-token-permission`, `legacy-token-secret-reference`,
    `npm-runtime-too-old`, `npm-cli-floor-absent`.

  These are the canonical OIDC trusted-publishing drift shapes the
  matcher rejects with exit code 2.
-->

# Fail fixtures — `oidc-trusted-publishing-grep`

The two YAML files in this directory model release workflows that
have NOT been migrated to OIDC trusted publishing. Running
`oidc_trusted_publishing_grep` against a project root whose
`.github/workflows/` contains these fixtures returns `passed: false`
and lists every drift occurrence per the comment above.
