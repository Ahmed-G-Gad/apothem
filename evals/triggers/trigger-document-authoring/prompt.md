---
description: A request in document-authoring's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:document-authoring']
expected_outcome: Claude invokes the document-authoring skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Write my thesis from the approved outline in outline.md as a full LaTeX document: check that every citation resolves to a real source, manage the bibliography, and compile it to PDF.
