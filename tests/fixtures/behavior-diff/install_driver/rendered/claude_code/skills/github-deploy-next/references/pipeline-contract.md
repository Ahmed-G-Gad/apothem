<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** The subsequent-release pass that follows the fresh-first-release pass at `github-deploy-fresh.md` and repeats once per release cycle.

**Consumed.** The `origin` remote and its `main` branch; the open and ready pull-request set; the issue set the release addresses; the Conventional Commits change set since the last release tag; the `CHANGELOG.md` `[Unreleased]` section; the version declaration in the host's manifest; and the host's discovered signing posture per `rules/host-discovery.md`.

**Emitted.** The merged commits on `origin/main`; the bumped version in the host's manifest; the rolled `CHANGELOG.md` with the new version section per Keep-a-Changelog; one new annotated and signed tag; one new GitHub Release with current-version release notes; and a deployment report enumerating every merge, every resolved issue, the derived bump and its rationale, every confirmation outcome, and the per-axis attestation against the seven-axes taxonomy.

**Pre-flight inquiry set.** Input Ingest emits the typed inquiry set per `rules/authority-inquiry.md` when the cycle surface is ambiguous — the ready-PR set is undeclared, the issue set the release addresses is unconfirmed, the derived bump is contested, or the release-artifact signing requirement is unstated. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Confirmation contract.** The merge step and the publish step each route a per-action confirmation per `rules/interactive-questions.md` §6 before acting; the irreversible option carries the `destructive-no-default` annotation per the destructive-op confirmation discipline. The version-bump preview, the CHANGELOG draft, and the release-notes draft are read-only previews and carry NO gate — the proportionality is stated, not blanket.

**Pre-emission gate.** The culmination stanza runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the merged tree, the bumped manifest, the rolled CHANGELOG, and the release notes before the report is finalized; the gate attestation block lands inside the report. Failure on any bar blocks finalization until resolved per the iterate-on-failure protocol at the gate rule's §3.
