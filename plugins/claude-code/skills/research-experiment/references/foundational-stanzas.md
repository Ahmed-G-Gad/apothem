<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror. Spelled out inline here so this command honors them at the surface, not via cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (executing the preregistered protocol and recording raw data with reproducible provenance). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE running the experiment when the study design or the preregistration is absent or the predecessor Sequence Gate is unsatisfied — route back to `/research-design` first. REFUSE editing `_inputs/preregistration.md` to match the executed run — the analysis plan is frozen, and a deviation from it is disclosed in the experiment log, never erased (R5). REFUSE recording a confirming observation while discarding a null or failed trial — every trial enters the log (R3).

### Output Surface

The experiment log and reproducibility manifest land at `{suite}/_outputs/experiment-log.md` and `{suite}/_outputs/reproducibility-manifest.md` per the suite-locality invariant and the `_outputs/` durable-emission surface at `rules/context-management-scratch.md` §2. The raw data lands at a host-natural location discovered per `rules/host-discovery.md` (e.g. `data/`), never inside `.apothem/plans/`. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on `_outputs/` emissions. Raw-data files at host-natural locations honor the host's discovered header convention where applicable. NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

The experiment log and reproducibility manifest are header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector at `scripts/inject-header.{sh,py}` on its own `_outputs/` emissions. Raw-data artifacts at host-natural locations follow the host's discovered file-header and naming conventions per `rules/host-discovery.md` (a `.csv`/`.parquet`/`.jsonl` data file carries no SPDX line; a `.py` collection script does). Every recorded observation carries its provenance inline (timestamp, protocol step, instrument, seed where stochastic); the recording is documentary and append-only — an observation, once logged, is never silently rewritten.

### Structured Inquiry on Ambiguity

When uncertain about the raw-data destination, the seed source for a stochastic protocol, the resolution of a protocol step that cannot execute as written, or whether execution touches data the ethics declaration does not cover (R6), route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Host-ratified data layouts are discovered, not invented, per `rules/host-discovery.md`. Free-form prose questions as primary input are forbidden. NEVER fabricate a data point, NEVER invent a real-world data path, and NEVER guess a version pin — an unrecorded environment fact is a reproducibility hole, marked as such in the manifest, not papered over.
