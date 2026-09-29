<!-- SPDX-License-Identifier: MIT -->

# CI Workflows

GitHub Actions workflow definitions for the `apothem` repository. Each `.yml`
file here is a self-contained workflow; its own top-of-file comment header is
the authoritative description of what it does and why. This README is the folder
index — it maps each workflow to its triggers and one-line purpose, and records
the conventions every file in this folder follows. A subfolder `README.md` does
not override the repository's branded root `README.md` on GitHub; only a
top-level `.github/README.md` would, and none exists.

## Workflows

| Workflow | Triggers | Purpose |
|----------|----------|---------|
| `ci.yml` | push (main), PR (main), dispatch | Ten canonical check classes — lint, format-check, type-check, test matrix, coverage, security-scan, supply-chain-scan, docs-build, example-run, release-preflight. |
| `ci-matrix.yml` | push (main), PR (main), dispatch | Cross-platform 3-OS × 5-Python `pytest` matrix (adds macOS reach) via the in-repo reusable setup workflow. |
| `ci-docs-stub.yml` | PR (main) | Documentation-only PR stub that reports the required `quality` / `coverage` contexts green; self-gates and fails if a gated code/config surface is present. |
| `clean-install-gate.yml` | push (main), PR (main), dispatch | Clean-machine install gate — one-shot installer shell-compat across documented shells, plus a hermetic clean-runner install and built-wheel smoke. |
| `harness-matrix.yml` | push (main), PR (main), dispatch | Per-harness install + verify matrix fanning across all 17 registered adapters (build wheel → install → verify → uninstall in a sandbox home). |
| `conformity.yml` | push (main), PR (main), schedule (weekly), dispatch | Outward-conformity fixture sweep in strict mode over the user-scope ecosystem tree; fails on any per-fixture per-mandate `fail` cell. |
| `docs-drift.yml` | push (main), PR (main), dispatch | Documentation drift gate — forbids a root `docs/` tree and fails on any diff after regenerating the source-generated reference pages. |
| `codeql.yml` | push (main), PR (main), schedule (weekly), dispatch | CodeQL SAST over the Python source and the Actions workflows; uploads SARIF to the Security tab. |
| `zizmor.yml` | push (main), PR, dispatch | Static analysis of every workflow for template injection, credential persistence, unpinned actions, and excessive permissions; uploads SARIF. |
| `scorecard.yml` | push (main), schedule (weekly), dispatch, branch_protection_rule | OpenSSF Scorecard analysis; publishes to the OpenSSF API and uploads SARIF to the Security tab. |
| `dco.yml` | PR (main), dispatch | Developer Certificate of Origin enforcement — requires a `Signed-off-by` trailer on every PR commit. |
| `dependency-review.yml` | PR (main) | Blocks PRs that introduce dependencies with known vulnerabilities or disallowed licenses, evaluated against the manifest/lockfile diff. |
| `pip-audit.yml` | push (main), PR, schedule (weekly), dispatch | Weekly `pip-audit` CVE scan of the resolved dependencies, the frozen vendored closure, and the hash-locked release build tooling, plus a PR/push gate on changes to them. |
| `npm-audit.yml` | push (main), PR, schedule (weekly), dispatch | Weekly `npm audit` of the documentation site's dependency tree, plus a PR/push gate on `site/package.json` and its lockfile. Sibling of `pip-audit.yml`, whose path filters cover the Python surface only — without this the npm tree is unaudited. Fails on high/critical. |
| `license-audit.yml` | push (main), PR, schedule (weekly), dispatch | Scans the resolved dependency tree for copyleft or otherwise MIT-incompatible licenses; mirrors the dependency-review allow-list. |
| `badges.yml` | workflow_run (CI completed), dispatch | Generates the shields.io endpoint JSONs after CI completes and uploads them as the `badges` artifact for the static site to serve. |
| `release.yml` | push (tag `v*.*.*`) | Release orchestration — build sdist + wheel, SBOM, cosign signature, SLSA provenance, then publish the GitHub Release with every artifact attached. |
| `publish-npm.yml` | push (tag `v*.*.*`), dispatch | Publishes `@ahmed-g-gad/apothem` to registry.npmjs.org via npm trusted publishing (OIDC); gated on the `NPM_TRUSTED_PUBLISHING_READY` variable. |
| `publish-vscode.yml` | push (tag `v*.*.*`), dispatch | Packages the extension into a `.vsix` and publishes to the Visual Studio Marketplace; gated on the `VSCE_PAT` secret. |
| `publish-static-site.yml` | push (main), dispatch | Builds the Next.js + Fumadocs site, stages the canonical install scripts and badges, and deploys to apothem.ahmedgad.com via GitHub Pages. |
| `harness-convention-monitor.yml` | schedule (quarterly), dispatch | Enforces the 90-day freshness cadence on each adapter's `STANDARD-CONVENTION-PIN.md`; files a drift-alert issue when a pin is missing, malformed, future-dated, or stale. |
| `reusable-python-setup.yml` | workflow_call, dispatch | Reusable Python setup + dependency-install building block callers invoke via `uses: ./.github/workflows/reusable-python-setup.yml`; not a standalone gate. |

## Conventions

- **SHA-pinning.** Every action `uses:` reference is pinned by 40-character
  commit SHA followed by a `# vMAJOR.MINOR.PATCH` version comment. Renovate
  (`renovate.json`) proposes SHA bumps on a weekly schedule; a bump lands only
  when a maintainer merges it. One documented exception exists in `release.yml`:
  the SLSA reusable generator is trust-anchored on its per-tag attestation
  (Sigstore policy forbids SHA-pinning trusted reusable workflows), and that
  `uses:` line carries an `action-pinning-exempt:` marker.
- **Branch-protection required checks.** Three workflows declare, in their own
  headers, that a job is a `main` required status check: `ci.yml` (the
  `quality / <os> / py<ver>` matrix and `coverage`), `clean-install-gate.yml`,
  and `harness-matrix.yml` (`matrix (<name>)`). A required check is never gated
  by a `paths:` filter on its pull-request trigger — a skipped required check
  can never report and would silently gate nothing — which is why
  `clean-install-gate.yml` and the `harness-matrix.yml` pull-request trigger run
  on every PR to `main`, and `ci-docs-stub.yml` reports the required contexts
  green on a documentation-only PR that never runs the real jobs.
- **Least privilege.** Each workflow declares a `contents: read` baseline at the
  workflow scope; per-job overrides escalate a scope (`security-events: write`,
  `id-token: write`, `issues: write`, `pages: write`) only where a step needs
  it. No job uses write-all.
- **Runner hardening.** Every job's first step is `step-security/harden-runner`;
  jobs with a small, stable endpoint set (`dco.yml`, `dependency-review.yml`,
  `scorecard.yml`) set `egress-policy: block` with an explicit allowlist, and
  the rest run `audit`. `zizmor.yml` and `license-audit.yml` stay on `audit`
  because their endpoint sets are not stable enough to allowlist without
  false-failing the job.
- **Concurrency.** Each workflow declares a `concurrency` group keyed on the ref;
  release and publish workflows set `cancel-in-progress: false` so a
  publication run is never cancelled mid-flight, while gate and scan workflows
  cancel superseded runs.
- **Pip pin.** Workflows that install pip carry `env.PIP_PIN_VERSION` set to the
  single canonical value; `scripts/dev/check_pip_pin_drift.py` fails the build if
  any workflow's pin diverges.

## Working in this folder

To add or change a workflow: write the top-of-file comment header first (it is
the authoritative description), pin every new `uses:` reference by 40-character
SHA with a version comment, keep the `contents: read` baseline with justified
per-job escalation, and add a row to the table above. If the change adds,
renames, or removes a `main` required status check, keep the required-check set
and the `ci-docs-stub.yml` complement in lockstep —
`tests/scripts/test_required_check_coverage.py` asserts the stub's `paths-ignore`
is the exact complement of `ci.yml`'s trigger `paths`. Validate before handoff:

```bash
python -m apothem.conformity.gate --all .
python -m pytest tests/scripts/test_required_check_coverage.py
```

The `unpinned-action-grep` conformity matcher enforces the SHA-pinning policy;
`zizmor.yml` and `codeql.yml` audit these workflows in CI.
