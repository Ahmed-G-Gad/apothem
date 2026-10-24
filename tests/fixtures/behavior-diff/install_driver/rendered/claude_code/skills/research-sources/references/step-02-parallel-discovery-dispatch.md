<!-- SPDX-License-Identifier: MIT -->

### Phase 2 — Parallel Discovery Dispatch

Dispatch discovery in parallel — one `research-scout` agent per sub-query facet — per the Research Team pattern at `rules/agent-orchestration.md` §1 (full-parallel, single-message dispatch, structured-summary return contract). Each `research-scout` invocation fans its facet through `WebSearch`/`WebFetch` for external sources and `Read`/`Glob`/`Grep` for any in-repo corpus, returning a deduplicated ranked candidate list per facet; `research-scout` discovers and ranks only — it never fabricates a URL and never synthesizes (per its return contract at `agents/research-scout.md`). Where a facet needs per-source fetch-and-extract within the same pass, the `multi-source-research` skill (`skills/multi-source-research/SKILL.md`) drives the fanned fetch/extract loop.

Collect every facet's returns in a single pass; release the raw agent output after extracting the candidate list per `rules/agent-orchestration.md` §4 (return-contract enforcement). Honor the post-wave compaction trigger per `rules/context-management.md` §3 after the discovery wave.
