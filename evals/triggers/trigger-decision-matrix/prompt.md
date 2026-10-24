---
description: A task decision-matrix exists for, phrased as a user would type it.
tags: [trigger, 'class:skill', 'component:decision-matrix']
expected_outcome: Claude invokes the decision-matrix skill through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

We have to pick a message queue for our order pipeline: RabbitMQ, Kafka, or SQS. Cost, operational burden, and ordering guarantees all matter, and we cannot run anything self-hosted on the ops side. Help me weigh the trade-offs and tell me which one to choose.
