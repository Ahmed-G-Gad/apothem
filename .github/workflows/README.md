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
| `ci.yml` | push (main), PR (main), dispatch | Eleven canonical check classes — lint, format-check, type-check, test matrix, coverage, security-scan, supply-chain-scan, docs-build, example-run, release-preflight, metrics (per-package coverage floors and the `metrics.json` artifact). Release-preflight also runs `scripts/dev/validate_harness_convention_pins.py`, so a stale pin blocks the merge. |
| `ci-matrix.yml` | push (main), PR (main), dispatch | Cross-platform 3-OS × 5-Python `pytest` matrix (adds macOS reach) via the in-repo reusable setup workflow. |
| `ci-docs-stub.yml` | PR (main) | Documentation-only PR stub that reports the required `quality` / `coverage` contexts green; self-gates and fails if a gated code/config surface is present. |
| `npm-shim.yml` | push (main), PR (main), dispatch | npm shim runtime-floor gate — runs `bin/apothem.mjs` on Node 18, 20, 22 and 24 with Python 3.10: the missing-prerequisite error, `--version`, an isolated dry-run install, and the packed tarball through `npx`. |
| `clean-install-gate.yml` | push (main), PR (main), dispatch | Clean-machine install gate — one-shot installer shell-compat across documented shells, plus a hermetic clean-runner install and built-wheel smoke. |
| `installer-lint.yml` | PR (main), dispatch | Runs the Static Site build's two installer lint commands on `scripts/installer/` for every PR: `shellcheck --severity=error` on the `.sh` scripts and `Invoke-ScriptAnalyzer` with `PSScriptAnalyzerSettings.psd1` on the `.ps1` scripts. A finding fails the PR instead of stopping the Pages deploy after merge. `tests/integration/test_installer_lint_workflow.py` keeps the two workflows' commands identical. |
| `channel-smoke.yml` | schedule (weekly), dispatch | Runs every documented install channel the way an anonymous new user would — clean runner, documented prerequisites only, isolated home, no credentials — via `scripts/dev/channel_smoke.py`. The harness CLIs install with `npm ci` from `.github/channel-smoke/package-lock.json`. Run it after a visibility change, a release, or an install-docs change. |
| `harness-matrix.yml` | push (main), PR (main), dispatch | Per-harness install + verify matrix fanning across all 17 registered adapters (build wheel → install → verify → uninstall in a sandbox home). |
| `conformity.yml` | push (main), PR (main), schedule (weekly), dispatch | Outward-conformity fixture sweep in strict mode over the user-scope ecosystem tree; fails on any per-fixture per-mandate `fail` cell. |
| `docs-drift.yml` | push (main), PR (main), dispatch | Documentation drift gate — forbids a root `docs/` tree and fails on any diff after regenerating the source-generated reference pages. |
| `codeql.yml` | push (main), PR (main), schedule (weekly), dispatch | CodeQL SAST over the Python source and the Actions workflows; uploads SARIF to the Security tab. |
| `zizmor.yml` | push (main), PR, dispatch | Static analysis of every workflow for template injection, credential persistence, unpinned actions, and excessive permissions; uploads SARIF. |
| `scorecard.yml` | push (main), schedule (weekly), dispatch, branch_protection_rule | OpenSSF Scorecard analysis; publishes to the OpenSSF API and uploads SARIF to the Security tab. Maintainer annotations live in `.scorecard.yml` at the repository root, because the archive Scorecard reads leaves out the export-ignored `.github/`. |
| `dco.yml` | PR (main), dispatch | Developer Certificate of Origin enforcement — requires a `Signed-off-by` trailer on every PR commit. |
| `dependency-review.yml` | PR (main) | Blocks PRs that introduce dependencies with known vulnerabilities or disallowed licenses, evaluated against the manifest/lockfile diff. |
| `pip-audit.yml` | push (main), PR, schedule (weekly), dispatch | Weekly `pip-audit` CVE scan of the resolved dependencies, the frozen vendored closure, and the hash-locked release build tooling, plus a PR/push gate on changes to them. |
| `npm-audit.yml` | push (main), PR, schedule (weekly), dispatch | Weekly `npm audit` of the documentation site's dependency tree, plus a PR/push gate on `site/package.json` and its lockfile. Sibling of `pip-audit.yml`, whose path filters cover the Python surface only — without this the npm tree is unaudited. Fails on high/critical. |
| `license-audit.yml` | push (main), PR, schedule (weekly), dispatch | Scans the resolved dependency tree for copyleft or otherwise MIT-incompatible licenses; mirrors the dependency-review allow-list. |
| `evals.yml` | dispatch only (runs when the `RUN_PAID_EVALS` variable is `true`) | Behavioural eval suite under `evals/` with `claude plugin eval` against a staged copy of the plugin package. Billed per run: the cost ceiling, the model, the judge model and the CLI version are required inputs; uploads `eval-results`. |
| `badges.yml` | workflow_run (CI completed on main), dispatch | Generates the shields.io endpoint JSONs after CI completes and uploads them as the `badges` artifact for the static site to serve. |
| `release.yml` | push (tag `v*.*.*`) | Release orchestration — check the harness convention pins, build sdist + wheel, package the VS Code extension (`apothem.vsix`) in its own job with vsce from the `.github/vsce` lockfile, SBOM, cosign signature, SLSA provenance, then publish the GitHub Release with every artifact attached. |
| `publish-npm.yml` | push (tag `v*.*.*`), dispatch | Publishes `@ahmed-g-gad/apothem` to registry.npmjs.org via npm trusted publishing (OIDC) with provenance; no registry token is stored or read. |
| `publish-vscode.yml` | push (tag `v*.*.*`), dispatch | Packages the extension into a `.vsix` with vsce from the `.github/vsce` lockfile and publishes to the Visual Studio Marketplace; gated on the `VSCE_PAT` secret and the `VSCODE_MARKETPLACE_READY` variable. |
| `publish-static-site.yml` | push (main), dispatch | Builds the Next.js + Fumadocs site, stages the canonical install scripts and badges, lints the staged scripts with the commands `installer-lint.yml` runs on every PR, and deploys to apothem.ahmedgad.com via GitHub Pages. |
| `harness-convention-monitor.yml` | schedule (weekly), dispatch | Enforces the 90-day freshness cadence on each adapter's `STANDARD-CONVENTION-PIN.md`; reports a drift alert when a pin is missing, malformed, future-dated, or stale. A second job runs `scripts/dev/check_vendor_urls.py` over every vendor URL the pins and harness templates cite and reports any that has moved or died; a timeout or a passing outage is listed but does not count. Each job keeps one open issue and comments on it rather than filing another. |
| `reusable-python-setup.yml` | workflow_call, dispatch | Reusable Python setup + dependency-install building block callers invoke via `uses: ./.github/workflows/reusable-python-setup.yml`; not a standalone gate. |

## Conventions

- **SHA-pinning.** Every action `uses:` reference is pinned by 40-character
  commit SHA followed by a `# vMAJOR.MINOR.PATCH` version comment. Renovate
  (`renovate.json`) proposes SHA bumps on a weekly schedule; a bump lands only
  when a maintainer merges it. One documented exception exists in `release.yml`:
  the SLSA reusable generator is trust-anchored on its per-tag attestation
  (Sigstore policy forbids SHA-pinning trusted reusable workflows), and that
  `uses:` line carries an `action-pinning-exempt:` marker. `.github/zizmor.yml`
  records the same exception as zizmor's only `ref-pin` policy.
- **Branch-protection required checks.** `ci.yml`'s `quality / <os> / py<ver>`
  matrix and `coverage` are `main` required status checks, as the
  `ci-docs-stub.yml` header records. Three more workflows declare, in their own
  headers, that a job is one: `clean-install-gate.yml`, `harness-matrix.yml`
  (`matrix (<name>)`), and `installer-lint.yml` (`installer-lint`). A required
  check is never gated by a `paths:` filter on its pull-request trigger — a
  skipped required check can never report and would silently gate nothing —
  which is why `clean-install-gate.yml`, `installer-lint.yml`, and the
  `harness-matrix.yml` pull-request trigger run on every PR to `main`, and
  `ci-docs-stub.yml` reports the required contexts green on a
  documentation-only PR that never runs the real jobs.
- **Public-only security scans.** Code scanning and dependency review are free
  on public repositories and need GitHub Code Security on private ones, and
  Scorecard needs public access to the repository. The jobs and steps that
  depend on them run only when `github.event.repository.private == false`:
  `codeql.yml`, the `review` job in `dependency-review.yml`, `scorecard.yml`,
  `zizmor.yml`, and the Trivy scan and SARIF upload in `ci.yml`. On a private
  repository they are skipped rather than failed, and they run again unchanged
  once the repository is public. None of them is a required check, so a skip
  never blocks a merge. The other gates, including pip-audit, npm audit, the
  license audit, and gitleaks, run in both states.
- **Least privilege.** Each workflow declares a `contents: read` baseline at the
  workflow scope; per-job overrides escalate a scope (`security-events: write`,
  `id-token: write`, `issues: write`, `pages: write`) only where a step needs
  it. No job uses write-all.
- **Runner hardening.** Every job's first step is `step-security/harden-runner`;
  jobs with a small, stable endpoint set (`dco.yml`, `dependency-review.yml`,
  `installer-lint.yml`, `scorecard.yml`) set `egress-policy: block` with an
  explicit allowlist, and the rest run `audit`. `zizmor.yml` and
  `license-audit.yml` stay on `audit` because their endpoint sets are not
  stable enough to allowlist without false-failing the job.
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
