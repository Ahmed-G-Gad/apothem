<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Standalone-ratified, read-only — orthogonal to the canonical sequence.** The canonical sequence is `/plan-spec → /plan-generate → /plan-review → /plan-design (CONDITIONAL — architecture-bearing suites only) → /plan-execute`; this command is invocable read-only at any point in it (including between `/plan-design` and `/plan-execute`). It emits no artifacts — it reads the suite's tracking files and presents a report directly to the operator. It is therefore exempt from the remaining contract elements:

- **Handoff Manifest schema.** N/A — no manifest is consumed or emitted; the command is a read-only reporter outside the pipeline's hand-off chain.
- **Pre-flight inquiry set.** N/A — no authoritative-data emission; the command reports on whatever tracking-file state exists at invocation and surfaces gaps as findings within its prose, not as structured-inquiry invocations.
- **Pre-emission gate.** N/A — no artifact emission means the fifteen-bar gate has no surface to gate. The read-only invariant is itself the conformity guarantee.

The exemption is anchored in the specification's §3.5 opening clause "every slash-command that emits artifacts into the host project declares" — no emission ⇒ no contract surface beyond this pipeline-position declaration.
