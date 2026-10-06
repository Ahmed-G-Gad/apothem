---
name: "secret-rotation"
version: "0.1.0"
updated: "2026-10-02"
description: "Safe secret-rotation template — matched when the user says 'rotate a secret', 'a key leaked', 'a token leaked', 'a credential is exposed', 'revoke and re-issue this key', 'an API key was committed', or any phrasing that asks to safely retire and replace an exposed credential. Treats a leaked credential as compromised the moment it touched a tracked file and enforces the revoke-before-re-issue ordering invariant: detects the coarse exposure surface, revokes the compromised credential at its issuer FIRST, re-issues a least-privilege replacement, rewires configuration through env-var or secret-manager indirection (never plaintext), and verifies no plaintext residue remains in the working tree or version-control history. NOT a full secret-scanner (routes the broad sweep to the host's scanner), NOT an issuer client, NOT a history-rewrite engine. User-invocable directly."
archetype: "security-template"
userInvocable: true
argument-hint: "[--scope PATH]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Drive the safe rotation of an exposed secret end to end: detect the exposure surface, revoke the compromised credential at its issuer, re-issue a replacement, rewire configuration through indirection, and verify no plaintext residue remains.

The skill treats a leaked credential as **already compromised the moment it touched a tracked file**. This drives the one non-negotiable ordering invariant of the whole procedure: **revoke before re-issue.** A replacement minted before the leaked key is revoked leaves both keys live — doubling the attack surface instead of closing it. Every step downstream of detection assumes the leaked key is in an adversary's hands.

## Detection Signal

The user asks to retire and replace a compromised credential. Trigger phrases: "rotate a secret", "a key leaked", "a token leaked", "a credential is exposed", "an API key was committed", "revoke and re-issue this key".

**Incidental-discovery trigger.** The skill ALSO fires when the agent proactively discovers a committed credential mid-change during ordinary work — a plaintext key, token, or high-entropy secret in a tracked file that no user request named. An incidentally-found committed secret is routed here from `rules/production-ready-prs.md` §3 (supply-chain); the discovery itself is the signal, and the rotation procedure starts from step 1 without waiting for a user phrasing.

## Non-Goals

The skill carries a deliberately narrow surface. It is NOT:

- **Not a full secret-scanner replacement.** Detection is coarse — high-entropy strings, known key prefixes, and the host's ratified secret patterns. Exhaustive scanning is `gitleaks` / `trufflehog` territory under `conformity/secret_leak_grep.py` and the host's CI; this skill routes the broad sweep there and acts on the confirmed exposure.
- **Not an issuer client.** The skill names the revocation and re-issue steps the operator performs at the credential's issuer (cloud console, registry, identity provider); it does not hold issuer credentials or call issuer APIs on the operator's behalf.
- **Not a history-rewrite engine.** History rewriting (`git filter-repo`, BFG) is surfaced as an operator decision under the per-file destructive-op floor, never executed silently.

## Workflow

Five ordered steps. The order is the safety contract — step 2 (revoke) MUST precede step 3 (re-issue); the procedure NEVER mints a replacement while the leaked key is still live.

1. **Detect the exposure surface.** Glob the scope (`--scope PATH`, default project root) and Grep for the host's ratified secret patterns, known key prefixes, and high-entropy literals. Enumerate **every** file and line where the credential appears. Run `git log -p -S '<fragment>'` to find the historical commits that introduced or carried the secret. **Criterion:** the full surface — working tree AND history — is reported; the skill never acts on a partial enumeration, because a missed occurrence is a credential still leaking after rotation "completes".

2. **Revoke the compromised credential at its issuer — FIRST.** Direct the operator to revoke the leaked credential at its issuer (cloud console, registry, identity provider) before any other action. A live leaked key is an open door; revocation closes it before a replacement exists. **Criterion:** revocation is confirmed by the operator. The skill does NOT advance to step 3 on an unconfirmed revocation — STOP and re-confirm.

3. **Re-issue a replacement.** Direct the operator to mint a new credential at the same issuer with the **minimum scope** the workload requires (least-privilege, not a copy of the old grant). Capture the new value only into the step-4 indirection surface — **never echo it to STDOUT, never write it to a tracked file, never paste it into a report.** **Criterion:** a replacement exists and its value is held only behind indirection.

4. **Rewire configuration through indirection.** Replace every plaintext occurrence from step 1 with an env-var reference or a secret-manager lookup discovered per `rules/host-discovery.md` (the host's ratified `.env` convention, vault path, or cloud secret-manager). The replacement reads the value at runtime; the tracked source carries only the **reference**. **Criterion:** zero plaintext secrets remain in tracked config — every site reads through indirection.

5. **Verify no plaintext residue remains.** Re-run the step-1 sweep over the working tree and confirm **zero** plaintext hits. Re-run `git log -p -S '<fragment>'`; when the secret persists in history, surface the history-rewrite decision under the per-file destructive-op floor (one structured-inquiry invocation per affected ref, every option's `default-pointer:` carrying the verbatim `no-default: user decision required` marker). Confirm the new credential resolves through indirection and the workload reaches a working run. **Criterion:** working-tree sweep is clean, history disposition is decided (rewritten or operator-accepted-with-rationale), and the workload runs green on the replacement.

## Return Contract

Maximum response: 800 tokens. Structure:

- **Summary:** one sentence stating the credential rotated and its disposition.
- **Exposure surface:** every file / line / historical commit where the secret appeared.
- **Actions taken:** revocation confirmation, re-issue confirmation, indirection rewiring per file.
- **Residue verification:** working-tree and history sweep results; pending history-rewrite decisions.
- **Outstanding-obligation ledger** (when the rotation began from the incidental-discovery trigger): record that the secret was removed from the working tree in this change-set NOW, and that BOTH version-control-history rotation AND credential rotation at the issuer remain outstanding until steps 2, 3, and 5 confirm them.
- **Surfaced gaps:** out-of-axis concerns (deeper scan, related credentials) per M6. Empty: `none`.

## Foundational Stanzas

The four standing surfaces every operator inherits, adapted to this skill's user-invocable security role so the destructive-op floor is preserved across the rotation surface.

### Refusal & Escalation

REFUSE any request that asks the skill to act outside its mission — exhaustive secret-scanning, holding issuer credentials, silent history rewriting, rotating a credential the operator has not confirmed exposed. Refusal is explicit: name what was refused, name the mission boundary crossed, and surface escalation through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). When revocation cannot be confirmed, STOP before re-issue — a replacement minted beside a live leaked key doubles the exposure.

### Output Surface

The rotation report writes to STDOUT. NEVER write a captured secret value to a tracked file, a report, or STDOUT. Configuration edits land at the host's ratified paths per `rules/host-discovery.md`; indirection references replace plaintext in place. Audit-internal scratch lands under `.audit/` (gitignored-class per the canonical `.gitignore` snippet); NEVER write rotation working state to a global location.

### File-Authoring Contract

When the skill emits a NEW file (rare; the rotation path edits existing config in place), the file routes through `scripts/inject-header.py` so the canonical single-line SPDX license header is injected at the head; the injector is idempotent and detects the filetype variant automatically from the byte-exact fixture at `src/apothem/schemas/authorship-header.txt`. Exempt classes (LICENSE, JSON configuration files, lockfiles, generated assets, `.env` files, `.audit/` ephemera, binary files) are enumerated at `src/apothem/schemas/header-exceptions.txt`. Edits to existing config preserve any existing header.

### Structured Inquiry on Ambiguity

When the rotation reaches a decision in any of the seven authoritative-data categories per `rules/host-discovery.md` and `rules/authority-inquiry.md` — identity (credential owner), scope direction (which secret, which environment), preference (secret-manager choice), security (rotation cadence, allowed egress), naming of public surfaces, infrastructure endpoints (issuer, vault path), version pins — and the host is silent, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). NEVER fabricate authoritative data. The replacement landing in production-ready form — config rewired, no plaintext residue, workload green — satisfies the same-change-set discipline per `rules/production-ready-prs.md`. **Per-file destructive-op floor.** Every history-rewriting step (`git filter-repo`, BFG, force-update of a ref) and every delete / overwrite-without-retention of an exposed file routes through the structured-inquiry channel on a per-file (per-ref) basis per `rules/interactive-questions.md` §6 — one invocation per ref, every time, no `multiSelect` batching, every option's `default-pointer:` carries the verbatim `no-default: user decision required` marker.

## Recommended Next Step

**Run `python -m apothem.conformity.gate --all .`** to run the host's mechanical conformity corpus — which includes the secret-leak matcher — and confirm zero plaintext-secret residue after rotation. (To scope the secret-leak matcher to a single touched file, use `--check secret-leak-grep <path>`; the bare `--check secret-leak-grep .` directory form is not a runnable invocation.)

## Bindings (§0.j five-direction)

- **Drives →** ● Every exposed-credential rotation the operator invokes. ● Every plaintext-to-indirection config rewiring under the host's ratified secret surface. ◐ The per-ref history-rewrite decision under the destructive-op floor.
- **Satisfies →** ● `CLAUDE.md` Source Layout row "secret-rotation" (skills/ class). ● `rules/production-ready-prs.md` supply-chain-posture preservation (no secret literal in tracked source).
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ folder-with-`SKILL.md` convention). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication).
- **Gated by ←** ● The harness's tool surface (Read / Write / Edit / Glob / Grep / Bash). ● Operator confirmation of revocation before re-issue.
- **Cross-bound with ↔** ↔ `rules/host-discovery.md` (secret-manager and `.env` convention discovery). ↔ `rules/interactive-questions.md` (per-ref destructive-op floor on history rewrites). ↔ `rules/production-ready-prs.md` (supply-chain posture). ↔ `conformity/secret_leak_grep.py` (the mechanical sweep this skill routes to). ↔ `skills/ecosystem-audit/SKILL.md` (sibling skill under the same registry section).
