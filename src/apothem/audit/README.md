<!-- SPDX-License-Identifier: MIT -->

# audit

> **Role.** Inventory and drift scanners that map the ecosystem and surface staleness, leakage, classification, and convention findings. The pipeline runs build → scan → classify/analyze → synthesize → render.

## Build

| File | Purpose |
|------|---------|
| `build_inventory.py` | Walk an ecosystem root and produce a machine-readable inventory of every artifact. |
| `build_capability_graph.py` | Build a node-edge graph of cross-artifact references (agents → skills, commands → agents). |
| `build_plans_provenance.py` | Per-suite, per-file provenance for every plan suite under `.plans/`. |

## Scan

| File | Purpose |
|------|---------|
| `scan_ai_surfaces.py` | Detailed AI-conventions surface presence and coherence map. |
| `scan_ai_surfaces_coarse.py` | Coarse map of AI-conventions surfaces present in the working tree. |
| `scan_drift_features.py` | Detect references to deprecated or renamed features. |
| `scan_frontmatter.py` | Scan frontmatter consistency across artifact classes that carry it. |
| `scan_header_coverage.py` | Detailed authorship-header coverage scan against the inventory snapshot. |
| `scan_plan_leakage.py` | Detect planning vocabulary leaking into shipped narrative artifacts. |
| `scan_plans_discipline.py` | Detect references to a global user-scope plans directory as a write target. |
| `scan_secrets_pii.py` | Detect secrets, PII tokens, and host-specific absolute paths. |
| `scan_stale_tokens.py` | Detect hard-coded model identifiers, version pins, and stale dates. |
| `check_links.py` | Walk every Markdown file and verify each link target is reachable. |

## Classify / Analyze

| File | Purpose |
|------|---------|
| `classify_artifacts.py` | Assign one classification verdict per inventory artifact. |
| `analyze_graph.py` | Detect orphan nodes and dangling references in the capability graph. |

## Synthesize

| File | Purpose |
|------|---------|
| `synthesize_drift.py` | Synthesise the eight drift-scan outputs into a single findings document. |

## Render

| File | Purpose |
|------|---------|
| `render_inventory.py` | Emit a human-readable Markdown mirror of `inventory.json`. |
| `render_capability_index.py` | Render the Markdown capability-index table in the project README's instruction-surface summary. |

## Support modules

Three entry points above are large enough to have been decomposed. Each keeps
its pipeline role and delegates the parts that are not scanning: the vocabulary
it speaks, the shapes it produces, and the documents it emits. None of these is
a pipeline stage — they are the layers beneath one.

The layering is deliberate and load-bearing: a *model* module holds the
dataclasses, and both the producer and the renderer depend on it. Without that
split the scanner would import its renderer while the renderer imported the
scanner.

### Under `scan_header_coverage`

| File | Purpose |
|------|---------|
| `header_vocabulary.py` | Status, variant, and malformation taxonomies plus the suffix and basename maps — pure declaration. |
| `header_variants.py` | Resolve a path to its header variant, and the exception globs that exempt one. |
| `header_banner.py` | Render the canonical header block for a variant. |
| `header_detect.py` | Read a file head, scan it for a banner, and plan an injection. |

### Under `scan_ai_surfaces`

| File | Purpose |
|------|---------|
| `ai_surface_catalog.py` | The candidate-surface catalog, canonical-section table, and status vocabularies. |
| `ai_surface_parsing.py` | Heading parsing and section detection — pure functions over strings. |
| `ai_surface_model.py` | The three result shapes: one surface's scan, one pair's coherence verdict, one authoring action. |
| `ai_surface_render.py` | Emit `ai-surfaces.json` and its markdown mirror. |

### Under `build_plans_provenance`

| File | Purpose |
|------|---------|
| `plans_provenance_vocabulary.py` | Confidence ladder, destination text, plan extensions, suite-name hints. |
| `plans_provenance_model.py` | The three shapes the pipeline speaks in: scan signals, suite verdict, file record. |
| `plans_provenance_render.py` | Emit `plans-provenance.json` and its markdown mirror. |
| `plan_frontmatter.py` | The frontmatter grammar and the two readers over it. |
| `plan_filename.py` | The slug rule, the H1 reader, and the title precedence between them. |

## Shared / data

| File | Purpose |
|------|---------|
| `_scan_lib.py` | Shared helpers for the drift / classification scan family — inventory loading, narrative-surface filtering, fail-soft text reads, the canonical JSON envelope, the `Hit` finding dataclass. |
| `deprecated-tokens.txt` | Token list consumed by the drift-feature and stale-token scans. |
| `known-projects.txt` | Known-project reference list used during inventory and provenance work. |

## Operating in this folder

- **Canonical JSON envelope.** A scanner reads an inventory snapshot and emits the canonical envelope (`generated`, `scanner`, `inventory-source-sha256`, `hit-count`, `hits`) via `_scan_lib.emit_json`; a new scanner reuses that envelope rather than inventing a finding shape.
- **`Hit` finding shape.** A finding record matches the `Hit` dataclass (`file`, `line`, `signal`, `severity`, `remediation`).
- **Reuse `_scan_lib`.** Recurring scan scaffolding lives in `_scan_lib.py` — extract a shared helper there rather than copy-pasting across scanners.
- **Root convention.** The inventory is built at the *content root* (`src/apothem`, e.g. `build_inventory --root src/apothem`), so its record paths are content-root-relative (`rules/…`, `hooks/…`). The inventory-record-resolving scanners (`check_links`, `scan_frontmatter`, `scan_drift_features`, `scan_plans_discipline`, `scan_secrets_pii`, `scan_stale_tokens`, `scan_plan_leakage`) default `--root` to that content root (`_scan_lib.CONTENT_ROOT`). Repo-root tools (`scan_ai_surfaces`, `scan_ai_surfaces_coarse`, `build_plans_provenance`, `scan_header_coverage`) anchor on the repository root and keep `--root .`; `build_inventory` and `build_capability_graph` require `--root` explicitly (no silent default). The classify and synthesize passes read each scanner's drift JSON from `--audit-dir` (default `.audit/`) by filename, so a non-default `--audit-dir` resolves correctly.
- **Fail-soft reads.** File reads fail soft (UTF-8 with replacement) so a mixed-encoding corpus does not halt a scan.
- The plans-discipline and plan-leakage scanners encode the canon's plans-locality and plain-language claims — keep them coherent with the root canon; never weaken them in the per-scanner logic.
- **Adding a stage module:** place it in its pipeline stage, reuse `_scan_lib` for inventory loading and JSON emission, and emit the canonical envelope. **Modifying a scanner:** preserve the output schema downstream synthesis depends on. Surface any ambiguity in classification verdicts through structured inquiry or a `TODO(clarify)` marker — never invent a verdict.
- Validate a change with `python -m ruff check`, `python -m mypy` for the in-scope modules, and `python -m pytest` (audit-pipeline tests).
