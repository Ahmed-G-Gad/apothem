---
trigger: glob
description: "Path-filtered companion sub-rule carrying the seven-category inquiry catalog (full forbidden-to-invent + inquire-because columns), the required-vs-optional explanatory paragraph, the carved-out auto-decisions catalog, and the failure-tells enumeration declared at the parent `authority-inquiry.md` rule's anchors; demand-loaded on host-project artifact authoring."
globs: "**/*.md, **/CLAUDE.md, **/rules/**, **/commands/**, **/skills/**, **/agents/**, **/docs/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Authoritative Inquiry — Seven Categories, Carve-Outs, and Failure Tells (Companion Sub-Rule)

## Purpose

Specify the executable catalog surfaces for the M5 authoritative-inquiry discipline declared at the parent rule `rules/authority-inquiry.md`. This companion is path-filtered: it loads when the assistant edits any host-project artifact under the governed-core authoring directories, keeping the parent's always-on payload lean while preserving full catalog fidelity at the demand-load surface. The parent rule remains the canonical home for the M5 standing directive, the canonical-channel routing, and the disclosure-surface anchors; this companion carries the full seven-row inquiry catalog, the required-vs-optional explanatory paragraph, the carved-out auto-decisions catalog, and the failure-tells enumeration.

## Obligations

### 1. The Seven Inquiry Categories

| Category | Forbidden to invent | Inquire because |
|---|---|---|
| **Identity** | Names, emails, handles, pronouns, organizations, tenants, team affiliations, role descriptions. | Bind to a real person; create real-world artifacts (commits, PRs, public attribution). |
| **Scope direction** | Which subtree, which branch, which environment (dev / staging / prod), which target (libraries vs services), which user-facing vs internal-only. | The user has implicit context the agent lacks; silent picks misalign. |
| **Preference** | Formatter, linter, test framework, documentation generator, CI provider, branch strategy, commit-message convention, release-signing mechanism, versioning scheme, license — *where the host has not ratified one*. | Each is a long-lived ratification that resists silent adoption. |
| **Security** | Secret-rotation cadence, allowed shells, allowed network egress, accepted-risks list, trusted-action allowlist, MCP-server auth endpoint specifics. | Security misconfiguration is high-impact; silent picks risk silent breach. |
| **Naming** | A new convention introduced where the host has none, or a name binding (function name, CLI flag, subcommand, config key) where the user has implicit preferences. | Names are durable; silent picks compound into namespace pollution. |
| **Infrastructure** | Endpoints, hosts, ports, paths, regions, queue names, topic names, table names. | Bind to real-world resources; invention causes real-world failures. |
| **Version pins** | Which version of which dependency, where the host has not pinned and the choice matters (security-relevant deps, behavioral-shift deps, semver-major boundaries). | Long-tail consequences; silent picks burden the user. |

**Required inquiries** (Identity, Scope direction, Security posture, Naming-of-public-surfaces) MUST block dependent artifacts: emission produces `<USER-CONFIRM:id=<id>>` placeholders that pre-emission gate row 5 at `rules/pre-emission-gate.md` rejects until resolved. **Optional inquiries** the user MAY decline by silence; the agent then falls back to the **Recommended** option per `rules/option-annotation.md` and records the fallback as a finding so the user sees a decision was made. The split is fixed: the four required categories never silently resolve to an internal default; the remaining categories never block emission.

#### High-risk always-gate classes

These seven change classes ALWAYS route a confirmation through the structured-inquiry channel, even under an `--autonomous` opt-in that otherwise suppresses inquiry — the opt-in raises the silence-fallback threshold, it never waives this floor. This list is the single-source-of-truth semantic taxonomy of the high-risk classes:

1. A shared or published version-control-history rewrite.
2. Removal of a whole module or a documented public interface.
3. A major-version dependency upgrade carrying breaking changes.
4. A license, legal, or compliance-file change.
5. Secret rotation or removal, and any authentication or authorization behavior change.
6. A database schema or data migration.
7. Any change that breaks a documented public-API contract.

`commands/elevate.md` and `commands/fortress.md` cite this list rather than re-authoring it. This subsection carries only the high-risk-CLASS taxonomy; the destructive-op confirmation MECHANISM — canonical option sets and the no-default floor — is owned by `rules/interactive-questions-canonical-shapes.md` §6 and is not restated here.

### 2. Carved-Out Auto-Decisions

To prevent inquiry fatigue, the agent MAY decide the following five classes **without inquiry** — each disclosed in the change ledger as `[Default — applied: <decision>; class: <carve-out>]`:

- **Pure validity.** Syntax errors, schema violations, unambiguous typos.
- **Pure rigor.** Folklore → cited; missing dates added; unverifiable claims marked.
- **Universally-safe security.** `deny .env*`, `deny ~/.ssh/**` reads, `deny rm -rf:*`, `deny sudo:*`, `deny git push --force*` to protected branches, `deny eval` / `exec` on untrusted input.
- **Pure formatting normalization.** EOL, trailing whitespace, single quote-style per file *where the host has a ratified style and the artifact diverges*.
- **Internal reference repair where the fix is unambiguous.** Dead path → unique live path discovered by search.

Anything outside this carve-out goes through the inquiry surface.

### 3. Failure Tells

A `mailto:` field with a plausible-looking but unverified address. An invented domain in an MCP endpoint. A `CODEOWNERS` line with a guessed handle. A README "maintainer" field that the user has not stated. A version pin on a host-mutable dependency without the user's ratification. A `package.json` `author` field populated from `.git/config` without inquiry. A test-fixture user record with a synthetic-looking name and email. An emitted artifact carrying an unfilled `<USER-CONFIRM:…>` placeholder. A required-category decision (identity / scope / security / public-surface naming) silently resolved to an internal default.

## Enforcement

Path-filtered (the seven glob patterns in this rule's `pathFilter` field), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/authority-inquiry.md`. The parent rule carries the M5 standing directive, the canonical-channel routing through `rules/interactive-questions.md`, and the disclosure-surface anchors; this companion carries the seven-row inquiry catalog with full columns, the required-vs-optional explanatory paragraph, the carved-out auto-decisions catalog, and the failure-tells enumeration. Together they constitute the canonical specification for M5 — Authority Principle (inquiry half).

## Bindings (§0.j five-direction)

- **Drives →** ● Every host-project artifact authoring session under the seven path-filter globs (every authoritative-data emission consults the §1 catalog). ● The carve-out auto-decision routing at §2 (every default-applied decision is recorded with the named class). ● The failure-tells sweep at §3 (every emitted artifact passes the failure-tell screening). ◐ The pre-emission gate row 5 at `rules/pre-emission-gate.md` (the placeholder-presence check operationalizes this companion's required-inquiry blocking).
- **Satisfies →** ● the fifteen-mandate registry row **M5 — Authority Principle** (inquiry-half catalog surface). ● `rules/authority-inquiry.md` — Required Categories (the seven-row catalog). ● `rules/authority-inquiry.md` Carved-Out Auto-Decisions (the carve-out catalog). ● `rules/authority-inquiry.md` companion-sub-rule anchors (the parent rule's pointers to this companion's full catalogs).
- **Established by ↑** ● `rules/authority-inquiry.md` (parent-rule anchors). ● the fifteen-mandate registry (ratifies M5). ● `rules/authority-inquiry.md` Carved-Out Auto-Decisions (the upstream catalog specifications this companion reproduces with operational depth).
- **Gated by ←** ● The path-filter (the seven glob patterns) — this rule demand-loads only on host-project artifact authoring touches. ● `rules/authority-inquiry.md` always-on baseline (parent rule must be live for the companion's anchors to surface).
- **Cross-bound with ↔** ↔ `rules/authority-inquiry.md` (parent rule; companion-sub-rule anchors bind this companion). ↔ `rules/interactive-questions.md` (the canonical-channel routing the parent rule delegates; every §1 inquiry routes through the structured inquiry schema). ↔ `rules/host-discovery.md` (M5 discovery half — the discovery and inquiry halves form a complete coverage of authority data; §1 categories are the inquiry-half projection of M1's discovery walk). ↔ `rules/disclosure-ledger.md` (M2 — every §1 inquiry outcome and §2 carve-out default is recorded in the ledger). ↔ `rules/option-annotation.md` (M7 — every §1 inquiry's option set carries the recommended marker). ↔ `rules/pre-emission-gate.md` (M4 — bar 5 of the gate enforces this companion's `<USER-CONFIRM:…>`-placeholder absence and unresolved-inquiry array population).
