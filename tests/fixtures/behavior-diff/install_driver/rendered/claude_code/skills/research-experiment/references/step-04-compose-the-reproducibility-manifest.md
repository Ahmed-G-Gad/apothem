<!-- SPDX-License-Identifier: MIT -->

### Phase 4 — Compose the Reproducibility Manifest

Compose `{suite}/_outputs/reproducibility-manifest.md` so an independent party re-runs the study to the same observations without consulting the operator. The manifest carries:

- **Environment** — the Phase 1 snapshot (OS, runtime, dependency version pins, hardware-relevant facts, locale).
- **Containerized / pinned environment** — where the protocol is computational, a **container image or pinned environment specification** (a `Dockerfile` / OCI image digest, a `conda`/`uv`/lockfile-pinned environment, or the host-ratified equivalent) that an independent party instantiates to reproduce the exact runtime, rather than re-deriving the dependency set by hand (R2/R8, NASEM 2019 <https://nap.nationalacademies.org/catalog/25303/>). The image digest or lockfile hash is recorded so the environment is byte-identifiable.
- **Seed(s)** — every seed in force.
- **Protocol log** — the ordered steps as executed, with the positive/negative-control outcomes and the deviations from preregistration flagged per R5.
- **Version pins** — every dependency at its exact resolved version, commit-pinned where the source is a repository, never a floating range.
- **Reproducibility floor** — the explicit binding of the pinned environment + the fixed and recorded seeds + the logged hardware as the R2 reproducibility floor of a comparative study, cross-referencing the Phase 1 compute-utilization / execution plan, per `skills/research-suite/references/compute-utilization.md`. These three together are the floor an independent party stands on; a floor that is followed but not recorded here satisfies nothing an external reader can check.
- **Data manifest** — the raw-data file paths, their schemas/units, and a content hash per file so re-run output is byte-comparable.
- **Re-run recipe** — the exact command sequence, working directory, and inputs that reproduce the run.

Apply incremental generation per `rules/large-file-generation.md` when the manifest exceeds 500 lines. Emit `{suite}/_outputs/experiment-log.md` and `{suite}/_outputs/reproducibility-manifest.md` with the canonical sections enumerated in `## Output`.
