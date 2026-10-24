<!-- SPDX-License-Identifier: MIT -->

### Step 2: Ingest Prose

Lean ingestion (CM-12a, CM-24B): extract requirements into a compact numbered list. For normal runs, externalize to PLAN-NOTES.md; for `--dry-run`, keep the extraction in-memory only (no file writes). Deploy a Research Team (CM-25A) for skills scanning and codebase-pattern discovery. Return contract: structured findings, max 500 tokens per agent (CM-25C), required fields (`status`, `findings`, `evidence`, `gaps`), explicit failure behavior (`status=failed` + reason + partial coverage).

- If resuming interrupted generation: Session Start Protocol (CM-14) — including rules from `rules/*.md`.
- Load rules (`rules/*.md`) and relevant skills.
- Read prose from file. If absent, invoke the structured-inquiry channel to elicit it (delegate to `/plan-spec` §1.3 Guided Elicitation Protocol — one invocation per layer with up to 4 questions each per the tool schema; each option's body carries the three-segment annotation per `rules/interactive-questions.md` §3). Canonical input path: `<project-root>/.apothem/plans/{plan-suite-name}/_spec/spec.md`. Only a suite's own `_spec/spec.md` is authoritative for that suite — an `_inputs/` file (a `forge.md` still in elicitation, or a `review-findings.md` from `/plan-review`) is not a valid input and must be promoted first via `/plan-spec`. The directory boundary is suite-local (every suite has its own `_spec/` and `_inputs/` siblings inside its folder; no root-level `.apothem/plans/_spec/` or `.apothem/plans/_inputs/` exists); purpose vocabularies, promotion lifecycle, pre-suite bootstrap, and invariants are specified in `rules/context-management.md` §2.6.1 "Plan-Workflow Directories". If no prose is supplied or the prose body is empty, STOP and invoke the structured-inquiry channel: question `No prose input was supplied; how should generation proceed?`; header `Prose input`; options:
  - `Run guided elicitation (Recommended)`:
    rationale: Delegates to the `/plan-spec` Guided Elicitation Protocol, which surfaces the seven canonical layers and produces a spec-grade prose at `_spec/spec.md` ready for generation.
    recommendation: recommended — cites class 5 rule citation: `commands/plan-spec.md` §1.3 Guided Elicitation Protocol (the canonical mechanism for transforming raw input into spec-grade prose) and class 6 observed-state: empty prose produces vague plans that fail downstream conformity checks.
    default-pointer: Run guided elicitation — safe because the Forge produces a structurally-decomposed specification that downstream generation consumes without ambiguity.
  - `Type a minimal description now`:
    rationale: User supplies the description via Other-text; generation operates on the operator-provided minimal input directly.
    recommendation: acceptable
    default-pointer: Run guided elicitation — minimal-description input may produce vague phase decomposition; the Forge protocol surfaces the gaps the minimal input leaves implicit.
  - `Abort until prose is supplied`:
    rationale: Halts generation; the next invocation waits for the operator to supply prose at the canonical path.
    recommendation: acceptable
    default-pointer: Run guided elicitation — aborting forces a re-bootstrap; running the elicitation protocol produces the prose in the same session.
  `multiSelect: false`.
- Identify Mode, Seriousness, Domain from flags / prose / user.
- [OVERHAUL mode]: verify a target project or corpus exists. If no project context is available, invoke the structured-inquiry channel: question `Which target project / corpus should the overhaul plan operate on?`; header `Target repo`; options:
  - `Current working directory (Recommended)`:
    rationale: Uses the CWD as the target repository root, matching the operator's invocation context.
    recommendation: recommended — cites class 6 observed-state: the operator invoked the command from a specific directory, indicating that directory is the intended target.
    default-pointer: Current working directory — safe because the CWD is the operator's explicit invocation context and reflects their immediate intent.
  - `Path I will specify`:
    rationale: User supplies a repository path via Other-text; generation operates on the operator-named alternative.
    recommendation: acceptable
    default-pointer: Current working directory — out-of-context paths require additional verification; the CWD is the immediately-verified target.
  - `Abort until a repository is set up`:
    rationale: Halts generation; the next invocation waits for the operator to set up a target repository.
    recommendation: acceptable
    default-pointer: Current working directory — aborting forces a re-bootstrap; the CWD path is the immediately-resumable target.
  `multiSelect: false`.
- Parse thoroughly — expand "e.g.", "etc.", "..." to general patterns.
- Maintain ALL original nuances.
