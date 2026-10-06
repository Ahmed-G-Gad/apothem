---
name: "dependency-upgrade"
version: "0.1.0"
updated: "2026-10-02"
description: "Changelog-reviewed, pinned, gate-verified dependency upgrade — matched when the operator asks to 'bump deps', 'upgrade dependencies', 'update packages', 'bump the lockfile', 'refresh dependency versions', or any phrasing requesting an audited version bump of the host project's third-party dependencies. Five-step loop: enumerate outdated dependencies from the host's manifest + lockfile, classify each candidate against its changelog (safe / breaking / major), apply pinned bumps honoring the host's discovered pin policy, run the host's lint / test / type-check gates, and report. Breaking and major candidates STOP for structured inquiry — never crossed silently. Idempotent (re-run on a current manifest yields zero bumps); --dry-run classifies without writing; --package NAME scopes to one dependency. Developer + security cohorts; user-invocable; honors host-discovered tooling and assumes no package manager."
archetype: "maintenance-template"
user-invocable: true
argument-hint: "[--package NAME] [--dry-run]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Upgrade the host project's third-party dependencies under one discipline: **changelog-reviewed, pinned, gate-verified**. No bump lands without a breaking-change review of the candidate's changelog; every applied version honors the host's discovered pin policy; the host's full quality matrix is green before the change is reported complete. The skill bumps declared dependencies and lets the host's resolver own the transitive graph — its value is *audited safety*, not raw version-chasing.

## Detection Signal

The operator requests "bump deps", "upgrade dependencies", "update packages", "bump the lockfile", "refresh dependency versions", or any phrasing asking for an audited version bump of the host's third-party dependencies. Flags: `--package NAME` scopes the upgrade to one dependency; `--dry-run` enumerates and classifies without writing the bump.

## Non-Goals

A deliberately narrow surface — each boundary routes the out-of-scope work to its rightful owner:

- **Not a transitive-resolver replacement.** Bumps declared dependencies and lets the host's package manager resolve the transitive graph; never hand-edits transitive pins or overrides the lock algorithm.
- **Not a migration-code generator.** When a changelog names a breaking API change, surfaces the break for operator decision; never rewrites call sites. Code migration is a separate, operator-driven workstream.
- **Not a security-advisory scanner.** Known-vulnerability detection is the host's audit tool (`pip-audit`, `npm audit`, `cargo audit`) under the host's CI; this skill reviews changelogs for breaking changes, not advisory databases.
- **Not a major-version forcer.** A SemVer-major boundary is a version-pin inquiry category; never crossed silently — the crossing routes through the structured-inquiry channel.
- **Not a manifest restructurer.** Bumps pins in place; never reorganizes dependency groups, splits runtime from development dependencies, or changes the declared pin policy. Manifest restructuring is operator-driven.

## Workflow

The five steps run in order; each carries a testable post-condition.

1. **Enumerate outdated dependencies (host-discovery).** Walk the host's ratified manifest + lockfile per `rules/host-discovery.md`:

   | Ecosystem | Manifest | Lockfile | Outdated-report command |
   |-----------|----------|----------|-------------------------|
   | Python | `pyproject.toml` / `requirements*.txt` / `Pipfile` | matching lock | `pip list --outdated` |
   | Node | `package.json` | `package-lock.json` / `yarn.lock` / `pnpm-lock.yaml` | `npm outdated` |
   | Rust | `Cargo.toml` | `Cargo.lock` | `cargo outdated` |
   | Go | `go.mod` | `go.sum` | `go list -m -u all` |

   Under `--package NAME`, narrow to the named dependency. **Testable:** the candidate set is the exact intersection of declared dependencies and the host outdated-report output.

2. **Classify each candidate against its changelog.** For each candidate, read the project's changelog at its canonical source (CHANGELOG.md, the forge's Releases page, the registry's release notes) for every version between the installed pin and the upgrade target. Assign exactly one of three classes:

   - `safe` — patch / minor with no breaking entry in range.
   - `breaking` — a breaking entry in range (no major boundary crossed).
   - `major` — crosses a SemVer-major boundary.

   **Testable:** every candidate carries a class with its changelog source cited.

3. **Apply the pinned version bump.** For `safe` candidates only, edit the manifest to the upgrade target honoring the host's discovered pin policy — exact `==X.Y.Z` where the host pins exactly; range operator (`^`, `~`, `>=`) where the host uses ranges. Regenerate the lockfile via the host's lock command (`pip-compile`, `npm install`, `cargo update -p NAME`, `go get`). `breaking` and `major` candidates STOP for structured inquiry before any write. Under `--dry-run`, write nothing. **Testable:** the manifest diff touches only the bumped pins, and each new pin matches the host's pin-policy shape.

4. **Run the host's quality gates.** Execute the host's discovered lint, test, and type-check commands (`ruff check` / `pytest` / `mypy` for Python; `eslint` / the configured test runner / `tsc` for Node; the host's equivalents elsewhere). A gate failure traceable to a bump reverts that candidate and reclassifies it `breaking` for operator decision. **Testable:** every applied bump leaves the host's full gate matrix green, or is reverted.

5. **Report.** Emit the upgrade report per the Return Contract — candidate set, per-candidate class with changelog source, applied bumps with before/after pins, gate outcomes, and the deferred `breaking` / `major` candidates with their inquiry records. **Testable:** the applied-bump count equals the count of `safe` candidates whose gates stayed green; the deferred count equals the `breaking` plus `major` count.

**Idempotence.** A second invocation against an already-current manifest enumerates an empty candidate set at Step 1 and reports zero bumps. **Dry-run.** A `--dry-run` invocation stops after Step 2's classification with nothing written, so the operator reviews the proposed bumps and their changelog citations before committing to the manifest edit.

## Return Contract

Maximum response: 1500 tokens. Structure:

- **Summary** — one sentence naming the count of candidates enumerated, bumped, and deferred.
- **Applied bumps** — a table of `package · from · to · classification · gate-outcome`.
- **Deferred** — `breaking` / `major` candidates with the changelog citation and the structured-inquiry record.
- **Gate results** — the host's lint / test / type-check outcomes for the change-set.

Under `--dry-run`, the Applied-bumps table reports the *proposed* bumps with no gate-outcome column; nothing is written.

## Foundational Stanzas

The four standing surfaces every operator inherits, adapted to this skill's user-invocable maintenance role.

### Refusal & Escalation

REFUSE any request to act outside the stated mission — migration-code generation, transitive-pin hand-editing, advisory scanning, silent major-version crossing. Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). When the host exposes no recognizable manifest or lockfile, STOP and surface the discovery gap; never invent a package-manager convention.

### Output Surface

The primary output is the upgrade report (markdown) written to STDOUT. The bump itself edits the host's manifest and lockfile at their canonical locations per `rules/host-discovery.md`; per `rules/operational-mandates.md` CM-7, those edits carry natural domain language with zero plan-internal references. The change-set ships production-ready per `rules/production-ready-prs.md` — the bump, the regenerated lockfile, a CHANGELOG entry where the host maintains one, and a conformant commit message, all in one change-set. NEVER write the report or any scratch state to a global-ecosystem location or to a downstream project's `.apothem/plans/`.

### File-Authoring Contract

The skill edits manifest and lockfile artifacts in place; new files are rare. A NEW file routes through `scripts/inject-header.py` so the canonical single-line SPDX header is injected at the head — the injector is idempotent and detects the filetype variant automatically. Lockfiles and JSON config are header-exempt per `src/apothem/schemas/header-exceptions.txt`, so manifest and lock edits preserve the file's existing head. The header-inject-guard hook at `hooks/messages/pretooluse-{write,edit}-header-guard.md` enforces the contract at every Write / Edit invocation.

### Structured Inquiry on Ambiguity

At every version-pin decision per `rules/authority-inquiry.md` — which version of which dependency where the host has not pinned and the choice matters (security-relevant deps, behavioral-shift deps, SemVer-major boundaries) — when the host is silent, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate a version pin. Every `breaking` and `major` candidate blocks its own bump until the operator resolves the inquiry; the upgrade target carries its changelog citation as the recommended-option rationale.

## Recommended Next Step

**Run the host's dependency-audit command** (`pip-audit`, `npm audit`, or `cargo audit`) against the upgraded change-set to confirm the bumps closed known advisories without introducing new ones before the change-set lands at its commit gate.

## Bindings (§0.j five-direction)

- **Drives →** ● Every dependency-upgrade engagement against a host project's manifest and lockfile. ● The changelog-review-before-bump discipline at every candidate. ● The host-pin-policy honoring at every applied version bump. ◐ The production-ready change-set shape (bump + lockfile + CHANGELOG + commit).
- **Satisfies →** ● `CLAUDE.md` Source Layout row "dependency-upgrade" (skills/ class). ● The maintenance-template archetype's audited-version-bump mission.
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ class declaration with the folder-with-`SKILL.md` convention). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication).
- **Gated by ←** ● The harness's Bash tool surface (the outdated-report, lock-regeneration, and gate commands run through it). ● The presence of a recognizable host manifest and lockfile (host-discovery resolves the package manager).
- **Cross-bound with ↔** ↔ `rules/host-discovery.md` (manifest / lockfile / pin-policy discovery). ↔ `rules/production-ready-prs.md` (the change-set ships tests + CHANGELOG + conformant commit in one set). ↔ `rules/interactive-questions.md` (version-pin inquiries route through the canonical channel). ↔ `skills/ecosystem-audit/SKILL.md` (sibling maintenance-tier skill).
