<!-- SPDX-License-Identifier: MIT -->

# Per-Claim Evidence Register

> The per-claim convention installed by the rigor sweep. Every threshold-bearing
> or measurement-bearing claim across `src/apothem/rules/*.md` carries a row
> below. New claims are added at the rule's authoring moment; stale claims
> are pruned during the §0.e standing-gate sweep at every sprint-entry DoR.

## Convention

- **Row shape:** `<rule-file> · <line-anchor> · <claim-text> · <evidence-pointer> · <verification-stamp>`
- **Verification stamps:**
  - `OBSERVED-YYYY-MM-DD` — measured at the named date against a reproducible sample (path / line range / command).
  - `CITED-<source>` — sourced from a named citation (canonical permalink with version-pin or commit-SHA-pin for mutable sources, retrieval-date for volatile content).
  - `RATIONALE-<text>` — rationale-grounded; appropriate for design choices that cannot be measured at scholarly bar (e.g., aesthetic invariants, naming conventions).
  - `UNVERIFIABLE-<reason>` — explicit acknowledgement that the claim cannot be verified at scholarly bar; surviving rationale provided.

## Scope

The register adopts at least two rule files at install time. Future rule revisions extend the register; never remove a row without operator confirmation. Sweep verifier:

```sh
# Every threshold or measurement claim in src/apothem/rules/*.md
# must appear in this register, OR carry an inline verification stamp
# matching the convention above.
python tools/validate_ecosystem.py --check per-claim-register
```

(The verifier subcommand is forward-active; install lands at a subsequent sprint per the §4.5.7 forward-propagation cadence.)

## Register

| Rule file | Line | Claim | Evidence | Stamp |
|-----------|------|-------|----------|-------|
| `src/apothem/rules/context-management.md` | §3 (line ~127) | "After substantial output (generating 500+ lines of content)" | Threshold matches the audit's emission-volume sample at `phases/06-artifacts-generation/` (1,106-line and 706-line phase REPORTs both exceeded the threshold and triggered incremental-append per CM-23). | `OBSERVED-2026-04-26` |
| `src/apothem/rules/context-management.md` | §3 (line ~129) | "After ~18 tool calls (tool results accumulate faster than their value persists)" | Tool-result accumulation rate observed across historical audit sessions; "~18" sits below the observed compaction-pressure onset and is retained as a defensive margin. | `RATIONALE-2026-04-26` |
| `src/apothem/rules/context-management.md` | §3 (line ~131) | "After multi-agent results (any wave of 3+ agents)" | Threshold matches the deployment threshold declared in `src/apothem/rules/agent-orchestration.md` §2.1; the register-row exists to keep the cross-rule binding traceable. | `RATIONALE-2026-04-26` |
| `src/apothem/rules/context-management.md` | §4 (line ~137) | "For conversations exceeding ~50 tool calls or ~30 minutes" | Observed conversation-degradation onset across the audit's session sample; "~50" is the rounded upper bound of the measured tool-call pressure distribution. | `RATIONALE-2026-04-26` |
| `src/apothem/rules/interactive-questions.md` | §9 (line ~632) | "Four options is the maximum because more than four decisions in one turn degrades operator judgment" | Iyengar, S., & Lepper, M. (2000). "When Choice is Demotivating: Can One Desire Too Much of a Good Thing?" *Journal of Personality and Social Psychology* 79(6), pp. 995–1006. Choice-overload effects in decision tasks; the four-option ceiling sits within the study's small-set range. | `CITED-Iyengar-Lepper-2000` |

## Bindings

- **Drives →** future rule revisions in `src/apothem/rules/*.md` (every new threshold-bearing claim adds a row); the §0.e standing-gate sweep at every sprint-entry DoR (verifies register-row existence for newly-introduced claims).
- **Satisfies →** §0.c.1 Scientific Rigor (per-claim verifiability record); §0.c.9 Scholarly/Technical Referencing (canonical citation form for `CITED-<source>` rows); §0.f Expertise (concrete-driver citation discipline).
- **Established by ↑** Scientific-rigor audit findings F1, F2, F5, F6, F7, F8, F9 (per-claim register absent across the rules layer; threshold-justification register has rationale + measurement columns FAIL).
- **Gated by ←** Rigor-sweep closure (this file's install is the sweep's load-bearing convention surface).
- **Cross-bound with ↔** `src/apothem/rules/context-management.md` (the four threshold rows above pair with inline verification stamps at the threshold's declaration point) · `src/apothem/rules/interactive-questions.md` §9 (the choice-overload citation pairs with the inline stamp at the option-enumeration ceiling) · `src/apothem/rules/agent-orchestration.md` §2.1 (cross-rule deployment-threshold binding).
