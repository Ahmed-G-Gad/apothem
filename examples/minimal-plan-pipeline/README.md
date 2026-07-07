<!-- SPDX-License-Identifier: MIT -->

# minimal-plan-pipeline

A walkthrough of the four-stage plan pipeline: prose refinement → generation → review → execution.

## What it demonstrates

- The full command sequence for taking an unstructured idea and landing it as code.
- The hand-off contracts between each stage.
- Where operator approval gates fire.

## The four commands

| Stage | Command           | Input                                  | Output                              |
| ----- | ----------------- | -------------------------------------- | ----------------------------------- |
| 1     | `/plan-spec`     | Unstructured prose, notes, or sketches | Refined specification at `_spec/spec.md` of the active suite |
| 2     | `/plan-generate`  | The refined specification              | A complete plan suite (preamble, master plan, tracker, notes, phase folders) |
| 3     | `/plan-review`    | The generated plan suite               | Scorecard grades and a findings register |
| 4     | `/plan-execute`   | The reviewed plan suite                | Implemented code, per-phase reports, updated progress tracker |

## Quickstart

Plan suites live under `<project-root>/.apothem/plans/<suite>/` — the sole
canonical plans home, inside the project you are working in, never under a
harness's installed location. A legacy `<project-root>/.plans/` tree is no
longer canonical; upgrade an existing one via `apothem migrate-workspace`. The
snippets below use `<project-root>/.apothem/plans/<suite>/` for that suite
directory.

```sh
# 1. Refine an unstructured idea into a specification.
/plan-spec
# (interactive — answer the elicitation prompts; the result lands at
# <project-root>/.apothem/plans/<suite>/_spec/spec.md)

# 2. Generate the plan suite from the specification.
/plan-generate <project-root>/.apothem/plans/<suite>/_spec/spec.md
# (creates the suite skeleton with phases/, preamble, master plan, tracker, notes)

# 3. Review the generated plan.
/plan-review <project-root>/.apothem/plans/<suite>/
# (returns scorecards and a findings register; iterate if grades are below the threshold)

# 4. Execute the plan, one phase at a time or continuously.
/plan-execute <project-root>/.apothem/plans/<suite>/
# (with continuous-execution discipline at higher seriousness, the pipeline runs
# all phases without intervening prompts)
```

The four stages above are the minimal happy path. The full decomposed cohort
adds `/plan-design` (architecture-bearing suites), `/plan-audit` (closed-loop
finding remediation), `/plan-amend` (revise a suite without losing resolved
decisions), and `/plan-status` (read-only progress reporting) — each operates on
the same `<project-root>/.apothem/plans/<suite>/` directory.

## Operator approval gates

- After `/plan-spec`: review the spec; iterate via the same command if the spec needs refinement.
- After `/plan-generate`: review the master plan and dependency graph; iterate if the decomposition is wrong.
- After `/plan-review`: address findings; iterate if any scorecard is below the threshold for the chosen seriousness level.
- During `/plan-execute`: the per-phase report and the dependency-graph cursor advance the pipeline; operator decisions surface only when authored apply-time work requires them.

## Layout

```text
minimal-plan-pipeline/
└── README.md   ← this file (the example is the walkthrough itself)
```

## Anti-patterns

- Do not skip stages. The pipeline is designed so each stage produces the input the next stage needs.
- Do not start `/plan-execute` against an unreviewed plan at production-grade seriousness — the review stage catches structural defects before they propagate.
- Do not edit phase files by hand mid-execution; the orchestrator owns those during their lifecycle.
