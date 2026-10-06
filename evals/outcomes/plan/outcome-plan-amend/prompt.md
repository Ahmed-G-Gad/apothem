---
description: Amend a suite without destroying prior decisions.
tags: [outcome, 'pipeline:plan', 'component:plan-amend']
expected_outcome: PLAN-NOTES.md records the export cut; the earlier decisions D1-D3 remain.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:plan-amend amend .apothem/plans/notes-app/

Change: CSV export is cut from this release. Drop phase 03 and update the artifacts that depend on it.

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
