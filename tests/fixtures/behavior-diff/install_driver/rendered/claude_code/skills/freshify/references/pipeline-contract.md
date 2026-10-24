<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** The freshening pass that precedes the release decision. It consumes the target repository's full working surface and emits an in-place-freshened tree plus a freshening report; it specializes for no forge, registry, or continuous-integration vendor. The agnostic core here is the substrate the forge-specific specialization extends.

**Consumed.** The target repository's working surface: the host's ratified ignore manifest (the source of truth for what is generated state per `rules/host-discovery.md`), the cache and build-artifact trees that manifest enumerates, the narrative surfaces (the readme, the changelog, the contribution guide, the documentation tree, the inline source comments), the version-control history, the version declaration in the host's manifest, and the host's discovered quality-gate command set (formatter, linter, type-checker, test runner, documentation build, security scan).

**Emitted.** The freshened working tree (in-place by default), a concise current-version changelog entry curated per the host's ratified changelog format, and a freshening report enumerating every sweep, every removal, every confirmation outcome, the per-gate green/blocked verdict, and the per-axis attestation against the seven-axes-of-breadth taxonomy.

**Pre-flight inquiry set.** Input Ingest emits the typed inquiry set per `rules/authority-inquiry.md` when the freshening surface is ambiguous — the host's ignore manifest is absent, the quality-gate command set is undeclared, the changelog format is unknown, or the versioning scheme is unconfirmed. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Confirmation contract.** Every destructive step routes a per-target confirmation through the structured-inquiry channel per `rules/interactive-questions.md` §6 before acting. The default option in each confirmation is the non-destructive, in-place path; the destructive option is annotated `destructive-no-default` per the per-file destructive-op confirmation discipline, and no irreversible action proceeds without an explicit operator selection.

**Pre-emission gate.** The Validation Gate runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the freshened tree and the changelog before the report is finalized. The gate attestation block is recorded inside the report. Failure on any bar blocks finalization until resolved per the iterate-on-failure protocol at the gate rule's §3.
