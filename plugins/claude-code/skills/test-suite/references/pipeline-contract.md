<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** Consumes the deployed repository's behavior contracts (public-API surfaces, error-handling branches, documented invariants) and emits the test report downstream remediation cycles consume. **Upstream:** entered from `/plan-execute`'s implementation hand-off or invoked standalone against a deployed repository. **Downstream:** `/code-review` (per-file craft) and `/code-audit` (cross-file forensic) read the coverage-gap findings.

**Consumed.** The deployed repository's source tree, its root manifest (`pyproject.toml` / `package.json` / `Cargo.toml` / `go.mod` / sibling), and its existing test corpus. No upstream manifest is required; the command operates against on-disk state.

**Emitted.** The report at `_inputs/test-suite-report.md` plus the authored test files at the host's ratified test location. Test files carry the canonical SPDX header per the File-Authoring Contract; the report is header-exempt per the `.apothem/**` exception class at `src/apothem/schemas/header-exceptions.txt`.

**Pre-flight inquiry set.** The Discover phase emits the typed inquiry set per `rules/authority-inquiry.md` when the host's test framework is ambiguous (no framework declared in the manifest, no existing test corpus to converge on, or multiple frameworks present). Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3 — framework choice is a required-category naming decision and blocks test authoring until resolved.

**Pre-emission gate.** The Report phase runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate report and the authored test files before promotion; the gate attestation block lands inside the report. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.
