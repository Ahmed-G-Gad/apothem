<!-- SPDX-License-Identifier: MIT -->

### Phase 1 — Discovery & Extraction (Pre-G1)

Read the prose source in full. For MASSIVE prose (>50K tokens), chunk via parallel `Explore` agents (one chunk per agent, ≤10K tokens each) and persist each extraction at `{suite}/_inputs/extract-chunk-{A,B,...}.md`. Capture extraction lineage explicitly — every chunk file is an authoritative signal-lineage anchor referenced at Phase 6's Question-Resolution Audit.

**Establish the suite folder.** Per `rules/context-management.md` §2.6.1, every `_inputs/` and `_spec/` directory is a direct child of a plan-suite folder. Two sub-cases:

- **Suite name known up front (`--suite-name`):** create `{suite}/_inputs/forge.md` directly.
- **Suite name not provided:** surface via the structured-inquiry channel (single-select; options derived from a prose-content scan; safe default named per §7.1 of the canonical-channel rule). The question fires before any forge write.
