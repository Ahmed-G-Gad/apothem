#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Gate post-release follow-up work. The script is intentionally small and
# strict: follow-up steps must target an existing non-draft release and
# every required repository workflow for the release commit must already be
# green. It also checks the published CycloneDX SBOM for the tag (see the
# SBOM section below). GH_TOKEN must be set: the script reads releases and
# workflow runs with the GitHub CLI, and the release-cycle runbook documents
# the token scope.

set -euo pipefail
IFS=$'\n\t'

readonly TAG="${1:?usage: check-release-ready.sh <tag>}"
readonly REPO="${GITHUB_REPOSITORY:-${APOTHEM_GITHUB_REPO:-ahmed-g-gad/apothem}}"

if [[ -z "${GH_TOKEN:-}" ]]; then
    printf 'check-release-ready: GH_TOKEN is required\n' >&2
    exit 1
fi

if [[ ! "${TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf 'check-release-ready: %s is not a vMAJOR.MINOR.PATCH tag\n' "${TAG}" >&2
    exit 1
fi

release_state="$(
    gh release view "${TAG}" \
        --repo "${REPO}" \
        --json isDraft,isPrerelease,tagName \
        --jq '[.isDraft, .isPrerelease] | @tsv'
)"
IFS=$'\t' read -r is_draft is_prerelease <<<"${release_state}"
if [[ "${is_draft}" != "false" ]]; then
    printf 'check-release-ready: %s is still a draft release\n' "${TAG}" >&2
    exit 1
fi
if [[ "${is_prerelease}" != "false" ]]; then
    printf 'check-release-ready: %s is marked prerelease\n' "${TAG}" >&2
    exit 1
fi

commit_sha="$(git rev-list -n 1 "${TAG}")"
if [[ -z "${commit_sha}" ]]; then
    printf 'check-release-ready: cannot resolve commit for %s\n' "${TAG}" >&2
    exit 1
fi

required_workflows=(
    ci.yml
    ci-matrix.yml
    clean-install-gate.yml
    codeql.yml
    conformity.yml
    harness-matrix.yml
    license-audit.yml
    pip-audit.yml
    reuse.yml
    publish-static-site.yml
    release.yml
    scorecard.yml
)

for workflow in "${required_workflows[@]}"; do
    conclusion="$(
        gh run list \
            --repo "${REPO}" \
            --workflow "${workflow}" \
            --commit "${commit_sha}" \
            --limit 20 \
            --json conclusion,status \
            --jq 'map(select(.status == "completed")) | first | .conclusion // ""'
    )"
    if [[ "${conclusion}" != "success" ]]; then
        printf 'check-release-ready: %s is not green for %s (conclusion: %s)\n' \
            "${workflow}" "${commit_sha}" "${conclusion:-missing}" >&2
        exit 1
    fi
done

# Assert the SBOM describes this tag and enumerates the frozen vendored closure.
# The vendored packages execute at runtime, so a release whose SBOM omits one
# of them ships an incomplete supply-chain record. The release workflow writes
# the CycloneDX 1.6 JSON SBOM to dist/sbom.cdx.json and attaches it to the
# GitHub Release as sbom.cdx.json. build-release-assets writes the same file
# name into dist/release-assets/, the path checked here: download the
# published asset there (see the release-cycle runbook) or build it first.
# The required names must stay in step with VENDORED in
# scripts/release/generate_sbom.py (rpds-py is apothem-authored and absent).
readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly SBOM_PATH="${REPO_ROOT}/dist/release-assets/sbom.cdx.json"
if [[ ! -f "${SBOM_PATH}" ]]; then
    printf 'check-release-ready: SBOM not found at %s (download the published sbom.cdx.json there, or run build-release-assets first)\n' \
        "${SBOM_PATH}" >&2
    exit 1
fi
if ! python - "${SBOM_PATH}" "${TAG#v}" <<'PY'
import json
import sys

sbom_path, version = sys.argv[1], sys.argv[2]
with open(sbom_path, encoding="utf-8") as handle:
    sbom = json.load(handle)
if sbom.get("bomFormat") != "CycloneDX":
    sys.stderr.write("SBOM is not a CycloneDX document\n")
    sys.exit(1)
root = (sbom.get("metadata") or {}).get("component") or {}
if root.get("purl") != f"pkg:pypi/apothem@{version}":
    sys.stderr.write(f"SBOM describes {root.get('purl')!r}, not apothem {version}\n")
    sys.exit(1)
names = {
    str(c.get("name", "")).lower()
    for c in sbom.get("components", [])
    if c.get("type") == "library"
}
required = ("attrs", "jsonschema", "jsonschema-specifications", "referencing", "pyyaml", "typing-extensions")
missing = [pkg for pkg in required if pkg not in names]
if missing:
    sys.stderr.write("vendored packages missing from SBOM: " + ", ".join(missing) + "\n")
    sys.exit(1)
PY
then
    printf 'check-release-ready: SBOM at %s fails the release checks\n' "${SBOM_PATH}" >&2
    exit 1
fi

printf 'check-release-ready: %s release checks are green\n' "${TAG}" >&2
