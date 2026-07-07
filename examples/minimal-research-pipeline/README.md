<!-- SPDX-License-Identifier: MIT -->

# minimal-research-pipeline

A walkthrough of the thirteen-stage research pipeline: idea → framing → theory → sources → synthesis → proposal → design → experiment → analysis → paper → review → publish → dissemination.

## What it demonstrates

- The full command sequence for taking a raw research question and landing it as a disseminated, peer-reviewed paper.
- The hand-off contracts between each stage (each stage's Handoff Manifest is the return contract the next stage consumes).
- Where operator approval gates fire.

## The thirteen commands

| Stage | Command                 | Input                                            | Output                                                                 |
| ----- | ----------------------- | ------------------------------------------------ | --------------------------------------------------------------------- |
| 1     | `/research-ideate`      | A domain or problem space                        | Ranked candidate research questions from opportunity-and-gap scanning |
| 2     | `/research-spec`        | A free-form research question, notes, or idea    | A spec-grade research spec at `_spec/research-spec.md` of the active suite |
| 3     | `/research-theory`      | The framed research question                     | The foundational conceptual and theoretical framework                 |
| 4     | `/research-sources`     | The ratified research spec                       | Per-source extractions plus a ranked, screened `_inputs/source-ledger.md` |
| 5     | `/research-synthesis`   | The collected sources                            | A state-of-the-art map, literature matrix, and gap statement at `_inputs/synthesis.md` |
| 6     | `/research-proposal`    | The synthesized gap and theoretical framework    | A fundable, reviewable plan-of-record (SMART aims, feasibility, risk register) |
| 7     | `/research-design`      | The synthesized gap                              | An operationalized study design plus a frozen preregistration at `_inputs/preregistration.md` |
| 8     | `/research-experiment`  | The study design and preregistration             | The experiment log and raw data with full provenance                  |
| 9     | `/research-analysis`    | The raw data and preregistration                 | Preregistered tests with effect sizes and confidence intervals at `_outputs/analysis.md` |
| 10    | `/research-paper`       | The synthesis, design, and analysis              | A paper draft with verified references (no phantom citations)         |
| 11    | `/research-review`      | The paper draft                                  | A peer-review scorecard and severity-triaged required-revision list at `_outputs/review-report.md` |
| 12    | `/research-publish`     | The reviewed paper                               | A venue-formatted submission package (paper, supplementary, cover letter, declarations) |
| 13    | `/research-disseminate` | The accepted paper and submission package        | The dissemination and impact record (preprint, FAIR archival deposit, altmetrics) |

The canonical ordered stage chain is declared by the `/research` orchestrator at
`src/apothem/commands/research.md`: `research-ideate → research-spec →
research-theory → research-sources → research-synthesis → research-proposal →
research-design → research-experiment → research-analysis → research-paper →
research-review → research-publish → research-disseminate`.

## Quickstart

Research suites live under `<project-root>/.apothem/plans/<suite>/` — the sole
canonical plans home, inside the project you are working in, never under a
harness's installed location. A legacy `<project-root>/.plans/` tree is no
longer canonical; upgrade an existing one via `apothem migrate-workspace`. The
snippets below use `<project-root>/.apothem/plans/<suite>/` for that suite
directory. Paper, data, and figure deliverables land at host-natural locations
(`paper/`, `data/`, `analysis/figures/`), never inside `.apothem/plans/`.

```sh
# Drive the whole pipeline as a single wrapped workflow.
/research "does X cause Y"
# (starts at /research-ideate and drives to a disseminated paper; halts at each
# stage boundary for confirmation unless --autonomous is passed)

# Or run a stage at a time. The first-class stage commands stay individually invocable.

# 1. Formulate candidate research questions from a domain.
/research-ideate
# (opportunity-and-gap scanning; ranks candidate questions)

# 2. Frame the chosen question into a research spec.
/research-spec
# (interactive — answer the elicitation prompts; the result lands at
# <project-root>/.apothem/plans/<suite>/_spec/research-spec.md)

# 3. Build the theoretical framework.
/research-theory <project-root>/.apothem/plans/<suite>/

# 4. Collect and screen the sources.
/research-sources <project-root>/.apothem/plans/<suite>/
# (emits per-source extractions plus _inputs/source-ledger.md)

# 5. Synthesize the sources into a SOTA map and gap statement.
/research-synthesis <project-root>/.apothem/plans/<suite>/

# 6. Turn the gap into a fundable proposal.
/research-proposal <project-root>/.apothem/plans/<suite>/

# 7. Design the study and freeze the preregistration.
/research-design <project-root>/.apothem/plans/<suite>/

# 8. Run the experiment and capture the raw data.
/research-experiment <project-root>/.apothem/plans/<suite>/

# 9. Analyze the data per the frozen preregistration.
/research-analysis <project-root>/.apothem/plans/<suite>/

# 10. Assemble the paper draft with verified references.
/research-paper <project-root>/.apothem/plans/<suite>/

# 11. Run the peer-review critique.
/research-review <project-root>/.apothem/plans/<suite>/

# 12. Format for the venue and build the submission package.
/research-publish <project-root>/.apothem/plans/<suite>/

# 13. Drive post-acceptance dissemination and impact.
/research-disseminate <project-root>/.apothem/plans/<suite>/
```

The single `/research` call wraps the stage chain in a dynamic workflow —
independent-critique verification, named return contracts, and a deterministic
result surface — without reimplementing any stage. Pass `--quick` to run
`/research-sources` + `/research-synthesis` only for a one-shot cited report.

## Operator approval gates

- The wrapped `/research` workflow halts at each stage boundary for confirmation
  by default; continuous chaining engages only under the `--autonomous` opt-in.
- Irreversible or outward-facing steps stay per-action gated even under
  `--autonomous`: data collection (`/research-experiment`), publication
  submission (`/research-publish`), and dissemination (`/research-disseminate`).
- Before a downstream stage consumes an upstream Handoff Manifest, the hand-off
  passes a refute-by-default verification panel; a refuted hand-off or a failed
  Sequence Gate halts and surfaces rather than proceeding silently.
- After `/research-review`: address the required-revision list; iterate before
  `/research-publish` if any finding is unresolved.

## Layout

```text
minimal-research-pipeline/
└── README.md   ← this file (the example is the walkthrough itself)
```

## Anti-patterns

- Do not skip stages. The pipeline is designed so each stage produces the input the next stage needs.
- Do not let post-hoc analysis choices masquerade as predictions — the preregistration frozen at `/research-design` fixes the hypotheses and tests before data collection; deviations are disclosed, never silent.
- Do not proceed past a stage whose hand-off the verification panel refuted; remediate at the owning stage and re-verify.

## See also

- [`minimal-plan-pipeline/`](../minimal-plan-pipeline/) — the sibling planning pipeline (`/plan-spec` → `/plan-generate` → `/plan-review` → `/plan-execute`), which mirrors this pipeline-as-workflow shape.
