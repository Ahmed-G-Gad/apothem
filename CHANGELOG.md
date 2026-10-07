<!-- SPDX-License-Identifier: MIT -->

# Changelog — Apothem

All notable changes to this project are documented in this file.

This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Each install says where Apothem's support files are.** The instruction
  file an install already writes (or its profile document) gains an "Apothem
  support files" section that names the directory each `rules/`,
  `templates/`, `schemas/`, `hooks/`, and `conformity/` citation resolves
  against, derived from the propagation manifest.
- **The Claude Code plugin ships the four output styles**, in the plugin's
  `output-styles/` directory.
- **`apothem backups prune`** runs backup and ledger retention on demand
  (`--keep N`, `--harness NAME|all`, `--dry-run`, `--json`). It never removes
  the backup set that rolling back a harness's latest install restores from.
- **A weekly check follows every vendor URL the harness pins and templates
  cite**, and reports one that has moved or died on a single open issue. A
  timeout, a refused connection or a passing outage is listed but does not
  count as dead; a host name that no longer resolves does.
- **The one-shot installers offer a checksum-only path.**
  `APOTHEM_VERIFY=checksum` installs the release's platform archive after
  checking its SHA-256 against the release's `SHA256SUMS`, aborts on a
  mismatch before extracting anything, and states that a matching digest
  proves integrity, not who published the archive. It is the documented
  alternative to `APOTHEM_ALLOW_UNVERIFIED=1` for a host without the
  maintainer's public key.
- **Every `--json` object carries `schema_version`**, and the profile
  schemas are served at their `$id` URLs. `harnesses list --json` stays a
  JSON array, so it has no top-level key to carry the version.
- **`doctor` probes each installed harness's hooks** and accepts `--project`.
- **CI runs the npm shim on Node 18, 20, 22, and 24**, under a written
  runtime-floor policy with an end-of-life notice.
- **Installs name the other tools that load a shared path.** The registry
  records one owner for each path several tools read, and installing an owner
  or a reader prints a note naming the others.
- **Install warns about risky MCP profile entries**: `transport: sse`, plain
  `http://` to a non-loopback host, and token-shaped literals in headers or
  env, without printing the value.
- **The Qwen Code extension ships a Markdown bootstrap command.**
- **Every slash command has a generated docs page and nav entry**, and the
  command index, CLI list, and conformity-validator table are generated from
  code. Translated pages whose English source changed since translation show
  a staleness note.
- **A channel smoke workflow runs every documented install command
  anonymously.** `channel-smoke.yml` runs on a weekly schedule and on demand.
  Each of the eight install channels runs on a clean runner with only its
  documented prerequisites, an isolated home directory, no credentials, and
  Git prompts disabled, so a private repository, an unpublished listing, or a
  missing release asset fails the job instead of reaching a new user. The
  commands live in `scripts/dev/channel_smoke.py`, and a test keeps them equal
  to the README. The harness CLIs install from a hash-pinned lockfile, which
  overrides Qwen Code's sharp 0.35.4 with 0.35.5 for GHSA-wq5f-xc86-pv6w.
- **The README explains the Qwen Code plugin prompt.** The repository is also a
  Claude Code marketplace, so Qwen Code asks which plugin to install;
  `qwen extensions install ahmed-g-gad/apothem:apothem --consent` installs
  without the prompt.
- **A behavioural eval suite ships as plain data.** `evals/` holds 108 cases
  in the plugin-eval format: trigger and non-trigger cases for every
  model-invocable command and agent, one outcome case per `/plan`,
  `/research`, and `/audit` stage, and paired rule-effect cases.
  `evals/case.schema.json` and a test validate every case, and a
  manual-dispatch, cost-capped Evals workflow runs them on demand.
- **CI records per-commit metrics.** A `metrics` job runs
  `scripts/dev/collect_metrics.py` and enforces separate coverage floors for
  the engine (80), the conformity gate (81), and the audit tooling (70). It
  also reports launch-time bytes per harness, CLI cold start, and hook latency.
- **Property tests cover the profile loader and frontmatter parsers.**
- **`scripts/release/bump_version.py` moves every version anchor in one
  step.** CI also checks the CHANGELOG link definitions, and the release
  build stops a tag whose plugin changed without a version change.
- **The plugin manifest carries a display name and listing links.**
- **A `binding-five-direction-grep` validator gates the Bindings section**,
  and every conformity entry point answers `--help`.
- **Brand and README pages carry a trademark and non-affiliation notice**
  for third-party harness names.

### Changed

- **OpenCode loads the always-on rules only.** `opencode.json` `instructions`
  lists the profile document and the 28 `alwaysApply` rules by path instead of
  globbing all 91, which cut OpenCode's launch context from 914,285 bytes to
  about 216,000. Install and update replace the old glob, and uninstall
  removes it; your own `instructions` entries are kept.
- **A skill and a command that share a name install as the skill**
  (`projectify`, `workflow`), in the engine install as in the plugin.
- **The single-file rule anchors no longer point at the Apothem source
  repository**; they say which Apothem files the install placed.
- **CI bounds cyclomatic complexity.** The CLI and the install driver block any
  function above 15, and a repository-wide ratchet stops any function from
  growing past the current maximum. The longest command bodies are split
  into phase helpers with no change in behaviour.
- **Helpers used across packages have public names**:
  `capability_projection_results`, `is_apothem_hook`, and `configure_stdio`.
  The private spellings remain as aliases.
- **Install refuses to rewrite a config it cannot keep intact.** A merge
  that must change a commented, JSONC, JSON5, or unparseable operator config
  writes nothing for that harness and exits 1 with `config.unparseable`; a
  merge that changes no value leaves the file byte-for-byte as it was.
- **Backups and the install ledger stay bounded.** Each harness keeps its
  newest 10 backup sets, one per install, uninstall or rollback, plus any
  older set a kept install, uninstall or rollback record still references,
  and the ledger keeps the newest 10 installs per install root. A root with
  nothing installed keeps its last record, so the backups of its last
  uninstall or rollback stay until that root sees another operation.
- **Harness convention pins cite their vendor sources.** Each pin lists the
  pages it rests on with retrieval dates and gives every discovery-pending
  capability a dated target. CI and the release build block on a pin older
  than 90 days, a pin with no vendor URL, or an overdue target.
- **Capability rationales match the vendor docs.** GitHub Copilot, Kiro, Trae,
  CodeBuddy, and Devin rationales cite the command and agent surfaces those
  tools document; Antigravity skills and Gemini CLI memory are native; Cursor
  web fetch is supported; the CodeBuddy and Devin MCP paths are corrected.
- **Each converted cohort declares what it keeps or drops.** Every adapter
  that converts commands, agents, or rules records a `conversion_losses` map
  in its `capabilities.yml`, checked against real converted output, and
  Gemini CLI command prompts no longer start with the source frontmatter.
- **Skill and command descriptions stay within 1,024 characters**, the Agent
  Skills limit, and the schemas enforce it.
- **The commands README records each command's model-invocation setting**,
  and a test keeps the table equal to the command files.
- **Usage errors exit 64** with a `cli.usage` envelope under `--json`,
  distinct from a findings or partial-write exit.
- **`quickstart` asks for a harness** instead of configuring all seventeen;
  `--harness all` keeps the old behaviour. The first `install` creates the
  default profile.
- **`doctor` judges installed harnesses only**, and profile validation
  reports every error.
- **The GitHub Copilot instructions put the operator profile first.**
- **Shared instruction files carry harness-neutral text.** The Kimi Code
  `AGENTS.md` block and the Gemini CLI and Antigravity `GEMINI.md` blocks no
  longer present themselves as one tool's own file.
- **The harness docs state what each tool loads.** The Claude Code pages match
  what the adapter writes, the install page gives the plugin's
  `/apothem:<name>` command names, and the OpenClaw, Hermes, and Kimi Code
  pages cite the vendor docs. The comparison page is dated and sourced.
- **The session-end protocol is now opt-in.** A `Stop` hook that returns
  context makes the assistant take another turn, so the protocol cost one extra
  turn in every session, whether or not the operator asked for it. Set
  `APOTHEM_SESSION_END_ENABLED=1` to enable it. It never fires on a stop that
  already follows a hook-driven continuation.
- **Gate iteration and pipeline remediation are bounded.** The pre-emission
  gate's revise-and-re-run loop stops after three rounds and reports BLOCKED
  with the failing bars, and every command that iterates on the gate says so.
  `/plan` and `/research` take `--max-rounds N` (default 3) for per-stage
  remediation, matching `/fortress`.
- **The proactive-compaction advisory fires at most twice per session** and
  can be silenced with `APOTHEM_PROACTIVE_COMPACTION_ENABLED=0`. Its
  model-facing text now asks only for state externalization; the compaction
  suggestion goes to the operator, who owns that action.
- **`APOTHEM_HOOKS_DISABLE=1` silences every Apothem hook**, the
  dispatcher-routed ones and the engine install's conformity-gate hook, for
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
- **Conformity validators report what they inspected.** Every standalone
  report and `--all` result carries an `inspected` count. A run that inspects
  nothing fails unless its empty scope is declared. Unknown flags and missing
  files or roots exit 3.
- **The hedging check flags the filler the instruction surfaces forbid**:
  `basically`, `kind of` as an adverb, and `in some sense`.
- **The always-on budget check names its unit and reports the full loaded
  size** of the always-on rules, beside the word count it gates on.
- **The hook benchmark runs the registered hook chain on real payloads**, and
  the agent benchmarks report "not measured" instead of passing.
- **The release SBOM describes the shipped wheel and sdist**, vendored
  packages included, and is signed. The sdist and wheel build reproducibly
  with a pinned setuptools backend.
- **npm releases publish through OIDC trusted publishing only.**
- **`ROADMAP.md` is the single roadmap**, and the site page is generated from
  it. The release policy and runbooks describe one additive release model.
- **The repository-root plugin manifest is removed.** The marketplace serves
  `plugins/claude-code`, whose manifest validates in strict mode.

### Fixed

- **OpenCode receives the operator profile.** The projected profile document
  was never in the `instructions` list, so OpenCode saw neither the
  operator's identity and preferences nor the support-file locations.
- **The reference note in command skills names directories that exist.** It
  pointed templates and hooks at a support directory no install creates.
- **The shared-root install note reads correctly when one other tool loads
  the path**, and `~/.claude/CLAUDE.md` is recorded as a Claude Code target
  that OpenCode also reads.
- **Hermes uninstall removes the `auxiliary.mcp` block an earlier release
  wrote**, under the same exact-value rule `update` uses, so the operator's
  own `auxiliary` settings stay.
- **Rollback returns a harness to its exact pre-install state**, and restores
  native configs at their real path.
- **Uninstall removes the empty directories the install created.**
- **A repeat install leaves a current CRLF instruction file as it is.** When
  the Apothem block in Claude Code's `CLAUDE.md` or in the projected profile
  document is already current, install keeps the file's bytes, CRLF line
  endings included, and reports it unchanged. It no longer rewrites the file
  with LF line endings, backs it up, and reports it updated. An instruction
  file that is not UTF-8 text is refused with `config.unparseable` and left
  as it is, where install and `apothem diff` stopped with a decoding error.
- **Operator settings survive install, update, and uninstall.** Permission
  rules, MCP servers, Hermes `auxiliary` settings, and hook handlers the
  operator added are kept; a hook counts as Apothem's only when it runs
  Apothem's installed scripts.
- **Hermes MCP servers land in the top-level `mcp_servers` map**, and an update
  moves the servers an earlier release wrote under `auxiliary.mcp`.
- **The GLM provider file is written only when absent**, and GLM verifies in
  sync after a clean install.
- **Profile text can no longer split the managed block.**
- **`install --dry-run` and `diff` list every write**, and a repeated install
  writes nothing.
- **Cursor, Devin, and Kimi Code references point at the current vendor
  pages.**
- **Codex keeps user-only skills out of implicit invocation.** Codex ignores
  `disable-model-invocation`, so the install writes `agents/openai.yaml` with
  `allow_implicit_invocation: false` beside each user-only skill.
- **Claude Code skills use `user-invocable`**, the key Claude Code reads, in
  the engine install and the plugin.
- **Selecting an Apothem output style keeps Claude Code's coding
  instructions** (`keep-coding-instructions: true`).
- **Cursor, Kiro, Trae, CodeBuddy, and Windsurf rule files put frontmatter
  first**, ahead of the managed-block marker, so the tool reads it. Trae rules
  activate with `alwaysApply`, and Antigravity plugin rules carry a valid
  `trigger`.
- **Converted agents keep their limits.** Read-only agents run in a read-only
  Codex sandbox, Gemini CLI agents get a tool allowlist and `max_turns`, and
  the hard-coded Codex reasoning effort is gone. Agents no longer set
  `memory: false`, a value Claude Code does not define.
- **A missing `click` or `rich` gives a structured error naming the install
  command** instead of a traceback, and `PYTHONPATH=src` resolves the vendored
  dependencies.
- **The one-shot installer installs and verifies in one run**, and the
  installers emit no ANSI codes when output is not a terminal.
- **Piped output and `--help` epilogs keep their line structure.**
- **`apothem completion <shell>` no longer ends the script with a blank
  line.** The output for `bash`, `zsh`, `fish`, and `powershell` now ends in
  a single newline, so appending it to a shell profile adds no extra line.
- **Profiles without a version are read as version 1.**
- **Qwen Code hook timeouts are written in seconds** and the interpreter path
  is quoted.
- **The GLM provider file carries the documented model-mapping
  placeholders.**
- **Zed installs warn when the new `.rules` file hides an existing instruction
  file**, since Zed reads only the first one it finds.
- **Claude Code agent and command tool lists name the Task tools**, and the
  settings file declares its schema.
- **Docs pages meet WCAG 2.2 AA in the checked views.** Code-block and
  active-navigation colours reach 4.5:1 contrast, pages have `main` and `nav`
  landmarks, and the GitHub icon has an accessible name. Trailing-slash URLs
  redirect instead of returning 404, and translated pages search their own
  language's index.
- **Each GitHub Release attaches the VS Code extension.** The README's VS Code
  channel installs `apothem.vsix` from the Release, but the release workflow
  never built it, and v1.1.0 carries none. The release build now packages it
  into the signed, hashed, and attested asset set.
- **Extension wrappers run the engine version they shipped with.** The Gemini
  CLI and Qwen Code commands, the Gemini and Qwen Code context files, the
  Codex plugin skill, and the VS Code extension's default runner called
  `npx @ahmed-g-gad/apothem` with no version, so a later npm publish changed
  what an installed extension ran. Each call now pins the wrapper's own
  version, and `bump_version.py` moves the pins.
- **The docs describe the VS Code extension as it ships.** The install page
  said it installs from the Visual Studio Marketplace, where no listing
  exists, and the README said each release attaches a signed `.vsix`, which
  v1.1.0 does not. Both now say how to install the package and how to build
  it from a checkout.
- **The branch protection page matches the settings on `main`.** It described
  a ruleset with four required checks (`ci`, `Scorecard`, `CodeQL`,
  `pip-audit`), one required approval, latest-push approval, and "require
  branches to be up to date". `main` uses a classic protection rule that
  requires 12 checks (the ten `quality` cells, `coverage`, and
  `Require Signed-off-by`) and 0 approvals, does not bind admins, and does not
  require an up-to-date branch. The page now lists those exact settings and,
  separately, the clean-install, harness-matrix, and installer-lint checks
  still to be added. The solo-maintainer merge runbook, `CONTRIBUTING.md`, and
  the Scorecard page now describe the same review settings, and the runbook
  and `admin_merge.py` warn that an `--admin` merge also bypasses red required
  checks while `enforce_admins` is off.
- **The wheel and sdist carry the full hook corpus.** They left out
  `hooks/hooks.json` and the hook READMEs that every other channel ships.
- **Path-filtered rules no longer load in every Claude Code session.** Claude
  Code reads only `paths:` from a rule and loads every rule without it at
  launch, so the engine install loaded all 91 rules (over 900 KB) in each
  session. The install now writes each path-filtered rule with a `paths:` list
  built from its `pathFilter`; the 28 always-on rules (about 214 KB) load at
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
- **The engine-installed conformity gate hook starts.** It failed to import
  its package in the installed layout and crashed on every write.
- **Several validators no longer pass while inspecting nothing**, including
  the naming check and the five-direction Bindings check, and the secret-leak
  check no longer flags AWS documentation example keys.
- **The profile loader returns structured errors** for invalid UTF-8, YAML
  alias cycles, and very deep nesting instead of raising.
- **The documented release verification passes on real release assets**, with
  the exact signer identity, and the verifier script checks all three layers.
- **Distribution metadata declares `MIT AND PSF-2.0`**, and REUSE attributes
  the plugin tree's vendored code to its authors.
- **SECURITY.md lists 1.1.x as supported**, the release badge reads the tag
  from full history, and the CHANGELOG links resolve.
- **`install.sh` and `update.sh` treat only `vMAJOR.MINOR.PATCH` tags as
  release tags**, as `install.ps1` and `update.ps1` do. Both scripts matched
  `v1.2.3.4`, `v1..2.3`, and `v1.2.3v`, and `update.sh` also matched
  `v1.2.3-rc1` and `v1x.2.3`. A ref pinned to one of these went to
  `git verify-tag` instead of stopping as "not a signed release tag", and
  `install.sh` accepted the first three for `APOTHEM_VERIFY=checksum`. Both
  scripts now use the same check.
- **The installers give key-import guidance in any language.** When the
  maintainer key was missing from the local keyring and GnuPG printed its
  messages in another language, `install.sh`, `install.ps1` and `update.sh`
  reported the signed tag as possibly tampered with, because they matched
  GnuPG's English text. They now read GnuPG's status lines
  (`[GNUPG:] NO_PUBKEY`), which do not change with the language.
- **The shell rules' PowerShell lint command reports syntax errors.** The
  `code-craft-shell` and `performance-discipline` rules ran
  `Invoke-ScriptAnalyzer -Severity Error,Warning`. PSScriptAnalyzer reports
  a syntax error at severity `ParseError`, and an explicit `-Severity` list
  without it drops the error, so a script that did not parse passed clean.
  Both rules now pass `-Severity Error,Warning,ParseError`.
- **The shell rules' PowerShell lint check fails on a finding.** The
  `code-craft-shell` rule said `Invoke-ScriptAnalyzer ...` "exits 0" and that
  the host's `PSScriptAnalyzerSettings.psd1` "is honored". Without
  `-EnableExit` the cmdlet exits 0 even when it reports findings, and without
  `-Settings` it reads a settings file only from the `-Path` folder, never a
  parent folder. The rule now passes when the analyzer returns no records,
  runs a command that exits 1 on any record, and passes `-Settings` when the
  host has a settings file. The command also exits 1 when the script, the
  settings file or the PSScriptAnalyzer module is missing, under both
  `pwsh -Command` and `pwsh -File`. The `performance-discipline` §1.1
  verifier exits 1 on any record in the same way.

### Security

- **The release build tooling uses urllib3 2.8.0**, which fixes
  PYSEC-2026-4175, PYSEC-2026-4176 and PYSEC-2026-4177 in the hash-locked
  tooling the release workflow installs before it builds.
- **Profile text cannot carry the managed-block markers.** A profile value
  containing a block marker fails validation with
  `profile.managed_block_marker`, naming the field without echoing the value.
- **The VS Code extension runs only a user-scoped runner**, quoted, for a
  chosen harness; a workspace setting can no longer set the command it runs.
- **The release packages the VS Code extension in a job of its own.** vsce
  installs from a committed lockfile with `npm ci --ignore-scripts`, in a job
  that never sees the Python distributions, and only `apothem.vsix` passes to
  the build job, which adds it to the `dist/` assets that are hashed, signed and
  attested. Before, `npx` resolved the packager's dependency tree at release
  time, with install scripts, in the job that built the wheel. The Marketplace
  workflow uses the same lockfile. The packager is vsce 4.0.0, which no longer
  pulls in braces 3.0.3 (GHSA-vfj7-8cjw-p6xm, with no patched release).
- **No long-lived npm token path remains.** The npm publish workflow
  authenticates through OIDC alone; the token secret and its opt-in gate are
  gone.
- **Hooks never run code from the opened project.** The bootstrap stubs
  resolve the dispatcher from their own installed location. Previously the
  stubs took their root from the project directory when it contained a
  `hooks/` folder, so a project could supply the interpreter locator or the
  dispatcher that the plugin's hooks then ran. Session-start guidance is read
  from the installed tree; the project is read only for plan and memory
  summaries.
- **Per-session hook state is private to the user.** The session-end gate and
  the compaction tracker kept counters in a shared directory under the system
  temp dir, created with default permissions. State now lives in a per-user
  directory created with mode `0700`, and session ids are sanitized before use
  as file names. `APOTHEM_HOOK_STATE_DIR` overrides the location.

## [1.1.0] - 2026-08-16

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
- **`migrate-workspace` reports a legacy data home it failed to remove.** The
  removal ignored errors, so when a locked file or a denied permission kept the
  directory on disk, the command still reported a clean migration and the next
  run found the same directory again. It now adds a note that names the
  directory: its records are already merged into the shared store and kept in
  the backup, so the directory can be deleted by hand.
- Documentation corrections across the conformity gate's hook scope, the design
  tokens' consumers, the OpenCode example's provenance, two harness convention
  pins, and four architecture pages that were unreachable from ten locale
  indexes.

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
  same document defines in its field table, which are not valid Python.
  Correcting the fence language leaves the pseudocode byte-identical.

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
  Qwen Code extension, a Codex plugin, the npm shim
  (`npx @ahmed-g-gad/apothem <command>`), and the one-shot POSIX and PowerShell
  installers (`install.sh` / `install.ps1`) with matching update and uninstall
  scripts. The source of a VS Code-family extension is in `vscode-extension/`;
  this release attaches no packaged `.vsix`, and the extension is not listed on
  the Visual Studio Marketplace.

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

[Unreleased]: https://github.com/ahmed-g-gad/apothem/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/ahmed-g-gad/apothem/releases/tag/v1.1.0
[1.0.2]: https://github.com/ahmed-g-gad/apothem/releases/tag/v1.0.2
[1.0.1]: https://github.com/ahmed-g-gad/apothem/releases/tag/v1.0.1
