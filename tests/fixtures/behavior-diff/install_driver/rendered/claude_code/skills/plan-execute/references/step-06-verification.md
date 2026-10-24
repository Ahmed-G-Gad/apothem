<!-- SPDX-License-Identifier: MIT -->

### Step 6: Verification

Deploy a Quality Team (CM-25A) for parallel verification items.

**6.1 — Universal Baseline:** Per-Phase Checklist (Preamble §8).

**6.2 — Phase-Specific:** Execute each verification assertion.

**6.3 — Outputs Check:** All deliverables complete and working.

**6.4 — Success Metric:** Confirmed. "Success looks like" matches reality.

**6.5 — Self-Review:** "Would a domain expert approve?"

**6.6 — Coherence Check (CM-15):** Implementation matches specs. Update plan files if a spec error is found.

**6.7 — Plan-Internal Isolation Check (CM-7):** Scan ALL codebase deliverables and development artifacts (per the protected-artifacts list in `CLAUDE.md` CM-7) for leaked plan-internal references (per the forbidden-terms list in `CLAUDE.md` CM-7). Any occurrence is a finding: remove and replace with natural domain-appropriate language. The entire codebase and its git history must read as if no plan ever existed.

**6.8 — Failure Remediation:** Diagnose, fix, re-run, commit (CM-13B). If unresolvable → mark BLOCKED, inform the user.

**6.9 — End-of-Phase Commit Gate (CM-13C) — code-bearing phases:** Verify ALL codebase changes from this phase have been committed. Run `git status` — if any uncommitted codebase modifications exist (source, tests, configs, schemas, build scripts, data, assets), commit them now with a domain-descriptive commit message. This gate ensures no codebase changes leak uncommitted across phase boundaries. Plan-suite files (PROGRESS.md, phase reports, PLAN-NOTES.md) remain at user discretion per CM-13 scope exclusion. **Non-code phases** carry no commit obligation: the phase's deliverables (research, writing, documentation-only artifacts) are recorded in the phase report (Step 7) rather than committed. When a non-code phase nonetheless produced version-controlled artifacts (e.g., a Markdown document checked into the repo), those artifacts ARE committed under this gate — the exemption covers the absence of a code deliverable, not the avoidance of committing artifacts the host tracks in version control.
