#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

# Self-gating guard for the CI Docs Stub workflow.
#
# The stub reports the required `quality` and `coverage` contexts green for
# documentation-only pull requests. Because `ci-docs-stub.yml`'s paths-ignore
# and `ci.yml`'s paths are both ANY-match triggers, a MIXED docs+code PR
# satisfies both, so the stub can start alongside the real job on the same
# context names. This guard closes that gap: it lists the PR's changed files
# and exits non-zero if ANY of them touches a gated surface, so the stub can
# never report a required check green over a real code or config change.
#
# The gated globs are kept in lockstep with `ci.yml`'s trigger `paths` and the
# stub's `paths-ignore` (asserted by tests/scripts/test_required_check_coverage.py).
# When that path set changes, update _GATED_PREFIXES / _GATED_EXACT below too.

set -euo pipefail

if [ -z "${PR_NUMBER:-}" ]; then
  echo "::error::assert-docs-only: PR_NUMBER is unset; this guard runs only on pull_request events."
  exit 1
fi

# Gated directory prefixes (a change under any of these must run the real job).
_GATED_PREFIXES="src/ tests/ site/ examples/ scripts/ .github/workflows/"
# Gated exact file paths.
_GATED_EXACT="pyproject.toml .pre-commit-config.yaml .gitleaks.toml"

# List the PR's changed files via the REST API, paginating fully.
changed_files="$(gh api --paginate \
  "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/files" \
  --jq '.[].filename')"

if [ -z "${changed_files}" ]; then
  echo "::error::assert-docs-only: the PR reports no changed files; refusing to fabricate a docs-only green."
  exit 1
fi

gated_hits=""
while IFS= read -r file; do
  [ -z "${file}" ] && continue
  for prefix in ${_GATED_PREFIXES}; do
    case "${file}" in
      "${prefix}"*) gated_hits="${gated_hits}${file}"$'\n' ;;
    esac
  done
  for exact in ${_GATED_EXACT}; do
    if [ "${file}" = "${exact}" ]; then
      gated_hits="${gated_hits}${file}"$'\n'
    fi
  done
done <<EOF
${changed_files}
EOF

if [ -n "${gated_hits}" ]; then
  echo "::error::assert-docs-only: the PR touches gated surface(s); ci.yml owns the quality+coverage contexts. The docs stub must not report them green. Gated files:"
  printf '%s' "${gated_hits}" | sed 's/^/  - /'
  exit 1
fi

echo "assert-docs-only: no gated surface in the diff; documentation-only PR confirmed."
