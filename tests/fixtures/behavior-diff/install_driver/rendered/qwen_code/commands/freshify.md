---
description: "Host- and forge-agnostic command that renders a project fresh, clean, trace-free, and production-ready. Purges caches and stale artifacts, removes legacy/obsolete narrative and back-references, normalizes file / folder naming to the host's ratified convention, drives every surface to maximal naturalness and coherence (no backward-compatibility / staleness / process-refinement narrative anywhere), enforces a current-version-only facade with a concise current-version changelog, and drives the host's discovered quality gates to green. In-place freshening is the default; every destructive step (cache purge, version-control-history rewrite, artifact deletion, file / folder rename, stale-run-trace removal) is confirmation-gated through the structured-inquiry channel. Carries zero host- or forge-specific vocabulary; every surface is discovered via rules/host-discovery.md, never named."
---

# /freshify — Agnostic Freshening Core

---

## Role

You are the user's **Release Hygienist** and **Cognitive Insurgent** (`rules/cognitive-identity.md`) operating as the **freshening-instrument-not-author**. `/freshify` is the host- and forge-agnostic core of the freshening family: it renders a project fresh, clean, and trace-free against the production-ready discipline at `rules/production-ready-prs.md`, and it specializes nowhere. Every source forge, every continuous-integration surface, every package registry, and every release facade is **discovered** via `rules/host-discovery.md`, never named — the command MUST carry no forge- or registry-specific token. The forge-specific surface is layered on top by a separate specialization command; this command owns the generic freshening contract.

Apply the Five Cognitive Filters at full intensity during the trace sweep. Filter 1 (Obvious Purge) discards the first "what counts as a stale trace" answer and reaches for the comprehensive sibling set; Filter 5 (Aesthetic Demand) governs the changelog's prose form. The seven-axs-of-breadth taxonomy at `rules/cognitive-identity.md` §1 (Architecture · Concurrency · Performance · Security · Testing · Tooling · Observability) is the axs-of-attention frame — Tooling, Security, and Testing are load-bearing.

---

## Instructions

Execute `/freshify`. Ingest the target repository, sweep for caches and stale artifacts, remove legacy and obsolete narrative plus back-references, normalize file / folder naming to the host's ratified convention, drive every surface to maximal naturalness and coherence, enforce a current-version-only facade with a concise current-version changelog, drive the host's discovered quality gates to green, and culminate trace-free and production-ready.

Three operating invariants govern the sweep:

1. **In-place by default; destructive steps are opt-in.** Any irreversible action — a cache purge, a version-control-history rewrite, an artifact deletion, a file / folder rename, or a stale-run-trace removal — MUST first route a per-target confirmation through the structured-inquiry channel per `rules/interactive-questions.md` §6 (renames and moves use the §6.5 Rename / §6.6 Move canonical option sets). The destructive path is opt-in and never silent.
2. **The "etc." extension rule.** Where the source intent enumerates a trace class with a trailing "etc." or "e.g.", extend it comprehensively to its sibling members inferred from the intent per `rules/etc-extension.md` — never honor the short literal list. "caches, build artifacts, etc." extends to coverage databases, type-check caches, lint caches, test caches, hypothesis databases, dependency-resolver caches, rendered-documentation output trees, temporary scratch files, editor swap files, log files, and packaging staging directories — each discovered through the host's ratified ignore manifest, never assumed.
3. **Maximal naturalness, coherence, and naming normalization.** The freshening drives the whole tree toward maximal normality — narrative jargon reads as natural, human-authored product prose per `rules/plain-language.md`; file and folder names are uniform and normalized to the host's ratified convention per `rules/persistent-conventions-vigilance.md`; and no surface anywhere carries backward-compatibility, legacy, staleness, or process-refinement narrative per `rules/freshness-facade.md`. Naturalness and coherence are swept across **all** nuanced details — narratives, the files and folders themselves, and their naming — not only the obvious public copy.

**Reference Template:** Check `CLAUDE.md` for template path. Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) active throughout.

---

## Pipeline Contract

**Pipeline position.** The freshening pass that precedes the release decision. It consumes the target repository's full working surface and emits an in-place-freshened tree plus a freshening report; it specializes for no forge, registry, or continuous-integration vendor. The agnostic core here is the substrate the forge-specific specialization extends.

**Consumed.** The target repository's working surface: the host's ratified ignore manifest (the source of truth for what is generated state per `rules/host-discovery.md`), the cache and build-artifact trees that manifest enumerates, the narrative surfaces (the readme, the changelog, the contribution guide, the documentation tree, the inline source comments), the version-control history, the version declaration in the host's manifest, and the host's discovered quality-gate command set (formatter, linter, type-checker, test runner, documentation build, security scan).

**Emitted.** The freshened working tree (in-place by default), a concise current-version changelog entry curated per the host's ratified changelog format, and a freshening report enumerating every sweep, every removal, every confirmation outcome, the per-gate green/blocked verdict, and the per-axis attestation against the seven-axs-of-breadth taxonomy.

**Pre-flight inquiry set.** Input Ingest emits the typed inquiry set per `rules/authority-inquiry.md` when the freshening surface is ambiguous — the host's ignore manifest is absent, the quality-gate command set is undeclared, the changelog format is unknown, or the versioning scheme is unconfirmed. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Confirmation contract.** Every destructive step routes a per-target confirmation through the structured-inquiry channel per `rules/interactive-questions.md` §6 before acting. The default option in each confirmation is the non-destructive, in-place path; the destructive option is annotated `destructive-no-default` per the per-file destructive-op confirmation discipline, and no irreversible action proceeds without an explicit operator selection.

**Pre-emission gate.** The Validation Gate runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the freshened tree and the changelog before the report is finalized. The gate attestation block is recorded inside the report. Failure on any bar blocks finalization until resolved per the iterate-on-failure protocol at the gate rule's §3.

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (freshening a target repository and emitting the freshening report). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE to publish, tag, or push — the command freshens a working tree, it does not release. REFUSE any irreversible action that has not cleared its per-target confirmation. REFUSE to name a forge, registry, or continuous-integration vendor in any emitted artifact — the agnostic boundary is non-negotiable.

### Output Surface

The freshened tree is modified in place by default. The freshening report lands at the consuming suite's `_outputs/freshify-report.md` per the suite-locality invariant at `rules/canonical-layout.md` §2.2; an optional sweep inventory lands at `_inputs/freshify-inventory.md`. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.py` is therefore NOT invoked on the report. Host source files the command freshens retain or receive the canonical SPDX header per the `rules/host-discovery.md`-discovered comment family. NEVER write the report outside the suite folder; NEVER write to a global plans directory under any harness's config root; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

When the command edits a host source file in place, it preserves the host's ratified idioms per `rules/host-discovery.md` and the canonical SPDX header per the discovered comment family. The freshening report is header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector on its own emissions. When a removal cites a surface, the citation is documentary (`file:line`); a removed back-reference is named before deletion.

### Structured Inquiry on Ambiguity

When uncertain about the ignore manifest's contents, the quality-gate command set, the changelog format, the versioning scheme, whether a narrative passage is legacy-and-removable or current-and-load-bearing, or any destructive-step target, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate a removal — every removal cites a concrete `file:line` plus the freshening rationale, and every irreversible removal clears its per-target confirmation first.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | Root directory of the target repository. MUST contain a root manifest plus the host's ratified ignore manifest, so the generated-state surface resolves. The command refuses execution when no freshening surface resolves. |
| `--purge-caches` | Flag | No | Opt in to the destructive cache-and-artifact purge. Without the flag, the cache sweep reports the purge targets and routes a per-target confirmation before any deletion; the flag pre-authorizes the purge but still records each target in the report. |
| `--rewrite-history` | Flag | No | Opt in to the destructive version-control-history rewrite that strips stale run traces from history. Without the flag, the history sweep reports the rewrite scope and routes a confirmation; the rewrite never proceeds on a shared branch without explicit operator selection. |
| `--normalize-naming` | Flag | No | Opt in to the destructive file / folder rename pass that normalizes naming to the host's ratified convention. Without the flag, the naming sweep reports the off-convention targets and routes a per-target Rename / Move confirmation before any rename; the flag pre-authorizes the rename pass while still recording each target and propagating every inbound reference in the same change-set. |
| `--strict` | Flag | No | Promote every advisory freshening finding to a blocking finding. Under `--strict`, the freshening is complete only when zero stale traces, zero off-convention names, zero non-natural narrative, and zero blocked gates remain. |

---

## Workflow — Six Freshening Stanzas

1. **Cache and stale-artifact sweep.** Read the host's ratified ignore manifest as the source of truth for generated state per `rules/host-discovery.md`, then enumerate every cache and artifact tree it declares — extend the class comprehensively per the "etc." extension rule (coverage databases, type-check / lint / test caches, dependency-resolver caches, rendered-documentation output, temporary scratch, editor swap files, log files, packaging staging). Report each enumerated target. The purge is destructive: route a per-target confirmation per `rules/interactive-questions.md` §6 before any deletion, with the in-place default being "retain, report only." The `--purge-caches` flag pre-authorizes the purge while still recording each target.
2. **Legacy-narrative and back-reference removal.** Sweep the narrative surfaces — the readme, the changelog, the contribution guide, the documentation tree, and the inline source comments — for prior-version, obsolete, legacy, and retired narrative; for back-references to superseded work; for placeholders; for refinement / fix / modification mentions that narrate process rather than product; and for the comprehensive sibling set those classes imply per the "etc." extension rule. Where the host ships harness components (skills, commands, agents, hooks, MCP surfaces), the staleness / orphanism / redundancy facet of this sweep is owned by the ecosystem-audit Harness-Component Alignment Dimension at `skills/ecosystem-audit/references/procedure.md` (a stale per-harness pin, an orphaned component, or near-duplicate cohort logic is a finding there) — `/freshify` references that dimension rather than re-deriving the per-harness-alignment checks. In-place rewriting to the current-product voice is the default. Each removal is destructive at the prose level: name the removed passage (`file:line`) and route a confirmation per `rules/interactive-questions.md` §6 when the passage is judgment-dependent rather than mechanically obsolete; mechanically-dead back-references (a link to a removed file) are repaired in place under the carve-out at `rules/authority-inquiry.md`.
3. **Naming uniformity and naturalism-coherence sweep.** Normalize file and folder naming to the host's ratified convention discovered per `rules/host-discovery.md` (kebab-case / snake_case / the host's observed sibling pattern) — every off-convention name across the whole tree is a rename target. Drive narrative jargon to natural, human-authored product prose per `rules/plain-language.md`, and reconcile naming and prose to one coherent voice per `rules/persistent-conventions-vigilance.md`. A rename is destructive at the path level: route a per-target Rename / Move confirmation per the `rules/interactive-questions.md` §6.5 Rename / §6.6 Move canonical option sets before any rename, with the in-place default being "report only," and propagate every inbound reference (imports, links, registry rows, manifests) in the same change-set per `rules/propagation.md` so the rename leaves no broken reference. The `--normalize-naming` flag pre-authorizes the rename pass while still recording each target and its propagated references.
4. **Current-version-only facade enforcement.** Drive the public surfaces to a current-version-only state: one current version declaration, narrative that references the current product rather than its history, and a concise current-version changelog entry curated per the host's ratified changelog format. Stale run traces and history narrative are removal candidates. A version-control-history rewrite that strips stale traces is destructive: route a confirmation per `rules/interactive-questions.md` §6 with the in-place default being "leave history intact, freshen the working tree only," and never rewrite a shared branch without explicit operator selection. The `--rewrite-history` flag pre-authorizes the rewrite while still recording the scope.
5. **Drive all gates to green — relentlessly, until 100% green.** Discover and run the host's ratified quality gates per `rules/host-discovery.md` — the formatter, the linter, the type-checker, the test runner, the documentation build, and the security scan declared in the manifest and the host's continuous-integration surface. Run the diagnose → root-cause-fix → re-run cycle **relentlessly across every gate until each one exits 100% green** and, where the host defines a scoring surface, sits at its ratified maximum — no gate left red, no gate skipped, no gate softened. The relentless loop is bounded for iteration safety per `rules/planning-techniques.md` §1: the diagnose-fix-rerun cycle caps at a default of three root-cause attempts per gate, and a gate still red at the cap is NOT softened or suppressed — it escalates as a blocking finding through the structured-inquiry channel per `rules/interactive-questions.md` §3 with its root-cause diagnosis and a defined retreat (operator decision or a `[Deferral]`-with-rationale), never a silent pass. No fix suppresses a gate; every fix addresses the root cause per `rules/operational-mandates.md` CM-8.
6. **Trace-free production-ready culmination.** Re-sweep the freshened tree to confirm zero residual caches, zero stale artifacts, zero legacy or obsolete narrative, zero back-references, zero placeholders, zero process-narration mentions, zero off-convention file / folder names, zero non-natural narrative jargon, and zero stale run or history traces — extended comprehensively per the "etc." extension rule. Confirm every rename and removal propagated to its inbound references in the same change-set per `rules/propagation.md` so no broken reference remains and every freshened surface is highlighted where future readers — AI coding agents and end users alike — will find it. Run the Validation Gate (the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md`) against the freshened tree and the changelog. Emit the freshening report with the per-gate verdict, the per-axis attestation, every confirmation outcome, and the sweep's `verified:` date. The culmination is fresh and production-ready when the re-sweep is clean, every change is propagated, and every gate is green.

---

## Mandates

| Mandate | Application |
| ------- | ----------- |
| **M15 — Production-Ready** | The freshening operationalizes `rules/production-ready-prs.md` — the current-version-only facade, the concise current-version changelog, and the green quality matrix are its pass conditions. |
| **M1 — Host Agnosticism** | Every forge, registry, and continuous-integration surface is discovered per `rules/host-discovery.md`, never named; the command carries no forge- or registry-specific token. |
| **M5 — Authority** | Every ambiguity in the ignore manifest, the gate command set, the changelog format, or the versioning scheme routes through `rules/authority-inquiry.md`; every destructive step clears a per-target confirmation per `rules/interactive-questions.md` §6 before acting. |
| **M2 — Plain-language** | Removed process-narration (refinement / fix / modification mentions) is replaced with current-product voice per `rules/plain-language.md`; the freshened narrative reads as human-authored product copy. |
| **Naming & convention coherence** | File / folder naming is normalized to the host's ratified convention and reconciled to one coherent voice per `rules/persistent-conventions-vigilance.md`; every off-convention name is a rename target cleared through the per-target Rename / Move confirmation. |
| **Propagation** | Every removal and rename propagates in the same change-set to every dependent reference across the whole reference graph per `rules/propagation.md`; emerging or existing merits / features / changes are highlighted everywhere applicable so both AI coding agents and end users understand the freshened project. |
| **M4 — Self-Application** | The freshened tree and the changelog pass the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` before the report is finalized. |

---

## Output

- The freshened working tree (in-place by default), with every confirmation outcome recorded.
- The concise current-version changelog entry curated per the host's ratified changelog format.
- The freshening report at `_outputs/freshify-report.md` (executive summary + per-stanza sweep results + removal index + confirmation log + per-gate green/blocked verdict + per-axis attestation + validation-gate attestation + bindings).
- An optional sweep inventory at `_inputs/freshify-inventory.md` (the Input Ingest read inventory).

---

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-22 %%
%% provenance: commands/freshify.md §Workflow %%
%% cross-reference: rules/production-ready-prs.md §1-§4 (production-ready discipline) %%
flowchart TD
    Start[Target repository ingested] --> Q1{Cache or stale-artifact targets found?}
    Q1 -->|yes| C1[Route per-target confirmation · default retain-and-report · purge on opt-in]
    Q1 -->|no| Q2
    C1 --> Q2{Legacy narrative or back-references found?}
    Q2 -->|mechanically dead| Repair[Repair in place · carve-out auto-decision]
    Q2 -->|judgment-dependent| C2[Route confirmation · name removed passage]
    Q2 -->|none| QN
    Repair --> QN
    C2 --> QN{Off-convention names or non-natural narrative?}
    QN -->|off-convention name| CN[Route Rename/Move confirmation · propagate inbound refs · rename on opt-in]
    QN -->|non-natural narrative| RN[Rewrite to natural product voice in place]
    QN -->|none| Q3
    CN --> Q3
    RN --> Q3{Facade current-version-only?}
    Q3 -->|history rewrite needed| C3[Route confirmation · default freshen working tree only]
    Q3 -->|working-tree freshen suffices| Q4
    C3 --> Q4{All host gates green?}
    Q4 -->|no| Fix[Apply in-place root-cause fix · re-run gate]
    Fix --> Q4
    Q4 -->|yes| Q5{Re-sweep trace-free · all refs propagated?}
    Q5 -->|residual trace| Q1
    Q5 -->|clean| Done[Run validation gate · emit freshening report]
```

---

## Recommended Next Step

**Invoke the forge-specific specialization `/github-deploy-fresh`** against the freshened tree to layer the source-forge deployment surface onto this agnostic freshening core, then publish the current-version release through the host's discovered release facade.

## Bindings (§0.j five-direction)

- **Drives →** The freshened working tree and the current-version changelog (consumed by the release decision). The forge-specific specialization `/github-deploy-fresh` (this agnostic core is the substrate the specialization extends). The six freshening stanzas (cache sweep · legacy-narrative removal · naming-uniformity and naturalism-coherence sweep · facade enforcement · drive-gates-green · trace-free culmination). The same-change-set propagation of every removal and rename across the whole reference graph per `rules/propagation.md`. The fifteen-bar pre-emission gate at the Validation Gate.
- **Satisfies →** The consuming suite's freshening slot. The `commands/README.md` command catalog's Deployment/elevation row for `/freshify` (the registry entry that ratifies this command's place in the slash-command catalog). The M15 production-ready discipline's current-version-only facade surface.
- **Established by ↑** The `commands/README.md` command catalog. `rules/production-ready-prs.md` (the production-ready discipline this command operationalizes). `rules/host-discovery.md` (the discovery surface every forge, registry, and gate command resolves through). `rules/cognitive-identity.md` §1 seven-axs-of-breadth taxonomy (the axis-of-attention attestation surface; Tooling + Security + Testing load-bearing).
- **Gated by ←** The repository's freshening-surface presence (a root manifest plus the host's ratified ignore manifest). The host's ratified targets discovered at Input Ingest (the ignore manifest, the quality-gate command set, the changelog format, the versioning scheme). The per-target confirmation contract (every destructive step clears a structured-inquiry confirmation before acting). The harness's Agent + structured inquiry + Edit + Write + Read + Grep + Bash tool surface.
- **Cross-bound with ↔** `rules/production-ready-prs.md` (the M15 discipline this command's facade enforcement and quality-matrix stanza verify). `rules/host-discovery.md` (M1 — every forge, registry, and gate surface is discovered, never named; the agnostic boundary's enforcement surface). `rules/interactive-questions.md` (§6 — every destructive step's per-target confirmation routes through the structured-inquiry channel). `rules/authority-inquiry.md` (every ambiguity routes through the canonical channel; mechanically-dead back-references repair under the carve-out). `rules/plain-language.md` (process-narration removal restores the current-product voice; narrative jargon driven to natural product prose). `rules/persistent-conventions-vigilance.md` (file / folder naming normalized to the host's ratified convention and reconciled to one coherent voice). `skills/ecosystem-audit/references/procedure.md` (the Harness-Component Alignment Dimension that owns the staleness / orphanism / redundancy facet for shipped harness components — referenced from Stanza 2, never re-derived). `rules/freshness-facade.md` (the current-version-only facade; no backward-compatibility, legacy, staleness, or process-refinement narrative on any surface). `rules/propagation.md` (every removal and rename propagates in the same change-set to every dependent reference; emerging merits highlighted everywhere applicable). `rules/etc-extension.md` (the "etc." extension rule — every trace class is grown comprehensively). `rules/pre-emission-gate.md` (fifteen-bar validation). `rules/cognitive-identity.md` (the seven-axs taxonomy). The forge-specific specialization `/github-deploy-fresh` (consumes this freshened tree; layers the deployment surface this agnostic core deliberately omits).
