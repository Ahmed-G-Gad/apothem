<!-- SPDX-License-Identifier: MIT -->

<!--
  Conformant release-workflow fixtures for `oidc-trusted-publishing-grep`.

  - `publish-pypi.yml` declares `id-token: write`, pins
    `pypa/gh-action-pypi-publish@v1.12.4` (>= v1.10), and contains no
    `PYPI_API_TOKEN` reference.
  - `packaging-npm.yml` declares `id-token: write`, uses Node 24,
    pins npm CLI 11.5.1+, invokes `npm publish --access public`, and
    contains no `NPM_TOKEN` reference.

  These are the canonical OIDC trusted-publishing workflow shapes the
  matcher passes silently.
-->

# Pass fixtures — `oidc-trusted-publishing-grep`

The two YAML files in this directory model canonical conformant release
workflows. Running `oidc_trusted_publishing_grep`
against a project root whose `.github/workflows/` contains these
fixtures returns `passed: true` with zero findings.
