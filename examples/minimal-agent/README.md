<!-- SPDX-License-Identifier: MIT -->

# minimal-agent

The smallest viable persistent agent definition.

## What it demonstrates

- A flat agent definition file with the canonical five-section body (Mission, Deliverable, Constraints, Context, Return contract).
- Required frontmatter fields (`name`, `description`).
- A return contract suitable for orchestrator consumption.

## How to use it

1. Copy `sample-agent.md` to `src/apothem/agents/<your-agent-name>.md` in your apothem checkout (the active harness adapter then materializes it into the harness's native config location on install / sync).
2. Update the `name` and `description` frontmatter fields.
3. Replace the Mission, Deliverable, Constraints, Context, and Return contract sections with your agent's actual specification.
4. The agent becomes available for orchestrator dispatch via the Agent tool.

## Expected effect

Dispatching this agent produces the canonical greeting line and confirms the agent-dispatch pipeline is operational.

## Layout

```text
minimal-agent/
├── sample-agent.md   ← agent definition with frontmatter
└── README.md         ← this file
```
