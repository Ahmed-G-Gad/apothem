---
name: "code-craft-shell"
description: "Per-language code-craft for shell artifacts — POSIX bash idioms (set -euo pipefail; quoted variables; no eval on untrusted input; trap-based cleanup) and PowerShell idioms (Set-StrictMode -Version Latest; verb-noun cmdlet naming; no Invoke-Expression on untrusted input; structured error records). Honor shellcheck for bash and Invoke-ScriptAnalyzer for PowerShell; pass the host's ratified shell linter clean."
pathFilter: "**/*.sh, **/*.bash, **/*.ps1, **/*.psm1, **/*.psd1"
alwaysApply: false
paths:
  - "**/*.sh"
  - "**/*.bash"
  - "**/*.ps1"
  - "**/*.psm1"
  - "**/*.psd1"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Code Craft — Shell

## What this rule enforces

This rule binds **M13 — Code Craft Conventions** at the **shell per-language tier**, covering POSIX bash and PowerShell. Every shell artifact the agent produces — script, hook stub, build helper, runner, deployment driver, environment activator, CI-pipeline glue, one-shot administrative command — MUST meet the M13.1–M13.11 floor with shell-specific materialization: strict mode by default, every variable quoted, no shell injection on untrusted input, deterministic error handling with explicit exit codes, named constants over magic numbers, and behavior-shaped tests where the host has a shell-test framework. The artifact MUST pass `shellcheck` (bash / sh) and `Invoke-ScriptAnalyzer` (PowerShell) clean against the host's ratified configuration.

## Pre-conditions

Applies whenever a shell artifact matching the `pathFilter` glob list — `*.sh`, `*.bash`, `*.ps1`, `*.psm1`, `*.psd1` — is authored, modified, or reviewed. Ecosystem-internal shell stubs under `hooks/lib/bootstrap.sh` and `hooks/lib/bootstrap.ps1` (and siblings) honor this rule alongside host-project shell. The shell-execution sub-budgets at `rules/performance-discipline.md` §1.1 govern the runtime ceiling for hook bootstrap stubs and shell linters; this rule governs their static-form quality.

## Required behavior

### 1. Strict-Mode Defaults

#### 1.1 POSIX bash / sh

Every bash script opens with strict-mode declarations as the first non-shebang, non-comment lines:

```bash
#!/usr/bin/env bash
# Optional: header comment naming purpose / why-not-what / cross-references
set -euo pipefail
IFS=$'\n\t'
```

- **`set -e`** — exit immediately on any command failure (no silent error swallowing).
- **`set -u`** — unset variable reference is an error (catches typos at runtime).
- **`set -o pipefail`** — a pipeline's exit status is the last non-zero in the chain (no silent failure of `cmd1 | cmd2` when `cmd1` fails).
- **`IFS=$'\n\t'`** — restrict word-splitting to newline + tab; eliminates a class of space-bearing-filename bugs.

When the host's existing shell scripts use a different strict-mode discipline (e.g., `set -eEuo pipefail` adding the `-E` ERR-trap inheritance), honor the host's discovery per `rules/host-discovery.md`.

#### 1.2 PowerShell

Every PowerShell script opens with strict-mode declaration:

```powershell
#Requires -Version 7.0
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
```

- **`Set-StrictMode -Version Latest`** — uninitialized variable reference, missing object property access, function call with too-many positional args all become errors.
- **`$ErrorActionPreference = 'Stop'`** — non-terminating errors become terminating, eliminating the silent-error class.
- **`#Requires -Version 7.0`** — declare the minimum PowerShell version (or `5.1` when targeting Windows PowerShell). Match the host's discovered minimum.

### 2. Variable Quoting & Word-Splitting

#### 2.1 Bash

Every variable expansion is double-quoted unless the unquoted form is a deliberate word-splitting use:

- **Right form:** `cp -- "$src" "$dst"` (handles spaces, tabs, glob characters in `$src` and `$dst`).
- **Wrong form:** `cp $src $dst` (silently breaks on a path containing a space; security risk on adversarial inputs).
- **Argument terminators.** Use `--` before path arguments to disambiguate against unintended option parsing (`rm -- "$file"`).
- **Array expansion.** `"${array[@]}"` to expand each element as a separate argument; `"${array[*]}"` only when joining is intended.

#### 2.2 PowerShell

PowerShell handles word-splitting differently — variables are not subject to bash-style word-splitting. The discipline:

- **Stop-parsing token.** When invoking native executables that take arguments PowerShell would parse as operators, use `--%` to prevent re-parsing: `git log --% --format=%H`.
- **Splatting.** Pass argument arrays via splatting (`@args`) rather than string concatenation to preserve quoting.
- **Path operations.** Use `Join-Path` and `[System.IO.Path]::Combine()` rather than string concatenation for path construction.

### 3. Injection Prevention (M13.8)

A shell command or PowerShell expression MUST NOT be constructed from untrusted input:

#### 3.1 Bash

- **No `eval` on untrusted input.** `eval "$user_input"` is RCE. Use `case` / function dispatch instead.
- **No unquoted command substitution containing untrusted input.** `cmd $(echo "$user_input")` re-splits on word-splitting; prefer arrays.
- **No `bash -c "$untrusted"`.** Same RCE class. Pass arguments through `argv`, not via interpolation.
- **`xargs` with `-0` and `-r`** when chaining filename lists; otherwise newline-bearing names break the pipeline.

#### 3.2 PowerShell

- **No `Invoke-Expression` on untrusted input.** Same RCE class as bash `eval`. Use script blocks (`& { ... }`) with parameterized arguments instead.
- **No string-formatted SQL / shell commands.** Parameterized cmdlets honor quoting; string-formatted commands do not.
- **`-LiteralPath` over `-Path`** when the path is data, not a glob pattern (Path expands wildcards; LiteralPath does not).

### 4. Error Handling & Exit Codes (M13.3)

#### 4.1 Bash

- **Explicit exit codes.** `exit 0` for success; `exit 1`–`125` for documented failure modes (avoid 126 / 127 / 128+, reserved by POSIX for shell-internal errors).
- **`trap` for cleanup.** Resources allocated in the script (temp files, lock files, mounts, child processes) are released by a `trap '...' EXIT INT TERM` clause, not deferred to GC.
- **Error context on failure.** When a command fails, the failure message names the command, the input, and the exit code: `printf 'error: <command> failed (exit %d) with input %q\n' "$rc" "$input" >&2; exit "$rc"`.
- **No silent failure.** Every command whose failure is recoverable is wrapped in an explicit conditional; every command whose failure is fatal is allowed to propagate via `set -e`.

#### 4.2 PowerShell

- **Throw structured errors.** `throw [System.IO.FileNotFoundException]::new("$path")` rather than `throw "file not found"` (typed errors are catchable by type).
- **Try / catch / finally** over `$LASTEXITCODE` checks for cmdlet errors. Native-exe errors still need `$LASTEXITCODE` inspection.
- **`exit $exitCode`** at script tail makes the exit code explicit; absence defaults to 0 even after errors in `$ErrorActionPreference = 'Continue'` mode.

### 5. Naming & Documentation (M13.2, M13.11)

#### 5.1 Bash

- **Function names** use snake_case: `cleanup_tempfiles`, `parse_arguments`, `validate_input`.
- **Variable names** for script-level constants use UPPER_SNAKE_CASE: `readonly LOG_DIR="/var/log/app"`.
- **Local variables** inside functions use lower_snake_case and the `local` keyword: `local input="$1"; local rc=0`.
- **Header comment** at the top of the script names: purpose, dependencies (other scripts / binaries the script invokes), invocation example, exit-code catalog.

#### 5.2 PowerShell

- **Verb-noun cmdlet naming.** Functions follow the approved-verb list (`Get-Verb` lists them): `Get-FooConfig`, `Set-FooConfig`, `New-FooSession`, `Remove-FooSession`, `Test-FooReachability`. Non-approved verbs trigger `Invoke-ScriptAnalyzer` warnings.
- **Comment-based help.** Every public function carries a `<#  .SYNOPSIS / .DESCRIPTION / .PARAMETER / .EXAMPLE / .OUTPUTS  #>` block per the host's ratified discipline.

### 6. Magic Numbers & Constants (M13.10)

Numeric literals in shell logic become named constants:

#### 6.1 Bash

```bash
readonly TIMEOUT_SECONDS=30
readonly MAX_RETRIES=3
readonly EXIT_INVALID_INPUT=2

if (( retries >= MAX_RETRIES )); then
    exit "$EXIT_INVALID_INPUT"
fi
```

Avoid literal `30`, `3`, `2` in the body — the named constants tell the next reader why these values.

#### 6.2 PowerShell

```powershell
$Script:TimeoutSeconds = 30
$Script:MaxRetries = 3
$Script:ExitInvalidInput = 2
```

### 7. Linting & Static Analysis (M13.7)

The artifact passes the host's ratified shell linter clean:

- **Bash.** `shellcheck script.sh` exits 0. The host's `.shellcheckrc` is honored per M1 host-discovery; sibling scripts' shellcheck-disable directives are followed unless the new script's context warrants different.
- **PowerShell.** The check passes when `Invoke-ScriptAnalyzer` returns no diagnostic records for the script. Do not judge it by the exit status of a bare call: `pwsh -Command "Invoke-ScriptAnalyzer ..."` exits 0 even when the cmdlet reports findings. Run `$ErrorActionPreference = "Stop"; $findings = Invoke-ScriptAnalyzer -Path script.ps1 -Settings PSScriptAnalyzerSettings.psd1 -Severity Error,Warning,ParseError; if ($findings) { $findings | Format-Table -AutoSize; exit 1 }` with `pwsh -Command`, or save it as a `.ps1` file and run it with `pwsh -File`. It exits 1 on any record. It also exits 1 when the `-Path` target, the `-Settings` file or the PSScriptAnalyzer module is missing. Without the `$ErrorActionPreference` line, `pwsh -File` exits 0 in those three cases. From a POSIX shell, single-quote the `-Command` string, because double quotes let the shell expand `$findings` to nothing.
  - **Not `-EnableExit`.** It sets the exit code to the number of records, but Linux and macOS pass only the low 8 bits of an exit code to the caller, so 256 findings exit 0.
  - **Keep `ParseError` in the list.** PSScriptAnalyzer reports syntax errors at that severity, and an explicit `-Severity` list without it drops them, so a script that does not parse would pass clean.
  - **Pass the host's `PSScriptAnalyzerSettings.psd1` with `-Settings`**, as a path from the current folder. Drop the flag only when the host has no settings file, because the command above exits 1 when the `-Settings` file does not exist. Without `-Settings`, PSScriptAnalyzer looks for that file name only in the `-Path` folder, or in the folder that holds the `-Path` file, and never in a parent folder. A settings file at the repository root therefore does not apply to `scripts/installer/install.ps1` unless `-Settings` names it (PSScriptAnalyzer 1.25.0, `FindSettingsMode` in `Engine/Settings.cs`). The file's `Severity` list and `-Severity` are merged into one list (`Initialize` in `Engine/ScriptAnalyzer.cs`), so the file can add a severity but cannot remove `ParseError`.

The shell-linter performance budgets at `rules/performance-discipline.md` §1.1 govern the runtime ceiling: 5s for `shellcheck` over `hooks/lib/*.sh`, 10s for `Invoke-ScriptAnalyzer` over `hooks/lib/*.ps1`.

### 8. Testing (M13.6)

Where the host has a ratified shell-test framework:

- **bats-core** for bash. Test files at `tests/bash/<unit>.bats`. AAA shape: `setup() { … }` (Arrange) → `@test 'description' { run cmd; ... }` (Act) → `[ "$status" -eq 0 ]; [ "$output" = '...' ]` (Assert).
- **Pester** for PowerShell. Test files at `tests/powershell/<unit>.Tests.ps1`. AAA shape: `BeforeAll { … }` (Arrange) → `It 'description' { $result = Invoke-Foo … }` (Act) → `$result | Should -Be 'expected'` (Assert).

When the host has no shell-test framework configured but the script's behavior warrants verification, surface as an inquiry per `rules/authority-inquiry.md` with bats-core / Pester recommended per the language.

### 9. Cross-Platform Convention

When a script must run on multiple platforms (Windows + POSIX), prefer:

- **Pure POSIX sh** when the script's surface is small and dependency-free (no `[[ ]]`, no arrays, no `$(<file)` substitutions).
- **Bash with explicit `#!/usr/bin/env bash`** when the script needs bash features and the host has bash on every target platform.
- **Two parallel scripts** (`script.sh` + `script.ps1`) when the host has POSIX-only and Windows-only paths, with the dispatching wrapper choosing per platform. This is the pattern the ecosystem uses at `hooks/lib/bootstrap.{sh,ps1}` per the canonical-pair discipline declared in the hooks pipeline Paired-Template Review Cadence.

## Disclosure surface

Every shell artifact emission, refactor, or anti-pattern interception is recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[Discovery — source: .shellcheckrc | sibling-shell-scripts; value: <strict-mode-form | linter-config>; honored]` for shellcheck-config and bash-idiom discoveries.
- `[Discovery — source: PSScriptAnalyzerSettings.psd1 | sibling-ps1-scripts; value: <ruleset>; honored]` for PowerShell linter-config discoveries.
- `[Refinement — improvement: security; intercepted: <eval | Invoke-Expression | shell-injection-pattern>; replacement: <safe-form>]` for security interceptions.
- `[Default — applied: <auto-decision>; class: pure-formatting-normalization]` for shellcheck / Invoke-ScriptAnalyzer normalizations on existing files where the host has a ratified style.

## Failure tells

`#!/bin/sh` followed by bash-only constructs (`[[ ]]`, arrays, `$()` instead of backticks in old-shell contexts — bashism creep). A bash script with no `set -euo pipefail` (silent-error class). A bash script using `set -e` but with `||` chains that swallow the `-e` propagation without explicit handling. Variable expansion without quotes (`cp $src $dst` instead of `cp -- "$src" "$dst"`). `eval "$user_input"` (RCE). `bash -c "$untrusted"` (RCE). A PowerShell script with no `Set-StrictMode` (uninitialized-variable class). A PowerShell script using `Invoke-Expression` on untrusted input (RCE). A PowerShell function named with a non-approved verb (`Process-Foo` instead of `Update-Foo` or `Invoke-Foo`). A bash script that fails `shellcheck` with new findings the host's existing scripts do not have. A PowerShell script for which `Invoke-ScriptAnalyzer -Severity Error,Warning,ParseError` returns any diagnostic record. A PowerShell lint step that trusts the exit status of a bare `Invoke-ScriptAnalyzer` call, which is 0 even when the call reports findings. A PowerShell lint run without `-Settings` on a script outside the folder that holds the host's `PSScriptAnalyzerSettings.psd1`, which silently skips the host's settings. Magic numbers in retry / timeout / buffer-size logic without named constants. A trap-less bash script that allocates a tempfile and exits without cleanup. A PowerShell script that throws a string literal (`throw "error"`) instead of a typed exception. A cross-platform-intended script that uses bash-only constructs without a PowerShell parallel.

## Bindings (§0.j five-direction)

- **Drives →** ● Every shell artifact's quality floor across every host project (strict-mode defaults, variable quoting, injection prevention, deterministic error handling). ● Every `hooks/lib/bootstrap.sh` and `hooks/lib/bootstrap.ps1` touch under the path-filter (the canonical-pair stubs governed by the hooks pipeline). ● Every CI shell stub, deployment driver, and environment activator. ◐ The shell-execution sub-budgets at `rules/performance-discipline.md` §1.1.
- **Satisfies →** ● the fifteen-mandate registry row **M13 — Code Craft** at the shell per-language tier. ● the rules registry row "Code Craft — Shell".
- **Established by ↑** ● the fifteen-mandate registry (ratifies M13). ● POSIX shell standards (IEEE Std 1003.1) and PowerShell language specification (Microsoft Learn). ● `shellcheck` rules catalog (the upstream lint rulebook this rule projects). ● `PSScriptAnalyzer` rules catalog (the upstream PowerShell lint rulebook this rule projects).
- **Gated by ←** ● The path-filter (`*.sh`, `*.bash`, `*.ps1`, `*.psm1`, `*.psd1`) — this rule activates only on shell-language artifact touches. ● the trivial-vs-non-trivial threshold (trivial-scope shell edits run an abbreviated check covering strict-mode and quoting only).
- **Cross-bound with ↔** ↔ `rules/code-craft-conventions.md` (universal-delegation stub yields to this rule when the artifact's path matches; the universal floor M13.1–M13.11 is materialized here in shell idioms). ↔ `rules/code-craft-python.md` + `rules/code-craft-markdown.md` (sibling per-language code-craft rules; consistent body shape across the trio). ↔ `rules/performance-discipline.md` §1.1 (per-shell budgets — bootstrap.sh ≤ 500ms, bootstrap.ps1 ≤ 1500ms, find-python.{sh,ps1} ≤ 200ms, shellcheck ≤ 5s, Invoke-ScriptAnalyzer ≤ 10s; this rule is the static-form quality discipline whose runtime is governed there). ↔ `rules/host-discovery.md` (M1 — shellcheck and ScriptAnalyzer config discovery walks). ↔ `rules/clean-room-generation.md` (Code Generation §4 governs initial shell emission before this rule's path-filtered guardrails apply). ↔ `rules/host-discovery-manifests.md` (↔ reciprocal of the peer's Cross-bound citation). ↔ `rules/production-ready-prs.md` (↔ reciprocal of the peer's Cross-bound citation). ↔ `rules/ten-dimension-check-dimensions.md` (↔ reciprocal of the peer's Cross-bound citation).
