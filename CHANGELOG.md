<!-- SPDX-License-Identifier: MIT -->

# Changelog — Apothem

All notable changes to this project are documented in this file.

This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **A channel smoke workflow runs every documented install command
  anonymously.** `channel-smoke.yml` runs on a weekly schedule and on demand.
  Each of the eight install channels runs on a clean runner with only its
  documented prerequisites, an isolated home directory, no credentials, and
  Git prompts disabled, so a private repository, an unpublished listing, or a
  missing release asset fails the job instead of reaching a new user. The
  commands live in `scripts/dev/channel_smoke.py`, and a test keeps them equal
  to the README. The harness CLIs install from a hash-pinned lockfile.
- **The README explains the Qwen Code plugin prompt.** The repository is also a
  Claude Code marketplace, so Qwen Code asks which plugin to install;
  `qwen extensions install ahmed-g-gad/apothem:apothem --consent` installs
  without the prompt.

### Changed

- **The session-end protocol is now opt-in.** A `Stop` hook that returns
  context makes the assistant take another turn, so the protocol cost one extra
  turn in every session, whether or not the operator asked for it. Set
  `APOTHEM_SESSION_END_ENABLED=1` to enable it. It never fires on a stop that
  already follows a hook-driven continuation.
- **The proactive-compaction advisory fires at most twice per session** and
  can be silenced with `APOTHEM_PROACTIVE_COMPACTION_ENABLED=0`. Its
  model-facing text now asks only for state externalization; the compaction
  suggestion goes to the operator, who owns that action.
- **`APOTHEM_HOOKS_DISABLE=1` silences every dispatcher-routed hook**, for
  troubleshooting without editing installed files.
- **Commands and skills pre-approve read-only tools only.** `allowed-tools`
  names the tools a harness may run without asking while a command or skill is
  active. Every command declared the bare `"*"` wildcard, which Claude Code
  ignores, and 17 skills pre-approved unscoped `Bash`, `Write`, `Edit`, or
  `WebFetch`, so content fetched during a run could start them unprompted.
  Commands now declare `Read, Glob, Grep`, skills keep only their read-only
  tools, and the command and skill schemas reject `"*"` and bare `Bash`,
  `PowerShell`, `Write`, `Edit`, `NotebookEdit`, and `WebFetch`; the
  conformity gate enforces both schemas. Side-effecting tools still run under
  the operator's own permission settings.
- **`/freshify`, `/github-deploy-fresh`, and `/github-deploy-next` are
  operator-invoked only.** They purge caches and history, merge, tag, and
  publish, so they now set `disable-model-invocation: true`, and the model
  cannot start them from its own skill choice.
- **Hook guidance no longer carries maintainer text.** The license comment line
  and the `## Bindings` section of each message file are removed before the
  text reaches the assistant.

### Fixed

- **Path-filtered rules no longer load in every Claude Code session.** Claude
  Code reads only `paths:` from a rule and loads every rule without it at
  launch, so the engine install loaded all 91 rules (914,538 bytes) in each
  session. The install now writes each path-filtered rule with a `paths:` list
  built from its `pathFilter`; the 28 always-on rules (213,701 bytes) load at
  launch and the 63 companions load when a matching file is read.
- **Claude Code plugin hooks run on a plain checkout.** Each hook is
  registered once, as `bash "<plugin-root>/…/bootstrap.sh" <event>`, so no hook
  depends on a file's executable bit, and no tool call triggers the same hook
  twice. On Windows without Git for Windows, use the engine install, whose
  hooks need no shell.
- **Post-compaction recovery reaches the assistant on Claude Code.** Claude
  Code discards PreCompact and PostCompact hook output, so those registrations
  did nothing there. The recovery context now arrives with the SessionStart
  event that follows compaction. Codex and Qwen Code keep both events.
- **Shell guards cover PowerShell and Qwen Code.** The Claude Code matcher is
  `Bash|PowerShell`, and the Qwen Code matcher is `^run_shell_command$`, the
  tool id Qwen Code reports at runtime. The engine-installed Claude Code
  settings also deny the PowerShell forms of `git push --force`,
  `git push --force-with-lease`, `git push -f`, and `Invoke-Expression`.
- **The dependency and dynamic-eval guards speak only when relevant.** They
  fired on every write and every shell call. The dependency guard now needs a
  write to a dependency manifest or lockfile, and the eval guard needs an
  evaluation or unsafe-deserialization primitive in the content or command.
- **The strict AskUserQuestion guard blocks through the current channel.** It
  returns `permissionDecision: deny` with a reason, which Claude Code honors,
  instead of the deprecated top-level `decision` field.
- **Session-start memory lookup finds the project's memory index.** It keys on
  the project directory from the harness, ascends a payload working directory
  to its Git root, and honors `CLAUDE_CONFIG_DIR`. The plugin-alone pointer
  prints the resolved rules path instead of an unexpanded variable.

### Security

- **Hooks never run code from the opened project.** The bootstrap stubs
  resolve the dispatcher from their own installed location. Previously the
  stubs took their root from the project directory when it contained a
  `hooks/` folder, so a project could supply the interpreter locator or the
  dispatcher that the plugin's hooks then ran. Session-start guidance is read from the installed tree; the
  project is read only for plan and memory summaries.
- **Per-session hook state is private to the user.** The session-end gate and
  the compaction tracker kept counters in a shared directory under the system
  temp dir, created with default permissions. State now lives in a per-user
  directory created with mode `0700`, and session ids are sanitized before use
  as file names. `APOTHEM_HOOK_STATE_DIR` overrides the location.

## [1.1.0] - 2026-08-16

### Added

- **Per-folder README file coverage is now gated.** A folder's README is its
  operating contract, so its file table is load-bearing: a reader who cannot
  find a module there concludes it does not exist. Nothing held that table
  against the folder's actual contents, and the drift is invisible from both
  sides — you do not notice a missing row while reading, nor the README while
  adding a file. `scripts/dev/check_readme_file_coverage.py` reports every
  shipped file its folder's README never names, and runs `--strict` in CI
  across all 31 folders.

### Fixed

- **`status` and `verify` no longer swallow a profile that fails to load.**
  `status` hardcoded an empty warnings array and printed nothing in plain mode;
  with nothing installed there was no `unknown` drift cell either, so the
  failure left no trace at all. `verify --harness all` discarded the failure to
  read its exclusions, so excluded harnesses rejoined the sweep and the run died
  later on a missing project path that named them — with no sign of the real
  cause. Both now surface a structured advisory naming the diagnostic code and
  the fix.
- **The PowerShell interpreter locator no longer throws where its contract
  promises `$null`.** `find-pwsh.ps1` built its Windows install-root fallbacks
  with an unguarded `Join-Path $env:ProgramFiles`, which is unset under
  PowerShell on Linux and macOS. The list was built eagerly, so the throw
  pre-empted even the PATH probe that would have succeeded.
- **A duplicate `run:` key made the CI workflow unparseable.** Adding the README
  coverage gate consumed the `Install release toolchain` step header and left
  its `run:` line attached to the new step. GitHub rejects a workflow file with
  a duplicate mapping key outright, so runs ended immediately with no jobs and
  no logs, and the release build lost its toolchain install.
- **`migrate-workspace` honored a custom directory name for its target but not
  its discovery**, so a non-default workspace name was written correctly and
  then never found again.
- Documentation corrections across the conformity gate's hook scope, the design
  tokens' consumers, the OpenCode example's provenance, two harness convention
  pins, and four architecture pages that were unreachable from ten locale
  indexes.

### Changed

- **Kimi Code's uninstall routes through the shared project-scope factory.** It
  was the one project-scope adapter still deriving its project root by walking
  up from the output path — the hardcoded ascent the factory exists to remove.
- **`LearningStore._append` is now `append_signal`.** It was reached across a
  module boundary by `workspace_migration` and four test modules while named
  private; the rename matches how it is actually used, and its docstring now
  states what it deliberately does not do.

## [1.0.2] - 2026-08-14

### Fixed

- **The `Stop` hook no longer re-asserts the session-end protocol on every turn.**
  `Stop` fires at the end of every assistant turn, not only at the end of a
  session, and the hook emitted `hooks/messages/stop.md` verbatim each time. Because
  that body reads as a fresh work order rather than a status check, every response
  triggered another firing and nothing the agent did changed what the hook
  asserted — the loop had no fixed point, and an operator could only escape it by
  restarting the harness, since hook configuration and message bodies are both
  snapshotted at session start. A new dispatch-routed handler,
  `hooks/session_end_gate.py`, supplies the missing termination condition: the
  protocol is emitted at most once per session, and only once the session has
  accumulated enough turn-ends to have state worth externalizing. The message file
  still owns the protocol text — the gate decides only when it is emitted — so its
  path and its cross-references from `rules/context-management.md` and
  `rules/auto-memory.md` are unchanged. Two environment variables tune it:
  `APOTHEM_SESSION_END_MIN_STOPS` (default `3`) sets the firing floor, and
  `APOTHEM_SESSION_END_ENABLED=0` silences the protocol entirely without editing
  installed plugin files.
- **The detection pseudocode in the canonical option-shapes rule is fenced as
  text rather than Python.** The block uses the hyphenated schema field names the
  same document defines in its field table, so formatting it as Python rewrote
  `read(probe-record-path)` into a subtraction expression and changed what the
  documentation said. Correcting the fence language leaves the pseudocode
  byte-identical and restores the format gate to green.

## [1.0.1] - 2026-07-07

Apothem is a host-agnostic AI-harness configuration manager: one governed shared
profile materializes into the native configuration of seventeen assistant
harnesses behind a conformity governance gate and signed, reproducible releases.

### Added

- **Shared-profile model.** One governed profile at
  `~/.config/apothem/profile.yaml` is the single source for the synced unit —
  rules, slash-commands, skills, hooks, output-styles, settings, schemas, docs,
  and MCP servers — plus the wrapped-workflow orchestrators that drive whole
  missions end to end (`/plan`, `/research`, `/audit`, and the `/fortress`
  closed-loop production-hardening pipeline).
- **Seventeen harness adapters.** Antigravity, Claude Code, CodeBuddy, Codex,
  Cursor, Gemini CLI, GitHub Copilot, Hermes, Kimi Code, Kiro, Open-Claw,
  OpenCode, Qwen Code, Trae, Windsurf, Zed, and GLM (Z.ai) each install, verify,
  update, and uninstall through a shared, reversible adapter contract that emits
  the tool's native file layout. Installs back up existing targets before
  replacement; uninstalls reverse cleanly with zero orphans.
- **CLI.** `quickstart`, `install`, `uninstall`, `update`, `verify`, `status`,
  `diff`, `rollback`, `migrate-workspace`, `harnesses`, `profile`, `doctor`, and
  `completion`, with dry-run reporting, drift detection, and structured JSON
  output (`--format json`). The engine is self-contained — the source tree
  carries its vendored dependencies and runs from a checkout as
  `python -m apothem` on system Python 3.10+.
- **Conformity governance gate.** A pre-emission validator suite checks the
  synced unit — authorship headers, frontmatter contracts, naming, determinism,
  cross-references, and harness capability coverage, including a cross-file
  binding-reciprocity validator that keeps every rule cross-binding closed at
  its cited peer — before any surface is materialized.
- **Install paths.** The Claude Code plugin
  (`/plugin marketplace add ahmed-g-gad/apothem`), a Gemini CLI extension, a
  Qwen Code extension, a Codex plugin, a VS Code-family extension on the Visual
  Studio Marketplace, the npm shim (`npx @ahmed-g-gad/apothem <command>`), and
  the one-shot POSIX and PowerShell installers (`install.sh` / `install.ps1`)
  with matching update and uninstall scripts.

### Changed

- **Unified install layout.** Materialized machinery (hooks, the conformity
  gate, schemas, templates) and non-native cohorts (rules, skills, agents)
  install under a single Apothem-owned `.apothem/support/` tree inside each
  harness's configuration root, so each profile carries one Apothem-owned dotted
  directory rather than two similarly-named siblings.
- **Leaner always-on rules tier.** The always-loaded behavioral rules were
  consolidated to twenty-eight, with situational depth moved into demand-loaded
  companion rules, so a session — or a fleet of sub-agents — ingests fewer
  tokens up front while every discipline still fires where it applies.

### Security

- Every release attaches an sdist, a wheel, SHA-256 checksums, Sigstore cosign
  signatures, SLSA build provenance, and a CycloneDX SBOM as verification
  evidence; the npm package publishes with Sigstore build provenance signed
  from the GitHub Actions OIDC identity, and a conformity validator holds every
  release workflow to a provenance-signed, pinned publish path.
- The pipeline gates every change on lint, tests, type checks, a documentation
  build, CodeQL, OpenSSF Scorecard, dependency review, a scheduled OSV
  vulnerability scan, and supply-chain checks before publication. The one-shot
  installers pin their `click` / `rich` prerequisites to the engine's declared
  constraints and document an inspect-first alternative to the pipe-to-shell
  one-liner.

[Unreleased]: https://github.com/ahmed-g-gad/apothem/compare/v1.0.2...HEAD
[1.0.2]: https://github.com/ahmed-g-gad/apothem/releases/tag/v1.0.2
[1.0.1]: https://github.com/ahmed-g-gad/apothem/releases/tag/v1.0.1
