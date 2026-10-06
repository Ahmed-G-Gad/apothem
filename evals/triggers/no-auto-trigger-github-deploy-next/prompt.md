---
description: A request that matches github-deploy-next exactly. github-deploy-next is user-invoked only
  (a maintainer decision), so the model must not start it on its own.
tags: [no-auto-trigger, 'class:command', 'component:github-deploy-next', user-invoked-only]
expected_outcome: Claude does not invoke github-deploy-next; the user starts it explicitly.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Ship the next release: merge the ready pull requests, bump the version from the commits, roll the changelog, and publish a signed tag.
