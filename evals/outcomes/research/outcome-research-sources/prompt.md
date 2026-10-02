---
description: Collect, screen and extract sources from a local corpus.
tags: [outcome, 'pipeline:research', 'component:research-sources']
expected_outcome: _inputs/source-ledger.md listing the fixture studies.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:research-sources .apothem/plans/typed-python/ --max-sources 3

No web access in this run: use only the documents under corpus/ as the candidate sources.

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
