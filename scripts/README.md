<!-- SPDX-License-Identifier: MIT -->

# Scripts

Operator-, release-, install-, and dev-facing executables for the `apothem` repository — every standalone script lives here. Root-level entries are the operator / contributor utilities; `installer/` holds the install ceremonies, `release/` the release-engineering recipes, and `dev/` the internal CI/QA orchestration and audit / validation tooling (`validate_ecosystem.py`, `validate_hooks.py`, `chaos_pass.py`, `audit_all.py`, `auto_update.py`, `memory_audit.py`, `admin_merge.py`).

## Root-level scripts

| Script | Purpose |
|--------|---------|
| `apothem` / `apothem.ps1` / `apothem.cmd` | The `apothem` CLI binary. Dispatches `apothem <subcommand>` to the matching install/update/uninstall script; serves `--help` and `--version` inline. `.ps1` is the PowerShell parity sibling; `.cmd` is the Windows CMD wrapper delegating to the `.ps1`. |
| `build_release_tarball.py` | Cross-platform release-runtime archive builder (tar.gz on darwin/linux, zip on windows). Adds the `bin/` launcher layout the installers consume, excludes plan-suite ephemera / CI metadata / VCS internals, and emits the archive's SHA-256 digest to stdout. |
| `inject-header.py` / `inject-header.sh` | Deterministic authorship-header injector. Reads the canonical SPDX header line from `src/apothem/schemas/`; runs in `fix-in-place`, `emit-patch`, or `check` modes. The `.sh` wrapper locates a Python 3 interpreter and delegates to the `.py`. |

## `dev/` — contributor maintenance utilities

| Script | Purpose |
|--------|---------|
| `rebuild-assets-resvg.py` | The single canonical asset generator: regenerate the raster brand assets in [`assets/`](../assets/) from the editable SVG sources in `assets/src/` via a `resvg` binary plus Pillow. Supports a `--check-only` mode; `tests/unit/test_assets_manifest_coverage.py` asserts it produces every icon the PWA manifest references. |
| `regenerate-completions.sh` / `.ps1` | Re-emit the shell-completion scripts (`bash` / `zsh` / `fish`) into `src/apothem/cli/completions/` after a CLI surface change; byte-identical regeneration is the verification check. |
| `regen-behavior-goldens.py` | Regenerate the behavior-diff golden corpus under `tests/fixtures/behavior-diff/` from the deterministic HOME-isolated install-driver and CLI oracles after an intended behavior change; the canonicalized comparison stays portable across platforms, so a non-empty `git diff` flags platform-form churn to review. |
| `check_pip_pin_drift.py` | Assert every workflow's `PIP_PIN_VERSION` matches the canonical pin and no raw `pip==<version>` literal has been reintroduced. Invoked by CI. |
| `check_site_version_parity.py` | Assert `site/package.json`'s version matches `pyproject.toml`'s. Both are hand-maintained and the site renders its copy in the landing footer, so drift is silent — the site simply advertises a release that is no longer shipping. Invoked by CI beside the pin-drift check. |

## `installer/` — the canonical install scripts

The operator-facing bootstrap, update, and uninstall ceremonies — paired across three shell families. These are the scripts the network-install one-liners (`curl … | bash`, `irm … | iex`) fetch and the release-runtime archives bundle.

| Script family | Purpose |
|---------------|---------|
| `install.sh` / `install.ps1` / `install.bat` | Bootstrap the `apothem` package and materialize harness config. Idempotent; honors `APOTHEM_HARNESS` / `APOTHEM_REF` and sibling environment overrides. The `.bat` translates the documented POSIX flags (`--clean`, `--fresh`, `--dry-run`, `--yes`) to their PowerShell parameters, then delegates to the `.ps1`. |
| `update.sh` / `update.ps1` / `update.bat` | Update an existing install in place. Driven by environment overrides only (no CLI flags), so the `.bat` forwards its arguments verbatim. |
| `uninstall.sh` / `uninstall.ps1` / `uninstall.bat` | Remove the materialized harness config (via the engine) and the `apothem` PATH shim; confirms before removal unless `--yes`. Optional `--remove-source` deletes the managed clone. The `.bat` translates these POSIX flags — plus `--harness NAME` — to their PowerShell parameters, then delegates to the `.ps1`. |

## `release/` — release-engineering recipes

Invoked by the release engineer and by `.github/workflows/release.yml`. Each ships a POSIX `.sh` and a PowerShell `.ps1` parity sibling (`extract_release_notes.py` and `requirements-build-linux.txt` are single-file siblings).

| Script family | Purpose |
|---------------|---------|
| `build-release-assets` | Build the full GitHub Releases asset matrix for a version tag (runtime tarballs/zips, sdist + wheel supply-chain evidence, SBOM, SHA256SUMS). |
| `check-release-ready` | Gate post-release follow-up work: the tag must name an existing non-draft release and every required workflow for the release commit must be green. |
| `generate-sbom` | Generate an SPDX-JSON Software Bill of Materials for the source tree via Anchore `syft`. |
| `sign-assets` | Cosign keyless-OIDC `sign-blob` recipe for the release asset matrix (Sigstore signature bundle + Fulcio certificate per asset, plus a signed `SHA256SUMS`). |
| `verify-provenance` | Verify the supply-chain provenance chain for a release asset set: SHA-256 manifest re-computation, cosign, and the SLSA verifier. |

## Conventions

- Every script carries the canonical SPDX header line at its head.
- Shell scripts ship a POSIX `.sh` and a PowerShell `.ps1` sibling for cross-platform parity; `.bat` wrappers translate the documented POSIX flags to their PowerShell parameters and then delegate to the `.ps1`, so a CMD user gets the same `--flag` UX as the `.sh` sibling (a wrapper for a command with no CLI flags, such as `update`, forwards its arguments verbatim). Cross-platform parity is structural — touching one member of a family obliges updating its siblings in the same change-set.
- One-shot migration / normalization utilities default to `--dry-run` and are idempotent on re-run.
- Regenerator scripts (assets, shell completions) verify by byte-identical regeneration; the install/uninstall ceremonies keep their idempotency and unsafe-target-refusal guards.
- Self-tests for these scripts live under [`tests/scripts/`](../tests/scripts/).

## Working in this folder

To add or change a script: place it in the matching class subdirectory (or the
root for operator utilities), supply the cross-platform sibling(s), and add a
row to the relevant table above. Self-tests live under
[`tests/scripts/`](../tests/scripts/) (and [`tests/packaging/`](../tests/packaging/)
for the release-artifact builders); run them plus the conformity gate before
handoff:

```bash
python -m pytest tests/scripts tests/packaging
python -m apothem.conformity.gate --all .
python scripts/inject-header.py --mode check <path>   # confirm SPDX headers
```

Lint shell with the project's shell linters before handoff.
