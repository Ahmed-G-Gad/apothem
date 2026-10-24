<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** The terminal gate before a release decision. It consumes the deployed repository's release surface — the quality matrix, the dependency manifest, the CI workflows, the visibility-surface artifacts, the CHANGELOG, and the version-and-tag state — and emits the readiness verdict the release decision consumes. The command modifies no source, publishes nothing, and tags nothing; the verdict is a read-only diagnostic.

**Consumed.** The deployed repository's release surface: root manifest files, `.github/workflows/*.yml`, the dependency lock state, `CHANGELOG.md`, the version declaration in the manifest, the git tag stream, and the seven visibility-surface artifacts (README · install/use · is-it-alive · is-it-safe · how-to-contribute · can-I-trust · what-changed-and-when) per `rules/production-ready-prs.md` §2. When the consuming suite carries a dependency-audit artifact at `_inputs/dependency-audit-findings.md`, its CVE inventory is read as context.

**Emitted.** The verdict artifact at `_inputs/release-readiness-findings.md` carrying the READY / BLOCKED verdict, the ordered blocking list, the per-gate finding count, the per-severity breakdown, the per-axis attestation against the seven-axes-of-breadth taxonomy, and the sweep's `verified:` date.

**Pre-flight inquiry set.** Input Ingest emits the typed inquiry set per `rules/authority-inquiry.md` when the release surface is ambiguous — the host's quality-matrix command set is undeclared, the signing requirement is unstated, the CHANGELOG format is unknown, or the versioning scheme is unconfirmed. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** The Validation Gate runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate verdict artifact before promotion. The gate attestation block is recorded inside the emitted artifact. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.
