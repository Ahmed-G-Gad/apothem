#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Gate post-release follow-up work. The script is intentionally small and
# strict: follow-up steps must target an existing non-draft release and
# every required repository workflow for the release commit must already be
# green.

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

# Assert the built SBOM enumerates the frozen vendored closure. The vendored
# packages execute at runtime, so a release whose SBOM omits one of them ships
# an incomplete supply-chain record. generate-sbom.sh emits the SBOM into
# dist/release-assets/apothem-<TAG>.spdx.json (TAG is the vMAJOR.MINOR.PATCH
# git tag).
readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly SBOM_PATH="${REPO_ROOT}/dist/release-assets/apothem-${TAG}.spdx.json"
if [[ ! -f "${SBOM_PATH}" ]]; then
    printf 'check-release-ready: built SBOM not found at %s (run build-release-assets first)\n' \
        "${SBOM_PATH}" >&2
    exit 1
fi
if ! python -c '
import json
import sys

sbom = json.load(open(sys.argv[1], encoding="utf-8"))
names = {p.get("name", "").lower() for p in sbom.get("packages", [])}
required = ("attrs", "jsonschema", "jsonschema-specifications", "referencing", "pyyaml", "typing-extensions")
missing = [pkg for pkg in required if pkg not in names]
if missing:
    sys.stderr.write("vendored packages missing from SBOM: " + ", ".join(missing) + "\n")
    sys.exit(1)
' "${SBOM_PATH}"; then
    printf 'check-release-ready: SBOM at %s omits one or more vendored packages\n' \
        "${SBOM_PATH}" >&2
    exit 1
fi

printf 'check-release-ready: %s release checks are green\n' "${TAG}" >&2
