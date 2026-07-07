<!-- SPDX-License-Identifier: MIT -->

# Agent-Facing Folder Guidance Template

Per the root-only convention at
[`../rules/agents-md-convention.md`](../rules/agents-md-convention.md), the
repository carries a **single agent-facing canon** at the root `AGENTS.md`, and
per-folder operating guidance lives in each folder's `README.md` — which serves
both the human reader and the agent reader. **The convention does NOT require a
separate per-folder `AGENTS.md` companion beside each `README.md`:** the folder
`README.md` is the agent-facing surface, so authoring a standalone
`<folder>/AGENTS.md` is optional, not expected.

Use this template in one of two ways:

- **Preferred — author a folder README's agent-facing section.** Adapt the
  fenced skeleton below into a section of the folder's `README.md` (a heading
  such as `## For agents` followed by the same body) so one file orients both
  readers.
- **Rare — author a standalone companion.** Where a folder genuinely needs a
  standalone agent companion beyond its README, copy the skeleton into
  `<folder>/AGENTS.md`, keep the frontmatter and the single-line SPDX license
  header, replace every `<PLACEHOLDER>`, and delete the guidance comments.

## What to fill, and what to leave out

- **Fill** the folder's purpose, the load-bearing artifacts an agent touches,
  the local conventions an agent MUST respect, the safe-operation guidance,
  and the upstream/downstream edges.
- **Leave out** volatile inventory counts (e.g., "12 files"); they go stale.
  Describe the operating contract, which is stable.
- **Stay agnostic.** Privilege no single harness, model, or tool; pre-set no
  model or effort preference. A folder describing one harness adapter names it
  by its catalog slug, never by a privileging brand phrase.
- **Stay canon-coherent.** Extend the root `AGENTS.md` canon; contradict none
  of its shared claims (plans locality, authorship headers, ambiguity
  handling, naming, release freshness, human-only authorship, plain-language).

## Skeleton

```markdown
---
name: <FolderName>
version: <semver, e.g. 0.1.0>
updated: <YYYY-MM-DD>
description: Agent-facing operating guide for the <folder/path> folder.
scope: folder
portability: repo-local
---

<!-- SPDX-License-Identifier: MIT -->

# <folder/path> — Agent Guide

> **Role.** <One sentence: what this folder is for and what depends on it.>

## What lives here

<The load-bearing artifacts an agent touches and how they are organized —
the artifact CLASSES and their roles, not a file-by-file count. One short
paragraph or a compact list.>

## Conventions an agent must respect

<The concrete invariants for acting in this folder. Examples to adapt:
file-header form, frontmatter contract, naming scheme, where this folder's
artifacts register (an index/README/registry), gate requirements that run on
a change here, and any mutation guard.>

## Operating in this folder

<How to add, modify, or remove an artifact here safely, and which checks
verify the change. State the command(s) that validate a change to this
folder (lint, type-check, the relevant conformity matcher, tests).>

## Relationships

- **Consumes:** <upstream folders/artifacts this folder depends on.>
- **Produces:** <downstream consumers of this folder's artifacts.>
```
