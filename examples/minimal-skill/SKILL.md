---
name: minimal-skill
version: "0.1.0"
updated: "2026-06-16"
description: Minimal skill demonstration — surfaces a one-line greeting and shows the canonical SKILL.md frontmatter shape.
archetype: example-template
userInvocable: true
disable-model-invocation: true
allowed-tools: ""
---

<!-- SPDX-License-Identifier: MIT -->

# Hello Skill

> The smallest viable skill. Use it as a template when authoring a new skill folder.

## When to invoke

Invoke this skill when a contributor wants to verify their skill-loading pipeline is working end-to-end without committing to a substantive skill yet.

## Procedure

1. Acknowledge the invocation.
2. Reply with the line: `Hello from minimal-skill — the skill-loading pipeline is operational.`
3. Stop.

## Anti-patterns

- Do not use this skill in production work — it is a smoke test.
- Do not extend the procedure with project-specific logic; create a dedicated skill instead.
