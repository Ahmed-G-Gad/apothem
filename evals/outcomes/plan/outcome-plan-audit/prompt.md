---
description: Audit a suite with a planted gap (phase 03 has no acceptance criteria) and persist a report.
tags: [outcome, 'pipeline:plan', 'component:plan-audit']
expected_outcome: An audit report under the suite's _outputs/ that names the missing acceptance criteria.
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit, Skill, Agent, TodoWrite]
---

<!-- SPDX-License-Identifier: MIT -->

/apothem:plan-audit .apothem/plans/notes-app/ --cap 1

This run is non-interactive: nobody can answer questions. Where you would ask, take the option you would recommend, state it as an assumption, and continue.
