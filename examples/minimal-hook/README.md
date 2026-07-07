<!-- SPDX-License-Identifier: MIT -->

# minimal-hook

The smallest viable hook script — a POSIX shell wrapper that emits a confirmation line and exits cleanly.

## What it demonstrates

- A POSIX-shell hook script with `set -euo pipefail` (fail-loud on errors).
- Writing diagnostic output to stderr (the harness collects stderr from hook scripts).
- A clean `exit 0` (the canonical "hook ran successfully, do not block" signal).

## How to use it

The wiring example below targets the Claude Code adapter (which materializes hooks at `~/.claude/settings.json`); other harness adapters expose their own settings surface — consult the adapter's docs for the equivalent wiring location.

1. Copy `sample-hook.sh` to a stable location under your apothem checkout (e.g., `src/apothem/hooks/sample-hook.sh`); the active harness adapter materializes it into the harness's native hook location on install / sync.
2. Make it executable: `chmod +x src/apothem/hooks/sample-hook.sh`.
3. Wire it into `~/.claude/settings.json` (Claude Code adapter) under the `hooks` block. This standalone example sets `command` directly to the hook script and passes the event name in `args`, with `${HARNESS_ROOT}` resolving to the harness's installed location. (Apothem's own dispatcher hooks use a different shape — `command` is the Python interpreter `${PYTHON_BIN}`, and the `args` array carries the dispatcher script path followed by the event name.)

   ```json
   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "",
           "hooks": [
             {
               "type": "command",
               "command": "${HARNESS_ROOT}/.apothem/support/hooks/sample-hook.sh",
               "timeout": 10,
               "statusMessage": "Running the minimal smoke-test hook",
               "args": [
                 "PreToolUse"
               ]
             }
           ]
         }
       ]
     }
   }
   ```

4. Trigger any tool use; the hook fires before the tool runs and writes its confirmation line to stderr.

## Expected effect

Each `PreToolUse` event triggers the script, which emits `[hello-hook] PreToolUse event received: PreToolUse` to stderr and exits 0. The harness sees a clean exit and proceeds with the tool invocation.

## Layout

```text
minimal-hook/
├── sample-hook.sh   ← the hook script
└── README.md        ← this file
```

## Anti-patterns

- Do not make a smoke-test hook block tool invocations (return non-zero) — that disrupts the session.
- Remove the smoke-test hook once the pipeline is verified; production hooks have specific responsibilities.
