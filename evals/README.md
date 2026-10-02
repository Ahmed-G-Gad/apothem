<!-- SPDX-License-Identifier: MIT -->

# evals

> **Role.** The behavioural eval suite: realistic prompts plus graders that check whether Apothem's components fire when they should, stay quiet when they should not, produce their stage outcome, and whether an always-on rule changes behaviour. The cases are plain data in the plugin-eval case format (`schema_version: "1.1"`), so `claude plugin eval` runs them today and another runner can read the same files later.

## Files

| File | Purpose |
|------|---------|
| `case.schema.json` | JSON Schema (draft 2020-12) for one case: `prompt.md` frontmatter, `case.yaml`, and each grader. It also documents how each grader type maps to a runner-neutral check. `tests/unit/test_eval_suite.py` validates every case against it. |
| `triggers/` | 64 trigger cases, one directory per case. |
| `outcomes/plan/`, `outcomes/research/`, `outcomes/audit/` | One outcome case per pipeline stage: 8 plan stages, 13 research stages, 11 audit dimensions. |
| `rules/` | Rule-effect pairs for six always-on rules (the R-12 regression set). |

## Case layout

Each case is a directory whose name is the case name:

```text
<case>/
├── prompt.md        # frontmatter: case fields (tags, limits, tools); body: the prompt
├── graders/<name>.md  # frontmatter: one grader (type and options); body: the rubric of an llm grader
├── case.yaml        # optional: schema_version, name, context.scaffold_script
└── scaffold.sh      # optional: seeds the empty workspace (runs only with --scaffold)
```

Unknown frontmatter keys fail a case at load time, so metadata travels in `tags`:

| Tag | Meaning |
|-----|---------|
| `trigger`, `no-trigger`, `no-auto-trigger`, `outcome`, `rule-effect` | The case kind (exactly one). |
| `component:<name>` | The command, subagent or stage under test. |
| `class:command`, `class:agent` | What kind of component a trigger case targets. |
| `pipeline:plan`, `pipeline:research`, `pipeline:audit` | The pipeline of an outcome case. |
| `d12-user-invoked` | The command is user-invoked only by decision D-12 (`freshify`, `github-deploy-fresh`, `github-deploy-next`). |
| `rule:<name>`, `arm:rule-on`, `arm:rule-off`, `r12-regression` | A rule-effect pair and its arm. |

## Case kinds

- **Trigger (64).** Every model-invocable command and every subagent has a `trigger-<name>` case (a request in its domain, phrased as a user would type it, never naming it) graded by `tool_used` on `Skill` or `Agent` with the component's name in `input_match`, and a `no-trigger-<name>` near miss graded by the same check with `min: 0`, `max: 0`, `arm: both`. The three D-12 commands have `no-auto-trigger-<name>` instead of `trigger-<name>`: a request that matches them exactly must still not start them.
- **Outcome (32).** The prompt runs the stage as a user would (`/apothem:<stage> …`) on a workspace seeded by `scaffold.sh`, and free graders check the artifact the stage contract names (`file_exists`, `regex` over the file or the reply). Audit cases plant one defect per dimension and also assert the audit is report-only (no `Edit` of the seeded sources). No outcome case needs an `llm` grader.
- **Rule effect (6 pairs).** A plugin eval run loads no rules and no `CLAUDE.md`, so each sampled always-on rule has a `rule-<name>-on` and a `rule-<name>-off` case that differ only by `append_system_prompt`, which carries the rule's runtime text (the rule file without frontmatter, SPDX line and `## Bindings`). Sampled rules: `session-closure`, `option-annotation`, `interactive-questions`, `authority-inquiry`, `definitiveness`, `freshness-facade`.

## Grader types, runner-neutral

| Type | Neutral check |
|------|---------------|
| `regex` | A JavaScript-syntax pattern over the final reply (`last_message`), the transcript (`trace`), the created-path list (`files`), or one file (`{source: file, path}`); `match` is `contains`, `not_contains` or `count:N`; case-insensitivity goes in `flags`, never inline. |
| `tool_used` | The number of calls to `tool` whose JSON input matches `input_match` lies in `[min, max]`. |
| `tool_order` | The first matching call of `before` precedes the first of `after`. |
| `file_exists` | A file created during the run matches the `path` glob (or none does, with `exists: false`). |
| `llm` | A judge model votes PASS on the rubric (the grader body) in two of three votes. |

## Running

Every run calls the model and is billed; never run the suite without a cost ceiling. The suite runs against the shipped plugin package, so stage it into a scratch copy of the plugin and keep `plugins/claude-code/` itself untouched:

```bash
tmp="$(mktemp -d)" && cp -R plugins/claude-code "$tmp/plugin" && cp -R evals "$tmp/plugin/evals"
claude plugin eval "$tmp/plugin" --trust-plugin --scaffold --allow-tools Write Edit \
  --model <model-id> --judge-model <model-id> --max-cost-usd <usd> --no-publish --json results.json
```

`--tag r12-regression --ablation none` runs only the rule-effect pairs; `--tag trigger` and so on select one kind. Each case's prompt body opens with the repository's SPDX comment line; the runner sends the body verbatim, so the model sees that one comment line in every case and in both arms.

## Operating in this folder

- **Adding a case:** create `<kind-dir>/<case-name>/prompt.md` and at least one `graders/<name>.md`, tag it, and keep the directory name equal to the case name. Prefer free graders (`regex`, `tool_used`, `file_exists`); an `llm` grader states concrete PASS and FAIL conditions.
- **A grader that must never fire** (`max: 0`) sets `min: 0` and `arm: both`, so the no-plugin baseline is scored the same way.
- **Rule text drifts with the rule.** After editing an always-on rule that has a pair here, run `python scripts/dev/sync_eval_rule_cases.py`; the test fails until the `rule-on` text matches.
- **Run output is not source.** `evals/results/` is written by each run and ignored by git; record a run's `results.json` with the model ids and the cost it reports.
- Validate a change with `python -m pytest tests/unit/test_eval_suite.py` (free; no model call).

## Related

- [`../tests/unit/test_eval_suite.py`](../tests/unit/test_eval_suite.py) — schema validation and the coverage contract.
- [`../scripts/dev/sync_eval_rule_cases.py`](../scripts/dev/sync_eval_rule_cases.py) — keeps the rule-effect pairs in step with the rules.
