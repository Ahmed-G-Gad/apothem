<!-- SPDX-License-Identifier: MIT -->

# conformity

> **Role.** Pre-emission conformity validators. `gate.py` orchestrates a fleet of mechanical `*_grep` matchers (plus the link checker) against a Write/Edit input, returning a pass/fail verdict before the artifact is emitted.

## Orchestrator

| File | Purpose |
|------|---------|
| `gate.py` | The conformity-gate orchestrator — dispatches every matcher against a Write/Edit input and aggregates the verdicts. |
| `_git.py` | `run_git`, the one way the gate and its validators run `git` in a checked project: with the repository's program-running settings turned off on git's command line, fetching blocked, and git found only in full-path `PATH` entries. Private to this package. |
| `_grep_base.py` | Shared building blocks every `*_grep` matcher imports: the finding shape, the file-walk (`iter_tree_files`, which prunes nested git checkouts and the vendored, virtual-environment, cache and build-output trees), and the JSON envelope. Private to this package. |
| `_bounded_run.py` | `run_bounded`, the one place the package starts a program (a validator for the gate, git for `run_git`), with a time limit that holds for every program it starts: a Windows job object, or a session of its own elsewhere, ended on a stop, with a bounded wait for the output after it. Standard library only. Private to this package. |
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
| `binding_five_direction_grep.py` | Every rule, command, agent, and skill closes with a five-direction `## Bindings` section (hook messages: the three-direction subset). In an installed tree (a flat root holding `.apothem/support`), a rule or skill copy with no section is the shipped form and passes; a section that is present must be complete. |
| `always_on_budget_grep.py` | Always-on rule body token budget (the 500-token ceiling). Pointed at a rules directory, it also holds the loaded always-on set to `MAX_ALWAYS_ON_LOADED_BYTES` and the rule index to `MAX_INDEX_LOADED_BYTES`; the per-write check sees one file and enforces the body budget only. |
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
| `gate_evidence_grep.py` | Plan-suite gate claims that lack the command, the exit status or output, and the HEAD SHA the plan-execute gate-evidence contract requires, and fifteen-bar attestation blocks that omit a field of the rule's schema or give an `n/a` without a reason (advisory; `--strict` exits non-zero). |

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
  CLI-usage error (an unknown flag or validator name, a file or root that does
  not exist), kept distinct from `2` so a CI consumer can tell a findings block
  apart from a wrong invocation.
- **One command-line contract.** Every entry point parses its arguments with
  the shared parser in `_grep_base.py` (`make_parser`, `parse_path_input`,
  `parse_root_args`): `--help` prints usage and exits 0, and a usage error
  prints one line and exits 3 — never a traceback. A corpus walker resolves its
  root to an absolute path, so `.` and the absolute form inspect the same tree.
- **A walk from the root skips nested checkouts.** A corpus walker that walks
  from the root reads the checkout it was pointed at: it skips every nested git
  checkout (a directory holding a `.git` file or directory, such as a worktree
  under `.claude/worktrees/`, a submodule, or a nested clone) and the vendored,
  virtual-environment, cache and build-output trees (`node_modules`, `_vendor`,
  `venv`, `dist`, `.next`; the set is `PRUNED_SEGMENTS`), through
  `iter_tree_files` in `_grep_base.py`. Six validators walk that way:
  `agents-md-coverage-grep`, `agnosticism-grep`, `dynamism-grep`,
  `freshness-token-grep`, `plain-language-grep` and `reference-token-grep`; the
  stray-suite sweep in `no-global-plans-grep` stops at a nested checkout through
  `has_git_entry` and keeps its own skip list. A walker confined to one fixed
  subtree (`naming-grep` under `src/apothem/`, `redundancy-grep`, a plan suite's
  own files) reads everything below that subtree.
- **Every git call goes through `run_git`.** The project being checked can come
  with a `.git` folder someone else wrote, and its `.git/config` can name a
  program for git to start (`core.fsmonitor`, a signature program, a second git
  in a submodule, a lazy-fetch transport). `run_git` in `_git.py` turns those
  settings off on git's command line, blocks fetching, and starts git only from
  a full-path `PATH` entry. A matcher starts no program itself and names no
  git program. `_bounded_run.py` is the one module that starts a program:
  `run_git` starts git through its `run_bounded`, and gate.py's validator
  launcher starts Python through it.
  `test_no_conformity_module_starts_a_program_itself` is a tripwire for this
  rule, not a proof of it. It reads each module's source and fails on the forms
  it knows: any use of `subprocess` beyond its exception and result types, also
  under an `import ... as` name; the `os` functions that start a program;
  `which`, `find_git` and `git_argv`; an import of `ctypes`, `multiprocessing`
  or `pty`; a dynamic import, `exec` or `eval`; and a string naming the git
  program. It leaves out only this folder's own `_git.py` and
  `_bounded_run.py`, by path. Code that builds a call from computed names can
  still pass it, so review a new matcher against the rule as well.
  `run_git` reads file contents with `git cat-file blob`, never `git show`,
  which would show a submodule entry as a commit. Read a path list with `-z`
  and `file_names=True`, and split it with `split_names`: read as text, a
  carriage return in a name becomes a line feed and a byte that is not UTF-8
  becomes U+FFFD, and the changed name matches no file. Before a name from
  such a list goes back to git as an argument, ask `reaches_git_unchanged`,
  and report a name that fails it with `GitNameError`; never skip it.
  `tests/conformity/test_project_git_settings.py` plants each setting and drives
  every git-reading path, so a new one belongs in its `_drive_every_gate_git_call`.
- **No vacuous pass.** A corpus walker's report carries `inspected` (how many
  targets it examined), stamped by `finish_root_report`. A run that inspected
  nothing fails unless the walker declares `empty_scope_expected` (a plan-suite
  walker on a checkout without the gitignored plans tree, a workflow walker
  where no workflow directory exists yet).
- **No unfinished pass.** A check that could not finish does not pass either.
  Give every `run_git` call a timeout. `run_git` runs git through `run_bounded`,
  so the limit holds for every program git starts; `subprocess.run` would stop
  only git and, on Windows, then wait for every program that holds the output,
  such as the real git behind Git's launcher. Turn `subprocess.TimeoutExpired`
  into `GitTimeoutError`, and a git
  failure in a checkout the walker found into `GitFailedError`, both from
  `_grep_base.py`. `in_checkout` there says whether a folder is inside a
  checkout: it looks for a `.git` entry in the folder and in the folders above
  it, so a failure in a subfolder counts too, and it stops where git stops
  looking (a `GIT_CEILING_DIRECTORIES` folder, or another file system outside
  Windows). The messages name the command in fixed words and never repeat
  git's own output. A corpus walker hands that message to
  `finish_root_report(check_error=...)`, which stamps `check_error` and exits
  `2`, advisory or not. A timeout or a refused checkout is not the exempt state
  of a missing repository, a repository with no commit, or a host without git:
  the data is there but was not read, and a checked repository's own
  configuration can make git wait for ever or refuse to read it. The gate gives
  each standalone validator `STANDALONE_TIMEOUT_SECONDS` and reports one it had
  to stop with a `check_error` of its own.
- **Two layouts, one import surface.** `gate.py` runs from the package
  (`src/apothem/conformity/`) and from a harness install
  (`<harness>/.apothem/support/conformity/`, the PreToolUse hook). Its
  bootstrap registers the install's `support/` directory as the `apothem`
  package, so a per-Write matcher may import `apothem.conformity.*` and the
  standard library only; `apothem.lib` and the other engine subpackages are not
  shipped under `support/`.
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
   `check(content: str, path: Path | None = None) -> GrepResult` with a
   `run_grep(check, sys.argv)` entry; **corpus walker**:
   `check(root: Path) -> GrepResult` plus a `_main(argv)` that parses with
   `parse_root_args` and returns `finish_root_report(...)` with the walker's
   `inspected` count.
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
python -m mypy
```

Run `mypy` bare: this package is in the `[tool.mypy] files` strict scope, and
naming paths on the command line overrides that key — the earlier form here
type-checked everything except the package it was validating.

## Related

- [`hooks/`](../hooks/) — the dispatcher that fires the gate on PreToolUse Write/Edit events.
