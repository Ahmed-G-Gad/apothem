<!-- SPDX-License-Identifier: MIT -->

### Phase 5 — Findings Emission + Validation Gate

Emit the consuming suite's `_inputs/security-audit-findings.md` with the canonical sections:

1. **`## §1 Audit Metadata`** — HEAD commit SHA, ISO-8601 timestamp, scope (full / `--focus` value), tool-versions table (`pip-audit` · `safety` · `bandit` · `semgrep` · `gitleaks` · `trufflehog` · CodeQL).
2. **`## §2 Executive Summary`** — per-severity counts (HIGH / MEDIUM / LOW) per category + the top-three findings ordered by exploitability × impact.
3. **`## §3..§N` Per-Category Findings** — one section per audited category (Secrets · Permissions · Input-Validation · Shell-Injection · SQL-Injection · Deserialization · Path-Traversal · RCE · Dependency-CVE · CodeQL). Each finding carries identifier (`SF-<N>`) · severity · CWE mapping · OWASP ASVS / Top 10 mapping · file:line-range + commit SHA · observed pattern · recommended remediation · concrete-driver rationale per `rules/interactive-questions-canonical-shapes.md` §3.2.1.
4. **`## §Coverage Attestation`** — explicit attestation against OWASP ASVS v4.0.3+ chapters, OWASP Top 10 (2021) categories, and CWE Top 25 (2024) weaknesses; uncovered chapters / categories / weaknesses named with rationale.
5. **`## §Validation Gate Outcome`** — the fifteen-bar gate attestation block per `rules/pre-emission-gate.md` §2.
6. **`## §Bindings (§0.j five-direction)`** — the artifact's outward bindings.

Apply incremental generation per `rules/large-file-generation.md` above 500 lines. Run the fifteen-bar gate per `rules/pre-emission-gate.md` (canonical per-bar table at `rules/pre-emission-gate-bars.md` §1). Security-tier deltas: **M5** (every finding cites a verified file:line + commit SHA; no fabrication; secret evidence redacted); **M7** (every severity-boundary, accepted-risk, and false-positive call carries `**Recommended**` + concrete-driver rationale). Iterate on bar failure per §3 until every bar passes or its three-round cap returns BLOCKED, then emit the attestation block.
