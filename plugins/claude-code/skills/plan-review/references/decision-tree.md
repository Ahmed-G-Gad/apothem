<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-04-27 %%
%% provenance: commands/plan-review.md §Workflow %%
%% cross-reference: src/apothem/commands/ (slash-command cohort) %%
flowchart TD
    Start[/plan-review invoked/] --> Suite{Suite files present?}
    Suite -->|no| Recommend[STOP — recommend /plan-generate]
    Suite -->|yes| Focus{--focus argument?}
    Focus -->|yes| Narrow[Audit scoped dimensions only]
    Focus -->|no| Full[Audit all dimensions]
    Narrow --> Baseline[Pre-Audit Baseline registry]
    Full --> Baseline
    Baseline --> ProseAudit{Prose fidelity audited?}
    ProseAudit -->|yes| ProseScore[Prose Fidelity Scorecard]
    ProseAudit -->|no| Skip1[Skip prose-fidelity dimension]
    ProseScore --> ConsistAudit{Internal consistency audited?}
    Skip1 --> ConsistAudit
    ConsistAudit -->|yes| ConsistScore[Internal Consistency Scorecard]
    ConsistAudit -->|no| Skip2[Skip internal-consistency dimension]
    ConsistScore --> Findings[Compile findings registry · severity-count verification]
    Skip2 --> Findings
    Findings --> DryRun{--dry-run?}
    DryRun -->|yes| EmitOnly[Emit scorecards + findings · halt]
    DryRun -->|no| AnyFindings{Findings present?}
    AnyFindings -->|no| Done[Emit clean-bill report]
    AnyFindings -->|yes| AskRevise[structured inquiry: revise · accept-as-is · abort]
    AskRevise -->|revise| Apply[Apply revisions · update plan version]
    AskRevise -->|accept| Done2[Emit findings without revision]
    AskRevise -->|abort| Halt[STOP]
    Apply --> Rescore[Re-run scorecards on revised plan]
    Rescore --> Gate{Post-revision PASS?}
    Gate -->|yes| Done3[Emit revision-impact map · halt]
    Gate -->|no| AskFail[structured inquiry: re-revise · accept · abort]
```

The tree distinguishes scope-narrowing forks (`--focus` reduces dimensional
coverage), audit-mode branches (each dimension activates its own scorecard),
and revision-loop forks where operator decision drives whether findings flow
into applied revisions or stand as advisory output.
