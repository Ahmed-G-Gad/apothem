<!-- SPDX-License-Identifier: MIT -->

# hooks/lib

> **Role.** Dispatcher support — the shell stubs that locate an interpreter and
> hand off to the dispatcher, plus the shared Python helpers the hook scripts
> import.

The bootstrap stubs are the documented shell entry path; the Claude Code
`settings.json` hook entries instead invoke an install-resolved absolute
interpreter on `../dispatch.py` directly (the `${PYTHON_BIN}` placeholder is
substituted at install time), so the bootstrap stubs are not on that harness's
`settings.json` critical path.

## Files

| File | Purpose |
|------|---------|
| `bootstrap.sh` / `bootstrap.ps1` | Shell bootstrap stubs — resolve the project root, source the interpreter locator, and `exec` the dispatcher. The documented shell entry path. |
| `find-python.sh` / `find-python.ps1` | Python interpreter locators — find a real interpreter on PATH (rejecting zero-byte Store launcher shims, enforcing the version floor). |
| `find-pwsh.sh` / `find-pwsh.ps1` | PowerShell interpreter locators. |
| `events.py` | Single source of truth for the supported hook-event vocabulary, imported by the dispatcher and handlers. |
| `stdin_json.py` | Shared hook stdin JSON reader. Several handlers need the harness's event payload; this is the one canonical reader they consume, so the read path — and its behavior on absent, empty, or malformed stdin — cannot drift between them. |
| `log.py` | Shared logger factory for the hook scripts. |
| `resolve_root.py` | Project-root resolution for the apothem ecosystem. |
| `__init__.py` | Package marker. |

## Operating in this folder

- **Fail-open on the critical path.** The stubs use `set -u` (not `-euo pipefail`) and an `ERR` trap that emits a JSON diagnostic envelope and exits 0, so a missing interpreter or dispatcher never stalls the harness. Preserve every explicit diagnostic-envelope branch; `-e` would short-circuit them.
- **Stubs are paired across `.sh` and `.ps1`.** A change to one shell family's stub is mirrored in its counterpart in the same change so behavior does not diverge by platform.
- **Per-platform startup budgets bound the stubs:** the POSIX-bash stub carries the tightest budget; the PowerShell stub and the Windows Git-Bash/mingw64 path carry a wider budget because their interpreter startup dominates; the interpreter locator sits inside the stub budget. Keep stub work minimal — resolve, locate, `exec`; do not add per-invocation overhead.
- **The event vocabulary lives in `events.py`** and is imported, never duplicated, by the dispatcher and handlers.
- Shell files open with `#!/usr/bin/env bash` then the hash-form single-line SPDX license header; Python files carry the same hash-form header.
- Validate shell changes with `shellcheck hooks/lib/*.sh` and `Invoke-ScriptAnalyzer` over the `.ps1` stubs; validate Python helpers with `python -m ruff check`, `python -m mypy`, and `python -m pytest`. Surface any unresolved decision as `TODO(clarify): ...`.

## Related

- [`../`](../) — the hook runtime (`dispatch.py`, handlers, `messages/`) these stubs and helpers support.
- [`../../benchmarks/bench_hooks.py`](../../benchmarks/bench_hooks.py) — the per-event runtime benchmark whose budget the stub startup sits inside.
