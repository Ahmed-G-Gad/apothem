---
name: "vuln-triage"
version: "0.1.0"
updated: "2026-06-09"
description: "Vulnerability and security-advisory triage — matched when the user references a 'CVE', cites a 'security advisory' (GHSA, OSV, vendor bulletin), asks to 'triage this vuln', or asks 'is this vulnerable'. Targets one named advisory per invocation: severity-classifies it with a CVSS-style band (critical 9.0–10.0 / high 7.0–8.9 / medium 4.0–6.9 / low 0.1–3.9 / none 0.0) plus the justifying vector string, maps it to the affected surface in the host tree against the resolved lockfile, determines reachability and exploitability (reachable / unreachable / conditional + applicable attack vector), routes remediation from the closed set {patch, upgrade, mitigate, accept} (or not-applicable when no affected surface exists), and records a seven-field triage record with cited rationale. The output drives the operator's remediation decision; the skill does NOT apply the remediation, construct or run exploit payloads, scan the repository, re-publish CVSS scores, or re-solve the dependency graph. The 'accept' route is a security ratification — when the host has not ratified an accepted-risk threshold, it blocks on inquiry."
archetype: "security-template"
userInvocable: true
argument-hint: "[--advisory ID] [--focus PATH]"
disable-model-invocation: true
allowed-tools: "Read, Write, Edit, Glob, Grep, Bash"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Triage one vulnerability or security advisory against the host tree. The skill severity-classifies the advisory with a named scheme, locates the affected surface in the host, determines whether the affected code is reachable and exploitable, selects a remediation route, and records the disposition with cited rationale as a structured triage record. The output drives the operator's remediation decision; the skill does not apply the remediation itself.

## Detection Signal

The user references a `CVE` identifier, cites a `security advisory` (GHSA, OSV, vendor bulletin), asks to `triage this vuln`, or asks `is this vulnerable`. Any single phrasing that names a concrete advisory or asks whether the host carries a known vulnerability matches.

**Falsifiable counter-signal.** A request for a repository-wide scan, an exploit proof-of-concept, or the application of a fix is NOT a match — those route to the host's scanner CI, a penetration-test surface, and the remediation change-set respectively.

## Non-Goals

A deliberately narrow surface. The skill is NOT:

- **A full vulnerability scanner.** It triages one named advisory per invocation against a known surface. Repository-wide scanning is `pip-audit` / `gitleaks` / `trivy` / `osv-scanner` territory under the host's CI; the skill consumes a scanner's output, it does not replace it.
- **A remediation executor.** It selects a remediation route and records it; it does not apply the patch, bump the dependency, or edit the vulnerable code. Remediation lands as a separate operator-driven change-set governed by `rules/production-ready-prs.md`.
- **A penetration tester.** Exploitability is assessed by reachability analysis and advisory metadata, not by constructing or executing an exploit. No proof-of-concept payload is authored or run.
- **A CVSS authority.** It applies a CVSS-style classification to rank the advisory against the host's actual exposure; it does not publish or amend the upstream CVSS base score.
- **A dependency-graph resolver.** Transitive-dependency math is the package manager's job; the skill reads the resolved lockfile, it does not re-solve the graph.

## Workflow

Five numbered steps. Step 2 may short-circuit the workflow to step 5 when no affected surface exists (`not-applicable`).

1. **Classify severity using a named scheme.** Read the advisory metadata (CVSS vector, affected version range, attack vector, attack complexity, privileges required, user interaction). Assign a CVSS-style band — `critical` (9.0–10.0) / `high` (7.0–8.9) / `medium` (4.0–6.9) / `low` (0.1–3.9) / `none` (0.0) — and record the vector string that justifies it.
2. **Map the advisory to the affected surface in the host tree.** Use Glob and Grep to locate the affected package, module, or call site under `--focus PATH` (default: host root). Read the host's resolved manifest or lockfile (`pyproject.toml`, `uv.lock`, `package-lock.json`, the host's ratified equivalent per `rules/host-discovery.md`) and confirm the installed version falls inside the advisory's affected range. When no affected surface exists, the disposition is `not-applicable` and the workflow terminates at step 5.
3. **Determine exploitability and reachability.** Grep for call sites that reach the vulnerable function, configuration, or code path. Record whether the path is reachable (`reachable` / `unreachable` / `conditional`), whether the attack vector applies to the host's deployment (network-exposed, local-only, build-time-only), and whether a precondition (specific config, untrusted-input flow) is required.
4. **Route remediation.** Select exactly one route from the closed set `{patch, upgrade, mitigate, accept}` — `patch` (apply the upstream fix or backport), `upgrade` (bump to a fixed version), `mitigate` (configuration change, input validation, or network restriction that removes reachability), `accept` (document and accept the residual risk when unreachable or out of scope). The selection cites the severity band from step 1 and the reachability verdict from step 3.
5. **Record the disposition with rationale.** Emit the triage record per the Return Contract. The rationale cites the advisory ID, the affected-surface path, the reachability verdict, and the concrete driver for the chosen route. The record is the disposition's authoritative source.

## Return Contract

The skill emits one triage record per invocation. The record carries seven fields, every field populated:

| Field | Content |
|-------|---------|
| `id` | The advisory identifier (CVE / GHSA / OSV / vendor-bulletin ID) |
| `severity` | The CVSS-style band from step 1 plus the vector string |
| `affected-surface` | The host path mapped in step 2 (package + module + installed version), or `none` |
| `exploitability` | The reachability verdict from step 3 (`reachable` / `unreachable` / `conditional`) plus the applicable attack vector |
| `disposition` | The remediation route from step 4 (`patch` / `upgrade` / `mitigate` / `accept`), or `not-applicable` |
| `rationale` | The cited justification linking severity + reachability + route |
| `date` | ISO-8601 triage date |

A record with any field unpopulated is non-conformant. The record writes to STDOUT for direct invocation; when the host maintains a security-advisory ledger, the record appends to it at the host's ratified path.

## Foundational Stanzas

The four standing surfaces every operator inherits, adapted to this skill's single-advisory triage role.

### Refusal & Escalation

REFUSE any request that asks the skill to act outside its triage mission — applying remediation edits, constructing or running exploit payloads, repository-wide scanning, re-publishing CVSS scores. Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). When the advisory cannot be resolved to host state — the advisory ID is malformed, the affected package is absent, or the lockfile is unreadable — the skill STOPs and surfaces the recovery options; it never guesses a severity or fabricates an affected surface.

### Output Surface

The skill emits one triage record (the Return Contract). The record writes to STDOUT for direct invocation; when the host maintains a security-advisory ledger or `SECURITY.md` tracking surface, the record appends there at the host's ratified path per `rules/host-discovery.md`. NEVER write the record to a global-ecosystem location, and NEVER edit the vulnerable code as part of triage. Remediation artifacts a downstream change-set emits land at their domain-natural host locations per `rules/host-discovery.md`; per `rules/operational-mandates.md` CM-7, those artifacts carry natural domain language and zero plan-internal references.

### File-Authoring Contract

When the skill emits a NEW file — a fresh security-advisory ledger where the host has none — the file routes through `scripts/inject-header.py` so the canonical authorship-header banner is injected at the head; the injector is idempotent and detects the filetype variant automatically from the byte-exact fixture at `src/apothem/schemas/authorship-header.txt`. The exempt classes (LICENSE, JSON configuration files, lockfiles, generated assets, vendored trees, `.audit/` ephemera, `<project-root>/.apothem/plans/` ephemera, `.keep` / `.gitkeep` markers, binary files) are enumerated at `src/apothem/schemas/header-exceptions.txt`. Triage records emitted to STDOUT are header-exempt. Edits that append a record to an existing ledger preserve the ledger's existing banner.

### Structured Inquiry on Ambiguity

When triage reaches a decision in any of the seven authoritative-data categories per `rules/host-discovery.md` and `rules/interactive-questions.md` — identity, scope direction (which subtree to triage), preference (which severity scheme when the host ratifies one over CVSS), security posture (accepted-risk threshold, deployment exposure model), naming of public surfaces, infrastructure endpoints, version pins (the fixed-version target for an `upgrade` route) — and the host is silent, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data — a severity band, an affected version range, or an accepted-risk disposition is discovered or inquired, never invented. The `accept` route is a security ratification; when the host has not ratified an accepted-risk threshold, the route blocks on inquiry.

## Recommended Next Step

**Run the host's remediation change-set for the chosen route** — apply the `patch` / `upgrade` / `mitigate` action recorded in the triage record under `rules/production-ready-prs.md`, shipping the fix with its test, CHANGELOG entry, and CI-green attestation in one change-set. When the disposition is `accept`, record the operator-ratified accepted-risk entry in the host's `SECURITY.md` instead.

## Bindings (§0.j five-direction)

- **Drives →** ● Every single-advisory triage record's seven-field shape (the Return Contract is the disposition's authoritative surface). ● Every remediation route selection against the closed `{patch, upgrade, mitigate, accept}` set. ● Every downstream remediation change-set the triage record routes to. ◐ The host's security-advisory ledger append where one exists.
- **Satisfies →** ● `CLAUDE.md` Source Layout row "vuln-triage" (skills/ class). ● The security-cohort triage mission (severity-classify and route remediation for vulnerabilities and advisories).
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ class declaration with the folder-with-`SKILL.md` convention). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication).
- **Gated by ←** ● The harness's Read / Glob / Grep / Bash surface (the skill maps the advisory to host state by discovery). ● The presence of a resolvable advisory ID and a readable host manifest (the skill STOPs and surfaces recovery when either is absent).
- **Cross-bound with ↔** ↔ `rules/host-discovery.md` (M1 — affected surface and manifest discovered, never assumed). ↔ `rules/interactive-questions.md` (the structured-inquiry channel for accepted-risk and version-pin decisions). ↔ `rules/production-ready-prs.md` (M15 — the remediation change-set the Recommended Next Step routes to). ↔ `rules/disclosure-ledger.md` (M2 — triage dispositions recorded as findings). ↔ `skills/ecosystem-audit/SKILL.md` (sibling skill under the same registry section).
