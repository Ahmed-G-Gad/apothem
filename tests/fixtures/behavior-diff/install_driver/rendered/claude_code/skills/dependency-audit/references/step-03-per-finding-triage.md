<!-- SPDX-License-Identifier: MIT -->

### Phase 2 — Per-Finding Triage

Assign each drafted finding a severity from the closed taxonomy `{HIGH, MEDIUM, LOW}` with concrete-driver rationale per `rules/interactive-questions-canonical-shapes.md` §3.2.1:

- **HIGH** — CVE with CVSS v3.1 ≥ 7.0 and an exploit-available indicator; license incompatibility with a production-distributed dependency (GPL / AGPL into MIT / Apache redistribution surfaces); security-critical dependency at transitive depth ≥ 3 with no direct equivalent; or yanked production dependency with no published replacement. Cites class 3 (named constraint — CVE / SPDX identifier) or class 6 (tool advisory).
- **MEDIUM** — CVE with CVSS v3.1 in 4.0–6.9; license uncertainty (dual-licensed dependency, active license unclear); deprecation of a development-tier dependency; unpinned production dependency without an active CVE; or transitive-depth concern at depth = 2. Cites class 3 or class 6.
- **LOW** — CVE with CVSS v3.1 < 4.0; license drift (a non-load-bearing dev dependency on an unusual but permissive license); deprecation of a test-only dependency; or a transitive-depth concern without a security or licensing trigger. Cites class 5 (rule citation) or class 6.

**Axis attestation.** Every finding names which seven-axes it touches: CVE findings load Security heavily + Tooling (scanner instrumentation); license findings load Security + Architecture (redistribution-surface implications); deprecation findings load Tooling + Observability (registry-marker drift). Multi-axis findings carry the full set.

**Borderline calls route through inquiry.** When severity is genuinely underdetermined (CVSS 6.9 vs. the 7.0 floor; dual-license disposition; transitive-depth = 2 borderline), surface the triage through the structured-inquiry channel — the option set names both candidate severities with concrete-driver rationale per `rules/interactive-questions.md` §3.

**Remediation routing.** Each CVE finding routes its disposition through `skills/vuln-triage` (the seven-field severity-band + reachability + route record); each finding whose remediation is an audited version bump routes through `skills/dependency-upgrade` (changelog-reviewed, pinned, gate-verified). The command records the routed owner per finding; it never re-publishes CVSS, re-solves the graph, or authors the bump inline.
