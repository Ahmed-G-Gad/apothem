<!-- SPDX-License-Identifier: MIT -->

# Conformity Scenarios

The conformity-gate behavioral scenario harness. Where the per-validator self-tests under [`tests/conformity/`](../../tests/conformity/) check each mechanical matcher in isolation, this harness verifies the **end-to-end behavior** the ecosystem's mandates demand — each scenario is a small fixture corpus paired with a written statement of the verdict the conformity gate must produce against it.

## Files

| Path | Purpose |
|------|---------|
| `verify.py` | The verification driver. Iterates every fixture under `fixtures/F-*-*/`, loads its `expected-behavior.md` frontmatter (`fixture` / `title` / `spec-source` / `mandates`), and records a per-fixture per-mandate verdict matrix from a sibling `verdict.yml` when present, or emits a populated stub the operator fills during the live invocation. |
| `fixtures/F-*-*/` | One directory per behavioral scenario. Each carries an `expected-behavior.md` stating the spec binding and the verdict the gate must reach; scenarios that exercise file-level matchers also carry input samples and an `expected/` directory of golden outputs. |

## Fixture inventory

Each fixture binds to a row of the spec's verification recipe and one or more mandates (`M1`…`M15`):

| Fixture | Scenario |
|---------|----------|
| `F-1-polyglot` | Polyglot repository (M1 — host agnosticism). |
| `F-2-convention-silent` | Host silent on a convention. |
| `F-3-stale-conventions` | Stale conventions in the corpus. |
| `F-4-public-facing` | Public-facing surface change. |
| `F-5-architectural-change` | Architectural change. |
| `F-6-hedging` | Hedging vocabulary in prescriptive prose (M8). |
| `F-7-authority` | Authority / authoritative-data inquiry (M5). |
| `F-8-code-craft` | Code-craft conventions (M13). |
| `F-9-production-readiness` | Production-readiness discipline (M15). |
| `F-10-multi-mandate` | Multiple mandates engaged at once. |
| `F-13-injector-smoke` | Authorship-header injector smoke test — `sample.*` inputs across `.py` / `.js` / `.css` / `.md` / `.json` plus an `expected/` golden set. |
| `F-14-header-form` | Header-form classification — canonical / 5-line / malformed-SPDX / no-header / wrong-variant samples, each with an `expected/*.verdict.txt` golden verdict. |

## Running

CI invokes the driver in strict mode with JSON output:

```sh
python tests/conformity-scenarios/verify.py --strict --json
```

`--strict` fails the run on any fixture whose recorded verdict matrix diverges from `expected-behavior.md`; `--json` emits a machine-readable result for the workflow runner. The driver is also exercised by the suite via `python -m pytest`.

## Conventions

- Every fixture directory is named `F-<n>-<kebab-topic>` and carries an `expected-behavior.md` with the canonical frontmatter.
- Golden outputs live in a per-fixture `expected/` subdirectory, byte-compared against freshly produced output — a regenerated golden is committed deliberately, never drifted.
- Each `expected-behavior.md` carries the canonical authorship banner in HTML-comment form.

## Working in this folder

To add a scenario: create an `F-<n>-<kebab-topic>/` directory with an
`expected-behavior.md` (canonical frontmatter + banner) and, where the scenario
exercises a file-level matcher, input samples plus an `expected/` golden set.
Then run the harness:

```sh
python tests/conformity-scenarios/verify.py --strict --json
```
