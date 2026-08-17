---
name: "incident-runbook"
version: "0.1.0"
updated: "2026-06-09"
description: "Author and execute operational incident runbooks — matched when the operator asks to 'write a runbook', define an 'on-call procedure', author 'incident response steps', document a 'recovery procedure', 'document recovery steps for a failing service', or capture the response sequence for a failing or compromised service. Produces a runbook in the canonical five-stage shape — Trigger → Diagnosis → Action → Verification → Rollback — where every Action step carries an explicit, paired rollback path and every irreversible Action sits behind a no-default confirmation gate. On execution, advances Diagnosis → Action → Verification in order, confirming each live-infrastructure Action through the structured-inquiry channel and STOPping at the first Verification failure to surface its rollback. Serves the developer and security cohorts. NOT for provisioning monitoring/alerting/dashboards, paging on-call rotations or opening incident channels, writing post-mortems or retrospectives, or batch-executing destructive remediation unattended. User-invocable directly."
archetype: "runbook-template"
userInvocable: true
argument-hint: "[--service NAME]"
disable-model-invocation: true
allowed-tools: "Read, Write, Edit, Glob, Grep, Bash"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Author and execute operational runbooks for a named service. Every runbook follows the canonical five-stage structure — **Trigger · Diagnosis · Action · Verification · Rollback** — and every Action carries an explicit rollback path the on-call operator can execute under pressure.

The product is a document an operator reaches for at 3 a.m. and trusts without hesitation: each step is concrete (names the exact command), ordered (the sequence is the procedure), and reversible (every Action has a tested inverse, or is named irreversible behind a confirmation gate).

## Detection Signal

Triggers when the operator asks to "write a runbook", define an "on-call procedure", author "incident response steps", document a "recovery procedure", or capture the response sequence for a failing or compromised service. Any phrasing that asks for the ordered operational steps an on-call engineer follows during an incident matches.

## Non-Goals

This skill carries a deliberately narrow surface. It is NOT:

- **Not a monitoring or alerting configurator.** The runbook names the trigger the operator observes; it does not provision dashboards, alert rules, or telemetry pipelines.
- **Not an incident-management platform.** It authors the procedure document; it does not page on-call rotations, open incident channels, or track timelines in a tracker.
- **Not a post-mortem writer.** The runbook is the forward-acting recovery procedure, not the retrospective. Post-incident analysis lands in a separate document.
- **Not a remediation auto-runner.** When executing a runbook, the skill performs each Action against live infrastructure only after the operator confirms via the structured-inquiry channel; it never batch-executes destructive steps unattended.

## Workflow — Authoring

1. **Discover the service surface.** Walk the host's ratified source-of-truth files per `rules/host-discovery.md` to identify the named service (from `--service NAME` or inquiry), its deployment topology, health-check endpoints, log locations, and existing runbook conventions. Record each discovery with provenance.
2. **Author the Trigger stage.** State the observable condition that opens the incident — the alert name, the error-rate threshold, the failed health check, the security signal. The Trigger is a falsifiable observation, never a feeling.
3. **Author the Diagnosis stage.** Enumerate the ordered diagnostic steps that localize the root cause: the log queries to run, the metrics to read, the dependency checks to perform. Each step names the command and the expected signal that confirms or rules out a cause.
4. **Author the Action stage.** Enumerate the ordered remediation steps. Each Action step names the exact command or operation, the expected post-condition, and a one-line precondition that must hold before it runs.
5. **Author the Rollback stage — paired to every Action.** For each Action step, author the inverse operation that returns the service to its pre-Action state. An Action whose rollback cannot be executed because the operation is irreversible is named explicitly as irreversible, and that Action carries a `no-default: user decision required` confirmation gate per `rules/interactive-questions.md` §6. **Action–Rollback parity is the central invariant: no Action ships without a paired Rollback or an explicit irreversibility declaration.**
6. **Author the Verification stage.** State the ordered checks that confirm recovery: the health endpoint returns healthy, the error rate falls below threshold, the security signal clears. Each check names the command and the pass condition.
7. **Emit the runbook file.** Write the runbook to its host-natural location, route the new file through `scripts/inject-header.py`, and confirm every Action step has a paired Rollback step (or a declared irreversibility gate) before the file is considered complete.

## Workflow — Execution

When the operator asks to run an authored runbook, advance **Diagnosis → Action → Verification** in order:

- Run the Diagnosis steps and report which causes are confirmed or ruled out.
- For each Action step, confirm via the structured-inquiry channel before executing against live infrastructure; never batch live Actions.
- STOP at the first Verification failure and surface the paired Rollback path for the failed Action — do not advance past a failed verification.

## Return Contract

Maximum response: 800 tokens for authoring; unlimited when executing a runbook against live infrastructure. Structure:

- **Summary** — one sentence naming the service and the runbook's incident scope.
- **Stages emitted** — the Trigger / Diagnosis / Action / Verification / Rollback sections with their step counts.
- **Action–Rollback parity** — confirmation that every Action step carries a paired Rollback step, with any irreversible Actions named.
- **Surfaced gaps** — discovery gaps, missing endpoints, or unverifiable rollback paths (empty when none).
- **File path** — the canonical location the runbook was written to.

## Foundational Stanzas

The four standing surfaces every operator inherits.

### Refusal & Escalation

REFUSE any request that asks the skill to act outside its mission — provisioning monitoring, paging rotations, writing post-mortems, or batch-executing destructive remediation unattended. Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; free-form prose as primary input is forbidden). When an Action step has no executable Rollback and the operator has not confirmed the irreversibility gate, STOP — do not emit a runbook with an unguarded irreversible Action.

### Output Surface

The skill emits one runbook document per invocation at the host's ratified runbook location, discovered per `rules/host-discovery.md`. Planning artifacts go to `<project-root>/.apothem/plans/{suite}/`; NEVER write a plan-suite artifact to any global-ecosystem location. Runbook prose carries natural domain language per `rules/operational-mandates.md` CM-7 — zero plan-internal references.

### File-Authoring Contract

Every NEW file the skill creates routes through `scripts/inject-header.py` so the canonical `SPDX-License-Identifier: MIT` header is injected in the comment family matching the filetype; the injector is idempotent and detects the variant from the byte-exact fixture at `src/apothem/schemas/authorship-header.txt`. The exempt classes are enumerated at `src/apothem/schemas/header-exceptions.txt`. Edits to existing runbooks preserve any existing header.

### Structured Inquiry on Ambiguity

When the skill reaches a decision in any of the seven authoritative-data categories per `rules/host-discovery.md` and the host is silent — the service name, the deployment target, the health endpoint, the log location, the rollback mechanism — it routes the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden; NEVER fabricate authoritative data. Every Action step that deletes, restarts, scales down, or revokes against live infrastructure routes through the per-file destructive-op floor per `rules/interactive-questions.md` §6 — one invocation per operation, every option's `default-pointer:` carrying the verbatim `no-default: user decision required` marker.

## Recommended Next Step

**Invoke the `incident-runbook` skill via the Skill tool** with `--service NAME` to author the runbook for a named service, then execute its Verification stage against a staging deployment to confirm every step is orderable before the runbook reaches on-call.

## Bindings (§0.j five-direction)

- **Drives →** ● Every authored runbook's Trigger / Diagnosis / Action / Verification / Rollback structure. ● The Action–Rollback parity invariant at every emitted runbook. ● Every live-infrastructure Action step's destructive-op confirmation gate.
- **Satisfies →** ● The developer and security cohorts' need for tested, reversible operational procedures. ● `CLAUDE.md` Source Layout row "incident-runbook" (skills/ class).
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ folder-with-`SKILL.md` class). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication).
- **Gated by ←** ● The harness's Write / Edit / Bash tool surface. ● The host's discovered runbook conventions per `rules/host-discovery.md`.
- **Cross-bound with ↔** ↔ `rules/interactive-questions.md` (structured-inquiry channel; per-file destructive-op floor for live Actions). ↔ `rules/host-discovery.md` (service-surface discovery). ↔ `scripts/inject-header.py` (authorship-header injection). ↔ `src/apothem/schemas/header-exceptions.txt` (header-exempt classes). ↔ `skills/plan-suite/SKILL.md` + `skills/ecosystem-audit/SKILL.md` (sibling skills under the same registry section).
