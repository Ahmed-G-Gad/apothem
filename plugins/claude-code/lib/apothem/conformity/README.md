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
| `_corpus.py` | The `--all-perwrite` file list and reader: lists the tracked files with `git ls-files` (with a time limit) and reads only the regular files inside the project, checking every level with `lstat` so no link, junction, named pipe or device is followed or opened, and naming the reason for every path it skips. `link-check` uses the same level check to keep a corpus run's link lookups inside the project. Private to this package. |
| `__init__.py` | Package marker. |
| `_project_paths.py` | The link-aware helpers every validator reads project files through: a walk entry, a fixed path or a folder listing is looked at without following a link, a link to a regular file inside the project counts for a fixed file, and every link or special file left out is noted for the report's `skipped_links`. Private to this package. |

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
  checkout (a directory whose `.git` file or directory holds or names a
  repository, such as a worktree under `.claude/worktrees/`, a submodule, or a
  nested clone; a plain `.git` file or an empty `.git` folder, which git does
  not take for a repository, does not hide its folder) and the vendored,
  virtual-environment, cache and build-output trees (`node_modules`, `_vendor`,
  `venv`, `dist`, `.next`; the set is `PRUNED_SEGMENTS`), through
  `iter_tree_files` in `_grep_base.py`. A nested `.git` file that names the
  root's own repository or one outside the root still hides its folder, as it
  does for git, but `nested_checkout` notes that `.git` file for
  `skipped_links`; a worktree or submodule, whose `gitdir:` line points into
  the root repository's `worktrees/` or `modules/` folder, stays silent. The
  paths are compared as written, so nothing beyond what `git_entry_state`
  reads is read. Six validators walk that way: `agents-md-coverage-grep`,
  `agnosticism-grep`, `dynamism-grep`, `freshness-token-grep`,
  `plain-language-grep` and `reference-token-grep`; the stray-suite sweep in
  `no-global-plans-grep` stops at a nested checkout through the same
  `nested_checkout` test and keeps its own skip list. A walker confined to one
  fixed subtree (`naming-grep` under `src/apothem/`, `redundancy-grep`, a plan
  suite's own files) reads everything below that subtree.
- **Every git call goes through `run_git`.** The project being checked can come
  with a `.git` folder someone else wrote, and its `.git/config` can name a
  program for git to start (`core.fsmonitor`, a signature program, a second git
  in a submodule, a lazy-fetch transport). `run_git` in `_git.py` turns those
  settings off on git's command line, blocks fetching, and starts git only from
  a full-path `PATH` entry. A matcher starts no program itself and names no
  git program. `_bounded_run.py` is the one module that starts a program:
  `run_git` starts git through its `run_bounded`, and gate.py's validator
  launcher (`_run_standalone`) starts Python through it. No other code calls
  `run_bounded`: it starts whatever it is given, with none of `run_git`'s
  options.
  `test_no_conformity_module_starts_a_program_itself` is a tripwire for this
  rule, not a proof of it. It reads each module's source and fails on the forms
  it knows, among them: a use of `subprocess` beyond its exception and result
  types, also under an `import ... as` name or through another module; the
  `os` functions that start a program; `which`, `find_git`, `git_argv`, and
  `run_bounded` outside its two callers; an import of `ctypes`, `_winapi`,
  `multiprocessing` or `pty`; `exec`, `eval` and the import-by-name calls; and
  a string naming the git program. It holds only this folder's own `_git.py`,
  `_bounded_run.py` and `_corpus.py`, by path, to rules of their own: in
  `_git.py` it checks that `run_git` alone calls `run_bounded`,
  `_bounded_run.py` must name no git and look no program up, and `_corpus.py`,
  which opens files on Windows, may import `_winapi` and `ctypes` but call only
  the few functions that open a file and read what it is. Code that reaches a starter some
  way the test does not know can still pass it: source text run through
  `runpy`, `timeit` or a profiler, an attribute fetched through `builtins`,
  `inspect` or `operator`, a `sys.modules` lookup by a computed name. So
  review a new matcher against the rule as well.
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
- **Project files only, never through a link.** The project being checked can
  come with files someone else made, so a validator opens and lists only
  regular files and real folders that it reaches through real folders below
  the root. It never follows a symbolic link or a Windows junction, and never
  opens a named pipe, a device or a socket; each counts as missing. Use the
  helpers in `_project_paths.py`, re-exported by `_grep_base.py`:
  `iter_tree_files` for a walk (`prune=False` where every file below a fixed
  folder counts, as `rglob` did), `project_file_target` to read a fixed file
  (it also accepts a link to a regular file inside the project, such as
  `CLAUDE.md`), `is_project_dir` before listing or globbing a fixed folder,
  `is_project_file` to filter a listing, `list_real_entries` in place of
  `iterdir`, `child_folder_files` in place of a `*/NAME` glob, and `path_kind`
  or `scan_entries` for a check that reports a name, such as a plans folder or
  a `docs` entry that is a link. Plain `is_file`, `is_dir` and `exists` follow
  links, `glob`, `rglob` and `iterdir` list a linked folder and return links,
  `os.walk` looks up the target of each symbolic link it lists, and on Python
  3.12 a `*/NAME` glob lists every child folder, a linked one too, so keep
  each glob to one level of a folder you checked. On Windows a name ending in
  a dot or a space is a special entry: Win32 drops that ending when a path is
  opened by name, so the reopened path could be a junction beside it. A
  check that reads no content, such as `naming-grep`, walks with
  `include_links=True` to see each link by its own name. The helpers note
  every link and special file they leave out, every folder `scan_entries`
  could not list (no access, a path too long), and the `.git` entry of a
  nested checkout the walk skipped when that entry is a link, a special file
  or a `.git` file that names the root's own repository or one outside the
  root; `finish_root_report` lists them under `skipped_links`. A run that
  inspected nothing while it left a link out does not pass, even when an
  empty scope is expected. The helpers look at each level and the caller
  then opens the file by name, so a writer racing the gate can swap a checked
  entry for a link or a named pipe before the open, or make a read wait until
  the time limit; only the `--all-perwrite` corpus opens without following the
  last level (`_corpus._open_binary`).
  `tests/conformity/test_validators_stay_in_project.py` runs every `--all`
  validator against a project made of links. Add each file a new validator
  reads to its `_project_files` (or, for a file read only after another one
  passed, to `_second_reads`): its control test fails only while the
  validator reaches none of those files, so a path left out is not tested.
  A check in the `--all` or `--all-perwrite` set that runs git calls
  `nearest_linked_git_entry(root)` from `_grep_base.py` first, does not run
  git when it returns an entry (`linked_git_message` gives the sentence that
  names it), never asks `in_checkout` before it, and passes `discover=True` to
  every `run_git` call. In `--all` and `--all-perwrite`, the gate itself opens
  only regular files inside the root, checking each folder on the way with
  `lstat`, including every path git lists, and never reads inside a `.git`
  entry. Before they run git, the checks that run it look with `lstat` at the
  `.git` entry of the root and of every folder above it that git searches, as
  the tree is at that moment; if any of them is a link, or cannot be looked
  at, they do not run git. This also refuses projects git would handle safely,
  such as every project below a home folder whose `.git` is a link, even one
  with its own repository: that is the deliberate cost of a simple rule. They
  run git without `GIT_DIR` and the other variables that name the repository,
  its stores or its index. Which repository git then reads is not checked: a
  `gitdir:` line, `commondir`, alternates, `core.worktree`, an include, or a
  link inside the git folder can name another one, and git follows them, so
  git can reach a network path or wait until its time limit. The gate uses
  git's output only as names, modes, status letters, the subject of the last
  commit, commit times and a few settings, and never opens a path git prints
  without checking each level inside the root. A `.git` entry the gate cannot
  look at (a path too long, a share it cannot reach, no access) is not a link
  and is not listed under `skipped_links`: `conventional-commit-grep` fails
  with the status `git-failed` and a `check_error`, the companion coverage
  check and `--all-perwrite` fail with a `check_error` that says the entry
  could not be looked at, and `no-global-plans-grep` reports it as a finding.
  The callers today are `_corpus.tracked_entries`,
  `no_global_plans_grep._git_ls_files` and `no_global_plans_grep.check`,
  `agents_md_coverage_grep._read_history`, and
  `conventional_commit_grep._read_head_subject`; `conventional-commit-grep`
  asks git itself (`rev-parse --show-prefix`) whether the work tree's top is
  above the root. The `--staged` checks (`production-ready-pr-grep` and
  `semver-stability-grep` with `--staged`), which are not part of `--all` or
  `--all-perwrite`, call `refuse_linked_git` on the folder git runs in before
  git runs; it raises a `GitCheckError`, which they report as `check_error`.
  Its sentence is the same, except for a link in the folder git runs in: a
  hook's `GIT_DIR` may name the repository git reads, so that sentence says
  only that the gate does not run git (`STAGED_LINKED_GIT_MESSAGE`). They run
  git without `discover=True`, so a hook's `GIT_DIR` still names the
  repository. `conventional-commit-grep` reports a link with the status
  `not-a-git-repo` and a `check_error` that names it.

- **No unfinished pass.** A check that could not finish does not pass either.
  Give every `run_git` call a timeout, far above what the command takes, since
  a timeout fails the check: the validators give each command 60 seconds and a
  read of the whole history 300. `run_git` runs git through `run_bounded`,
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
  `2`, advisory or not. A timeout or a refused checkout is not an exempt state
  (a missing repository, a repository with no commit, a host without git, or a
  partial clone, where `run_git` does not let git fetch what the clone left
  out and any failed history read counts as unavailable): the data is there but was not read, and a checked repository's own
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
