<!-- SPDX-License-Identifier: MIT -->

# conformity

> **Role.** Pre-emission conformity validators. `gate.py` orchestrates a fleet of mechanical `*_grep` matchers (plus the link checker) against a Write/Edit input, returning a pass/fail verdict before the artifact is emitted.

## Orchestrator

| File | Purpose |
|------|---------|
| `gate.py` | The conformity-gate orchestrator — dispatches every matcher against a Write/Edit input and aggregates the verdicts. |
| `_grep_base.py` | Shared building blocks every `*_grep` matcher imports: the finding shape, the file-walk, and the JSON envelope. Private to this package. |
| `__init__.py` | Package marker. |

## Matcher families

### Authorship & structure

| File | Checks |
|------|--------|
| `file_header_grep.py` | Canonical authorship-header presence and form. |
| `frontmatter_grep.py` | Required frontmatter fields on artifact classes that carry them. |
| `frontmatter_value_grep.py` | Frontmatter `enum`/`pattern` values against the per-class JSON Schema (agents, commands, skills) — the value-level counterpart to `frontmatter_grep`'s key check. |
| `naming_grep.py` | Naming-convention conformance. |
| `binding_reciprocity_grep.py` | Reciprocal five-direction bindings — half-edge detection. |
| `binding_reciprocity_corpus_grep.py` | The same reciprocity check run across the whole artifact corpus rather than a single Write/Edit input. |
| `always_on_budget_grep.py` | Always-on rule body token budget (the 500-token ceiling). |
| `agent_capability_grep.py` | Every harness declares its agentic-capability matrix. |
| `agents_md_coverage_grep.py` | Stale agent-companion files under the root-only AGENTS.md convention. |
| `registry_capability_consistency_grep.py` | Registry capability cells not backed by install / materializer / projection evidence. |
| `recommend_next_step_grep.py` | `## Recommended Next Step` block presence on command / skill terminal surfaces. |
| `determinism_grep.py` | Deterministic output shape across command and skill surfaces. |
| `no_toplevel_docs_grep.py` | A top-level `docs/` directory at the repository root. |

### Prose & narrative discipline

| File | Checks |
|------|--------|
| `hedging_grep.py` | Hedging vocabulary in prescriptive prose. |
| `option_annotation_grep.py` | Per-option `(Recommended)` label-to-body bind (H6): canonical capital postfix iff body `recommendation: recommended`, no spurious or lowercase postfix, at most one recommended option in a single-select set. |
| `completion_claim_grep.py` | Unsupported absolute-guarantee completion claims in cohort prose (spec §4.2 honesty) — e.g., "guaranteed to pass", "always works", "100% complete", "cannot fail". |
| `diagram_staleness_grep.py` | Diagram verification dates against the structure they abstract. |
| `multi_surface_coherence_grep.py` | Coherence across paired/multi-surface artifacts. |
| `plain_language_grep.py` | Mechanistic / harness-internal vocabulary in user-facing prose. |
| `token_efficiency_grep.py` | Filler phrases, throat-clearing openers, content-free qualifiers. |
| `redundancy_grep.py` | Substantively-duplicated paragraphs across the governed corpus. |
| `agnosticism_grep.py` | Harness bias and re-introduced enforcement presets in shipped surfaces. |

### Plans discipline

| File | Checks |
|------|--------|
| `no_global_plans_grep.py` | Writes to a global plans directory. |
| `plans_discipline_language_grep.py` | Plans-discipline language violations. |
| `orphan_output_grep.py` | Orphan outputs — no consumer / no index entry / no producer attribution. |
| `user_confirm_grep.py` | Unfilled `<USER-CONFIRM:…>` placeholders. |
| `plan_suite_structure_grep.py` | Plan-suite structure — suite-locality, closed vocabulary, numeric-prefix discipline. |
| `plan_next_step_consistency_grep.py` | Plan-suite infra files' Recommended-Next-Step footer consistency (advisory). |

### Code craft

| File | Checks |
|------|--------|
| `bare_except_grep.py` | Bare / overly-broad `except` clauses. |
| `commented_out_code_grep.py` | Commented-out code blocks. |
| `magic_number_grep.py` | Magic numbers in logic without named constants. |

### Supply chain & security

| File | Checks |
|------|--------|
| `secret_leak_grep.py` | Secret literals committed to source — vendor-prefixed credential patterns plus a high-entropy heuristic, with a canonical-banner allow-list. |
| `unpinned_action_grep.py` | Unpinned GitHub Actions `uses:` references. |
| `permissions_minimum_scope_grep.py` | Every workflow declares a minimum-scope `permissions:` block. |
| `harden_runner_grep.py` | Every workflow job opens with a conformant harden-runner step. |
| `workflow_concurrency_grep.py` | Concurrency group + per-job timeout discipline on workflows. |
| `cross_platform_matrix_grep.py` | CI declares a cross-platform OS × Python matrix. |
| `oidc_trusted_publishing_grep.py` | Release workflows publish with OIDC-signed build provenance; PyPI stays keyless (no `PYPI_API_TOKEN`). |
| `editorconfig_presence_grep.py` | Canonical `.editorconfig` present at the project root. |
| `gitattributes_presence_grep.py` | Repo-root `.gitattributes` carries the canonical contract. |

### Release & branding

| File | Checks |
|------|--------|
| `production_ready_pr_grep.py` | Same-change-set production-readiness discipline. |
| `license_author_consistency_grep.py` | Verifies the root LICENSE carries an author line. |
| `brand_mark_grep.py` | Brand-mark usage. |
| `smoke_install_grep.py` | Install-script smoke-check markers. |
| `copilot_instructions_presence_grep.py` | `copilot-instructions.md` presence. |
| `dynamism_grep.py` | Static-string version embeds in dynamism-required surfaces. |
| `static_version_grep.py` | Version-bearing sites resolve dynamically, not as static literals. |
| `semver_stability_grep.py` | Semver stability (the change-set-scoped M15 mechanical fraction). |
| `conventional_commit_grep.py` | HEAD commit messages against the Conventional-Commits grammar. |
| `freshness_token_grep.py` | Freshness-narrative phrases on shipped public surfaces. |

### Link integrity

| File | Checks |
|------|--------|
| `link_check.py` | Validate Markdown internal links against the on-disk reference graph. |

## Operating contract

`gate.py` is the single dispatch surface. It owns two matcher registries —
`GREP_MODULES` (per-Write matchers with a `check(content, path)` signature, run
on the Write/Edit body) and `STANDALONE_MODULES` (corpus walkers that take a
root directory and walk the tree, git index, or a fixed surface set) — plus the
CLI surface (`--all`, `--check <name>`, `--list`, `--hook`, `--strict`) and the
scope/short-circuit logic. The invariants a matcher must hold to:

- **Advisory by default.** The gate reports findings and exits zero so the write
  proceeds; strict blocking is opt-in via `--strict` or a truthy
  `APOTHEM_CONFORMITY_STRICT`. A matcher's standalone `to_json()` carries
  `"advisory": true`, and its CLI `_main` may exit non-zero on findings (the
  orchestrator treats the standalone exit code as the strict signal). Never
  hard-block a write from inside a matcher.
- **Exit codes.** `0` — clean, or advisory findings with strict off. `2`
  (`EXIT_FAIL`) — a blocking finding under `--strict`. `3` (`EXIT_USAGE`) — a
  CLI-usage error (an unknown validator name, an unresolvable argument), kept
  distinct from `2` so a CI consumer can tell a findings block apart from a
  wrong invocation.
- **Fail-open isolation.** The orchestrator wraps every matcher load and
  `check()` call; a raised exception is recorded and surfaced, never swallowed,
  and never fail-closes the write. Do not catch-and-suppress inside a matcher;
  let the orchestrator's boundary handle errors.
- **Dataclass result shape.** Matchers return a frozen `GrepResult` carrying
  `passed: bool` and `findings: list[Finding]`; `Finding` carries the surface,
  kind/issue, and a `detail` string. The orchestrator duck-types
  `getattr(result, "passed", ...)` and `result.findings`, so the field names are
  the contract.
- **Registry-name forms.** `STANDALONE_MODULES` entries are stored hyphenated
  (`reference-token-grep`) for CLI ergonomics; the on-disk filename is
  underscored (`reference_token_grep.py`). `GREP_MODULES` entries are
  underscored. `_resolve_validator` normalizes both forms.
- **Plan/scope short-circuits are gate-owned.** `.plans/` paths, out-of-scope
  writes, and harness runtime-state subtrees (`projects/`, `memory/`)
  short-circuit to a silent pass in the orchestrator. A per-Write matcher MUST
  NOT itself special-case `.plans/`; rely on the gate's `_is_plan_suite_path`
  short-circuit.
- Denylist/schema data a matcher consumes lives in [`../schemas/`](../schemas/),
  never inlined in the module.

## Adding or modifying a matcher

To **add a matcher**:

1. Author `<name>_grep.py` here. Define frozen `Finding` and `GrepResult`
   dataclasses; `GrepResult.to_json()` emits `"advisory": true`. Expose the
   entry callable — **per-Write**:
   `check(content: str, path: Path | None = None) -> GrepResult`; **corpus
   walker**: `check(root: Path) -> GrepResult` plus a `_main(argv)` that prints
   JSON and returns `EXIT_PASS` (0) / `EXIT_FAIL` (2).
2. **Register** in `gate.py`: add the underscored name to `GREP_MODULES` for
   per-Write, OR the hyphenated name to `STANDALONE_MODULES` for a corpus walker.
3. Add **fixtures and tests** under `tests/conformity/<name>/` (pass/fail cases)
   and a test module under `tests/conformity/`. For standalone walkers, also
   register the matcher in `tests/conformity/test_standalone_greps_inprocess.py`
   so it runs in-process in the suite.
4. Keep within the **per-grep wall-clock budget** (`PER_GREP_BUDGET_SECONDS` in
   `gate.py`); the hook has a 10s `PreToolUse` ceiling and the orchestrator flags
   any matcher approaching the per-grep budget as a watch item. Cheap structural
   scans run before expensive regex sweeps.

To **modify or remove a matcher**: keep the registry entry, fixtures, and the
in-process test list in sync in the same change-set; an orphaned entry or a
registered name with no script surfaces as a load error.

Validate every change here:

```bash
python -m apothem.conformity.gate --all .
python -m pytest tests/conformity
python -m ruff check .
python -m mypy src/apothem/cli/ src/apothem/harnesses/
```

## Related

- [`hooks/`](../hooks/) — the dispatcher that fires the gate on PreToolUse Write/Edit events.
