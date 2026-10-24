<!-- SPDX-License-Identifier: MIT -->

### Phase 1 — Discovery & Extraction

Read the question or notes in full. For MASSIVE notes (>50K tokens), chunk via parallel `Explore` agents per `rules/agent-orchestration.md` (one chunk per agent, ≤10K tokens per chunk). At every clause, triple-extract: the **claim** the source asserts, the **scope** it implies, the **success condition** it presumes. Surface the prose's implicit research domain and the adjacent domains its assumptions inherit.

**Establish the suite folder.** Per `rules/context-management.md` §2.6.1, every `_inputs/` and `_spec/` directory is a direct child of a research-suite folder. When the suite name is provided via `--suite-name`, create `{suite}/_spec/` directly; otherwise surface the name via the structured-inquiry channel before any spec write.
