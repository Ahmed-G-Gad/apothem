<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror, spelled out inline so this command honors them without relying on cross-reference alone. Of all five `/plan` pipeline stages, this one carries the strictest destructive-op floor — execution is the surface where irreversible filesystem mutations land.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (executing the next pending phase of a generated, reviewed plan suite). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). REFUSE forced execution of a BLOCKED phase without operator-supplied rationale; REFUSE override of a FAIL scorecard at PUBLIC_LAUNCH (hard block, no override path). When a quality-gate failure exhausts the 2-cycle retry budget, halt and surface — never silently degrade.

### Output Surface

Plan-suite-internal updates (per-phase `phases/NN-topic/REPORT.md`, `PROGRESS.md`, `PLAN-NOTES.md`, the Handoff Manifest, the final `COMPLETION.md`) land at `<project-root>/.apothem/plans/{suite}/` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Codebase artifacts (source, tests, configs, schemas, build scripts, data, assets) go to their domain-natural locations under the host project per host-discovery (`rules/host-discovery.md`); the canonical layout is host-ratified, not invented. NEVER write a plan-suite artifact outside the suite folder, NEVER write a plan suite to a global plans directory under any harness's config root from a downstream-project context, and NEVER write to any other global-ecosystem location. Per `rules/operational-mandates.md` CM-7, codebase artifacts contain ZERO plan-internal references — natural domain language only.

### File-Authoring Contract

Every NEW codebase file the executor creates routes through `scripts/inject-header.{sh,py}` so the canonical authorship-header banner per `site/content/docs/reference/authorship-header.mdx` is injected at the head; the injector is idempotent and detects the filetype variant automatically from the byte-exact fixture at `src/apothem/schemas/authorship-header.txt`. The exempt classes (LICENSE, JSON configuration files, lockfiles, generated assets, vendored trees, `.audit/` ephemera, `<project-root>/.apothem/plans/` ephemera, `.keep` / `.gitkeep` markers, binary files) are enumerated at `src/apothem/schemas/header-exceptions.txt`. Plan-suite artifacts (REPORT.md, PROGRESS.md updates, PLAN-NOTES.md updates) are header-exempt under the `.apothem/**` exception class. Edits to existing files preserve any existing banner; the header-inject-guard hook at `hooks/messages/pretooluse-{write,edit}-header-guard.md` enforces the contract at every Write / Edit invocation.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or about any branch-point, deletion decision, or judgment call that materially affects the outcome — route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. **Per-file destructive-op floor.** Every delete / rename / move / overwrite-without-retention / revert-uncommitted operation routes through the structured-inquiry channel on a per-file basis per `rules/interactive-questions.md` §6 — one invocation per file, every time, no `multiSelect` batching across files, every option's `default-pointer:` carries the verbatim `no-default: user decision required` marker. Confirmation fatigue is an accepted cost; silent destruction is not. The §6.4 Delete / §6.5 Rename / §6.6 Move / §6.7 Revert canonical option sets are the floor.
