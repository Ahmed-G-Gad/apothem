---
description: A request in vuln-triage's domain, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:vuln-triage']
expected_outcome: Claude invokes the vuln-triage skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Triage CVE-2024-12345 for us: how severe is it, where does our lockfile pull in the affected package, is the vulnerable code reachable, and should we patch, upgrade, mitigate or accept it?
