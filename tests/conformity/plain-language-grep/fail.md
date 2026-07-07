<!-- SPDX-License-Identifier: MIT -->

# Apothem — AI Configuration Manager

Apothem is an AI configuration manager. It targets every popular agent
runtime including claude-code, cursor, gemini, and copilot.

## How the LLM integration works

Each agent loads its configuration at startup. The attestation produced
during phase 4 confirms the materialized files match the profile. Stream B
of the rollout covers windsurf and codex; the 01A sub-phase handles the
hermes adapter.

The cutover-rehearsal step replays the install against a scratch profile,
and only ratified conventions reach the operator surface — the agent decides
which knobs to expose.

```bash
# Inside a fenced block, tokens like AI and agent are permitted (quoted samples).
apothem install --harness claude_code
```

Run the verifier to confirm the LLM-facing config is in sync.
