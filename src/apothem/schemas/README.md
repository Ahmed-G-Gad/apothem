<!-- SPDX-License-Identifier: MIT -->

# Schemas

JSON Schema definitions, configuration schemas, and fixture files — the validation surface for Apothem's artifact frontmatter and the canonical fixtures the conformity tooling reads. These files ship inside the installed wheel via `[tool.setuptools.package-data]` so downstream tooling can resolve them by package path.

> **Provenance.** [`NOTICE.md`](NOTICE.md) carries the canonical single-line SPDX license header on behalf of every `.json` / `.yaml` / `.txt` file here — those formats cannot carry an in-band header. See `NOTICE.md` for the per-file provenance record; this README describes purpose and consumers.

## Frontmatter schemas

JSON Schema files validating the YAML frontmatter of apothem artifact classes.

| File | Validates |
|------|-----------|
| [`agent.schema.json`](agent.schema.json) | Frontmatter of persistent agent definitions under [`../agents/`](../agents/). |
| [`command.schema.json`](command.schema.json) | Frontmatter of slash-command definitions under [`../commands/`](../commands/). |
| [`output-style.schema.json`](output-style.schema.json) | Frontmatter of output-style definitions under [`../output-styles/`](../output-styles/). |
| [`skill.schema.json`](skill.schema.json) | Frontmatter of skill definitions under [`../skills/`](../skills/)`<name>/SKILL.md`. |
| [`plan.schema.json`](plan.schema.json) | Frontmatter of downstream-project plan files; consumed by `/plan-spec --quick` so plans can be validated without the full prose-refinement pipeline. |
| [`profile.schema.json`](profile.schema.json) | The apothem shared-profile configuration (`~/.config/apothem/profile.yaml`). |

## Profile-schema versioning & migration

The shared profile carries an optional top-level `schema_version` integer
(minimum `1`). The contract is additive and forward-compatible:

- **Optional, read as version 1 when absent.** A version-less profile is a
  version 1 profile (pinned as a literal, not the engine's current version),
  so a future v1 to v2 migration still runs on it; existing profiles need no
  edit. Every scaffold (`profile init`, `quickstart`, a first `install`)
  writes `schema_version` explicitly.
- **Current version is `1`.** The engine constant `_CURRENT_SCHEMA_VERSION` in
  [`../lib/profile.py`](../lib/profile.py) is the source of truth.
- **Additive migration shim.** `migrate_profile` runs at the top of
  `validate_profile`, before schema validation. It forward-migrates a profile
  to the current version through an ordered, append-only migration chain. The
  v1 chain is a no-op — the profile is returned unchanged.
- **Newer-than-supported is rejected early.** A profile stamped with a
  `schema_version` greater than the engine supports raises a
  `profile.version_unsupported` diagnostic — "the profile was written by a
  newer apothem; upgrade the engine" — instead of an opaque
  `additionalProperties` error. A non-integer `schema_version` is left for the
  schema validator to reject.

## Canonical `$id` host

Every `*.schema.json` `$id` resolves under the canonical host
`https://apothem.ahmedgad.com/schemas/<name>.schema.json` (filename segment
preserved). `tests/unit/test_schema_id_host.py` asserts the invariant across
the directory.

## Configuration & manifest schemas

| File | Purpose |
|------|---------|
| [`compatibility-matrix.yaml`](compatibility-matrix.yaml) | Cross-harness compatibility matrix — declares per-rule, per-agent, per-hook, per-output-style, per-skill, and per-schema compatibility across the apothem harness adapters. A reference artifact exposed via `schemas.compatibility_matrix_path()`; install-time asset resolution itself flows through `../lib/propagation-manifest.yaml` and `cohort-manifest.yaml`, not this matrix. |
| [`cohort.schema.json`](cohort.schema.json) | Schema for the cohort manifest — defines the closed cohort set (`core`, `developer`, `security`, `research`, `ai-engineering`, `full`) and the `per_harness_targets` contract that resolves each cohort's native plugin target. Consumed by `cohort-manifest.yaml` (which validates against it) and `tests/unit/test_cohort_contract.py`. |
| [`cohort-manifest.yaml`](cohort-manifest.yaml) | The cohort manifest itself — declares the six cohorts and their catalog member sets, validated against `cohort.schema.json`. Consumers resolve per-harness native targets through `per_harness_targets.source` (`../lib/propagation-manifest.yaml`); asserted by `tests/unit/test_cohort_contract.py`. |
| [`plugin.schema.json`](plugin.schema.json) | Schema for the Claude Code plugin manifest (`.claude-plugin/plugin.json`) — the component-path contract for `commands`, `agents`, and `skills`. Consumed by `build_plugin_manifest` / `_validate_manifest` in [`../lib/plugin_tree.py`](../lib/plugin_tree.py). |
| [`handoff-manifest.yaml`](handoff-manifest.yaml) | Manifest schema for cross-phase handoffs in the plan pipeline. |
| [`advisory-finding.schema.json`](advisory-finding.schema.json) | Output contract for the advisory-mode conformance / security auditor and reporting surface — the finding shape (`id`, `category`, `severity`, `location`, `message`, `next_step`) plus the advisory semantics (findings reported, never blocking unless `strict`). |
| [`header-visibility.yaml`](header-visibility.yaml) | Visibility configuration for authorship-header rendering across surfaces. |
| [`cohort-metadata-vocabulary.yaml`](cohort-metadata-vocabulary.yaml) | Canonical repo-controlled vocabulary — status names, severity names, ownership classes, per-cohort frontmatter key sets (mechanical floor vs authoritative contract), version-field rules, output-contract field shapes, and exemption markers. Each entry names the live artifact (`controlled_by`) that owns its values; `tests/unit/test_cohort_metadata_vocabulary.py` asserts the live schemas and validators agree with the declared values, so drift on either surface fails the gate. |

## Data-surface schemas

Agnostic JSON Schema files validating the records of the memory, contexts, and
continuous-learning surfaces. None carries a tool-specific or vendor-specific
identifier, so the same record applies across every installation target.

| File | Validates |
|------|-----------|
| [`memory-record.schema.json`](memory-record.schema.json) | One durable, operator-portable knowledge record in the memory surface — a fact, convention, preference, insight, or reference. |
| [`context-fragment.schema.json`](context-fragment.schema.json) | One named, injectable prompt or context fragment with an enable/disable switch and activation metadata. |
| [`learning-signal.schema.json`](learning-signal.schema.json) | One captured signal in the opt-in continuous-learning loop — the raw observation the capture stage records once the operator opts in. |

## Fixtures

| File | Purpose |
|------|---------|
| [`authorship-header.txt`](authorship-header.txt) | Byte-exact canonical authorship-header fixture (all variant families). The conformity tooling renders per-variant blocks from these lines. |
| [`header-exceptions.txt`](header-exceptions.txt) | Glob list of file classes exempt from authorship-header injection — a pathspec fixture, one pattern per non-comment line. |
| [`profile.example.yaml`](profile.example.yaml) | Worked example of a shared profile — copy to `~/.config/apothem/profile.yaml` and edit; validated against `profile.schema.json`. |
| [`profile.minimal.yaml`](profile.minimal.yaml) | Minimal valid shared profile — the smallest profile that validates against `profile.schema.json`; consumed by `../cli/_helpers.py`, `__init__.py`, and the profile / rollback / learning tests. |
| [`freshness-token-denylist.txt`](freshness-token-denylist.txt) | Denylist of legacy / deferral / replacement narrative tokens — read by `../conformity/freshness_token_grep.py` to enforce the current-version-only facade. |
| [`reference-token-denylist.txt`](reference-token-denylist.txt) | SHA-256 digests of reference-platform brand / identifier tokens, not the tokens — read by `../conformity/reference_token_grep.py` to enforce own-voice reimplementation. A digest keeps a token out of readable, searchable text but does not hide it: a short name can be recovered by exhaustive search. |

## Other contents

- `__init__.py` — package marker making `apothem.schemas` importable so the schema files resolve by package path at runtime.
- [`NOTICE.md`](NOTICE.md) — the directory's authorship-header carrier and provenance record (already present; not duplicated here).

## Conventions

- `.json` / `.yaml` / `.txt` files carry no in-band authorship header; `NOTICE.md` carries it for the directory class per the spec's authorship-header exception.
- Frontmatter schemas are consumed by the PreToolUse Write hooks (frontmatter-compliance check) and by the ecosystem-audit skill.
- All files in this directory ship in the installed wheel via the package-data declaration in `pyproject.toml`.

## Operating in this folder

- **Resolve-by-package-path ripple.** Matchers, installers, and the PreToolUse hooks resolve these files by package path, so a change here ripples to every consumer.
- **Byte-exact fixtures are contracts.** `authorship-header.txt`, `header-exceptions.txt`, and the denylist fixtures are consumed verbatim by matchers and installers; their content is a contract, not free prose. A whitespace or line change ripples to every consumer — treat a fixture edit as a contract change and verify its matchers and installers still pass.
- **The reference-token denylist has a digest grammar.** Every non-comment line of `reference-token-denylist.txt` is `word sha256:<64 hex>` or `literal <n> sha256:<64 hex>`; `reference_token_grep` reports any other line as a malformed entry and does not match it. Add entries only with `scripts/dev/hash_reference_tokens.py`: run it in a terminal, where it prompts for each token without echoing it, or redirect its input from a file kept outside the repository. A token passed as an argument or through `echo` lands in shell history; never commit one.
- **Schema ↔ consumer agreement.** The cohort-metadata vocabulary and the live schemas must agree; a drift on either surface fails the gate. Change a frontmatter schema and its consuming validator in the same change-set.
- **Agnostic data surfaces.** The memory / context / learning record schemas carry no tool-specific or vendor-specific identifier; keep them portable across every installation target.
- **Adding or modifying a schema:** edit the `.json` / `.yaml` file (no SPDX line), update `NOTICE.md` if a new file class arrives, and update every consumer in the same change-set (the PreToolUse frontmatter check, the audit surface, or a validator that reads the schema).
- Validate with `python -m apothem.conformity.gate --all .` and `python -m pytest` (the cohort-vocabulary test asserts schema/validator agreement).
