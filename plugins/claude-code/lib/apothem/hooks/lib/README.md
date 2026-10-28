<!-- SPDX-License-Identifier: MIT -->

# hooks/lib

> **Role.** Dispatcher support — the shell stubs that locate an interpreter and
> hand off to the dispatcher, plus the shared Python helpers the hook scripts
> import.

The Claude Code plugin's `hooks.json` runs `bootstrap.sh` through `bash` for
every hook. The engine-installed Claude Code `settings.json` hook entries
instead invoke an install-resolved absolute interpreter on `../dispatch.py`
directly (the `${PYTHON_BIN}` placeholder is substituted at install time), so
the bootstrap stubs are not on that surface's critical path.

## Files

| File | Purpose |
|------|---------|
| `bootstrap.sh` / `bootstrap.ps1` | Shell bootstrap stubs — resolve the installed hook tree from the stub's own location (never from the opened project), source the interpreter locator, and `exec` the dispatcher. The plugin's entry path. |
| `find-python.sh` / `find-python.ps1` | Python interpreter locators — find a real interpreter on PATH (rejecting zero-byte Store launcher shims, enforcing the version floor). |
| `find-pwsh.sh` / `find-pwsh.ps1` | PowerShell interpreter locators. |
| `events.py` | Single source of truth for the supported hook-event vocabulary, imported by the dispatcher and handlers. |
| `stdin_json.py` | Shared hook stdin JSON reader. Several handlers need the harness's event payload; this is the one canonical reader they consume, so the read path — and its behavior on absent, empty, or malformed stdin — cannot drift between them. |
| `log.py` | Shared logger factory for the hook scripts. |
| `resolve_root.py` | Project-root resolution for the apothem ecosystem. |
| `message_text.py` | Strips the maintainer-only parts of a message file (the license comment line and the `## Bindings` section) before the text reaches the assistant, and extracts and fills a guard's short `## Advisory` template. |
| `state_dir.py` | Per-user state directory (mode `0700`) and safe per-session file keys for the stateful handlers; resolution order `APOTHEM_HOOK_STATE_DIR`, `CLAUDE_PLUGIN_DATA/state`, `XDG_STATE_HOME/apothem`, then the platform default. |
| `vendor_contract.py` | Per-vendor hook contracts, selected by `dispatch.py --contract <id>` (`claude`, `codebuddy`, `devin`, `cursor`, `copilot`, `kiro`). Each row maps the vendor's event and tool spellings and payload keys onto the Claude shape the handlers read, rewrites the handler's envelope into the shape the vendor reads (the envelope as written, bare text, `{"additionalContext"}` or `{"additional_context"}`), drops an event the vendor does not hand to the model, and keeps one SessionStart marker per (session, source), shared by the vendor's own command and the Claude Code copy it imports, for Cursor and Devin Local. Standard library only; it carries no decision, so the dispatcher stays advisory. The default command line imports it only for a SessionStart under Cursor or Devin Local. |
| `header_check.py` | The authorship-header guards' checker, standard library only. Reads `authorship-header.txt` and `header-exceptions.txt` from the `schemas/` directory beside `hooks/` in the tree it runs from (the plugin tree, the engine support tree, a checkout), and decides by comment family from the file extension, using the variant tables and insertion-site rules of `scripts/inject-header.py` (`tests/hooks/test_header_check.py` holds the two equal). It needs no `apothem` import, which is unavailable under a plugin install and slow where it is available. `project_adopts_header` gates the guard to a git project that carries the fixture. A missing fixture leaves the guard silent. |
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
