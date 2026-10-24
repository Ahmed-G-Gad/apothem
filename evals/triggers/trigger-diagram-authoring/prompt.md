---
description: A request in diagram-authoring's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:diagram-authoring']
expected_outcome: Claude invokes the diagram-authoring skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Draw a sequence diagram of our login flow between the browser, the API gateway and the auth service, validate the syntax, and export it as an SVG file.
