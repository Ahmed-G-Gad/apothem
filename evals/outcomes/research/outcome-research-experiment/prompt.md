---
description: Execute the protocol on provided observations and record provenance.
tags: [outcome, 'pipeline:research', 'component:research-experiment']
expected_outcome: _outputs/experiment-log.md and _outputs/reproducibility-manifest.md.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:research-experiment --suite-name typed-python --data-dir data --seed 7

The observations were collected offline; their raw export is incoming/bug-rates.csv. Log and package them per the protocol.

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
