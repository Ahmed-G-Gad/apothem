<!-- SPDX-License-Identifier: MIT -->

### Phase 4 — Adversarial Reference & Claim Verification

**Resolve every reference refute-by-default.** Route each through `agents/fact-checker.md`, which treats each citation as a phantom until the source resolves: it retrieves the reference at its recorded locator, confirms the locator returns a real source (a DOI that resolves, a permalink that loads, a commit pin that exists), and confirms the cited claim is actually supported by the retrieved source, not misattributed (R1). It assigns a cited verdict per reference:

- **`resolved`** — the locator returns a real source and the cited claim is supported. Only `resolved` references appear in the final list.
- **`misattributed`** — the source resolves but does not support the cited claim. Corrected to a supporting source, or the claim is removed (R4).
- **`phantom`** — the locator resolves to no retrievable source. Corrected to a resolvable source, or removed (R4).

When a cited reference is paywalled, login-gated, purchase-only, or otherwise unreachable after the retrieval attempt — distinct from a `phantom` whose locator resolves to nothing — do NOT silently swap it for a lower-trust accessible substitute or drop the claim it carries; trust outranks reachability per `rules/source-accessibility.md`. STOP and request the full source content from the operator through the structured-inquiry channel so the reference's support for the cited claim can be confirmed. Record the source-trust decision (which reference, its trust tier, whether the trusted source was reachable, why a substitute was used) in the paper's disclosure ledger per `rules/disclosure-ledger.md`.

**Then trace every results claim to the analysis.** Each reported effect, interval, and corrected outcome traces to a `confirmed` result in `_outputs/analysis.md`; no `fragile` or `unverified` result is claimed as confirmed.

Dispatch the verification as an **Audit Team** per `rules/agent-orchestration.md` when 3+ independent references justify parallel fan-out; each agent returns a pass/fail verdict plus resolution evidence under the 200-token audit return contract.
