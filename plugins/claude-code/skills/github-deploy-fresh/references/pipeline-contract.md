<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** The GitHub deployment pass that follows the `/freshify` agnostic freshening core and precedes the next-release cycle (`/github-deploy-next`). The inherited freshening is the substrate; this command owns only the GitHub-specific deployment contract.

**Consumed.** The `/freshify`-freshened working tree; the `origin` remote and its `main` branch; the repository's GitHub Actions workflow set and run history; the GitHub Releases and Packages state; the GitHub Pages build history; the environment and deployment records; the branch and tag set; the pull-request and issue state; the `CHANGELOG.md`; and the version declaration in the host's manifest.

**Emitted.** The single templated `release: <repo-name> v0.1.0` commit on `origin/main` (with sibling `release: <sub-package> v0.1.0` lines for monorepos); one first-version GitHub Release tagged `v0.1.0`; the curated first-version `CHANGELOG.md` entry per Keep-a-Changelog; strictly-green-and-maximal-score workflow cards; and a deployment report enumerating every inherited `/freshify` pass, every GitHub-trace removal, every confirmation outcome, the per-workflow green/score verdict, and the per-axis attestation against the seven-axes taxonomy.

**Pre-flight inquiry set.** Input Ingest emits the typed inquiry set per `rules/authority-inquiry.md` when the deployment surface is ambiguous — the `<repo-name>` token is unresolved, the sub-package set is undeclared for a monorepo, the OpenSSF Scorecard applicability is unconfirmed, the registry-coordinate set (npm, npx) is unknown, or the release-artifact signing requirement is unstated. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Confirmation contract.** Every destructive GitHub-side step routes a per-action confirmation per `rules/interactive-questions.md` §6 before acting. The default option is the non-destructive in-place path; the destructive option carries the `destructive-no-default` annotation per the per-file destructive-op confirmation discipline; no irreversible action — git-history rewrite, branch / run / package / tag / release purge, Pages-build-history wipe, environment / deployment-record removal, or repository delete-and-recreate — proceeds without an explicit operator selection.

**Pre-emission gate.** The trace-free culmination stanza runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the deployed tree, the `release: <repo-name> v0.1.0` commit, and the first-version CHANGELOG before the report is finalized; the gate attestation block lands inside the report. Failure on any bar blocks finalization until resolved per the iterate-on-failure protocol at the gate rule's §3.
