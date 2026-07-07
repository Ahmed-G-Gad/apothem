---
name: hello
version: "0.1.0"
updated: "2026-06-16"
description: Minimal slash-command demonstration — prints a greeting and shows the canonical command-definition shape.
argument-hint: ""
disable-model-invocation: true
portability: universal
allowed-tools: ""
---

<!-- SPDX-License-Identifier: MIT -->

# `/hello` — Minimal Greeting Command

## Role

Smoke-test command verifying the slash-command-loading pipeline.

## Instructions

When invoked, reply with the line: `Hello from /hello — the slash-command-loading pipeline is operational.` and stop.

## Inputs

| Argument | Type   | Required | Description                                  |
| -------- | ------ | -------- | -------------------------------------------- |
| (none)   | —      | —        | This command takes no arguments.             |

## Workflow

1. Acknowledge the invocation.
2. Emit the deliverable line above.
3. Stop.

## Output

A single string, exactly the deliverable line.

## Critical rules

- Do not invoke other tools.
- Do not read or write files.
- Do not extend the response beyond the deliverable string.
