<!-- SPDX-License-Identifier: MIT -->

# External-Paper Checks and Reviewer Roles

Reference surface for the [`research-suite`](../SKILL.md) skill, read by
`/research-review --paper`. A paper that belongs to no suite brings no
synthesis, study design, preregistration, or analysis to check against, so the
review checks the paper against itself and against the sources it cites. This
file holds the paper types, the reviewer roles, and the checks that replace the
suite cross-checks. Loads selectively, beside `SKILL.md`.

## 1. Paper type and the checks that apply

Classify the paper once at intake and record the type in the report header. The
type selects the checks.

| Type | Recognised by | Checks that apply |
| ---- | ------------- | ----------------- |
| Empirical method | Proposes a method or model and reports comparisons | All of §3 to §9 |
| Theory | Main results are theorems | §3 in full (proof steps, assumptions), §7, §9; numerical experiments are read as illustration |
| System | A built artifact with measured performance | §5, §6, §7, §8, §9; §4 when components are credited |
| Benchmark or dataset | The data or the benchmark is the contribution | §5 on the benchmark, §7, §8, §9; plus data documentation, licensing, collection ethics, and leakage between splits |
| Survey | Scope, taxonomy, and synthesis are the contribution | §9, §7, and a check that each description of a cited work matches that work |
| Position | An argument is the contribution | §7, §9, and a check that each claim has evidence offered for it |

**Cost detection.** For an empirical method or system paper, note whether the
paper reports cost (parameters, training or inference compute, latency, memory,
data volume) for its own method and for each baseline. A claim of efficiency
with no cost column for the baselines cannot be judged at equal budget; record
it as a finding at MEDIUM, or HIGH when efficiency is the headline.

## 2. Reviewer roles

A role is a lens with a question, a reading list, and a required output. The
default set is `methods`, `domain`, and `skeptical`; `--roles` replaces it.

| Role | Asks | Reads | Produces |
| ---- | ---- | ----- | -------- |
| `methods` | Does the evidence support the claim? | Design, data, metrics, statistics, equations, ablations, baselines, reproducibility pointers (§3 to §8) | Findings with loci; the check rows of §10 |
| `domain` | Is the contribution new and significant, and is the paper honest about its neighbours? | Related work, the claim's scope, the prior results the paper relies on | The novelty delta over the closest work, missing neighbours named by title or identifier, the search record (see below) |
| `skeptical` | If the headline claim is false, what is the cheapest explanation? | The whole paper, taking the claim as the hypothesis to refute | A ranked list of alternative explanations, each with the evidence that would separate it from the claim and whether the paper supplies that evidence |
| `ethics-and-reporting` (optional) | Are people, data, and disclosures handled as the field requires? | Consent and approval statements, data provenance and licence, conflicts, the reporting-guideline checklist, anonymisation | Ethics and reporting findings |
| `statistics` (optional) | Do the tests, intervals, and corrections fit the data? | Every inferential claim | Findings against the statistical-review axis |
| `reader` (optional) | Can a reader from the adjacent field follow the argument? | Abstract to conclusion, figures, terms | Clarity findings |

**Skeptical alternatives to test.** Leakage between training and test data;
selection on the test set; choice of seeds, datasets, or metrics after seeing
results; dropped failed runs; unequal tuning or budget; a metric that rewards
the method's own shortcut; a post-hoc story told as a prediction.

**Domain search record.** The `domain` role keeps the record that
`rules/authoritative-referencing-provenance.md` §2 describes: queries run, items
opened and how far each was read, items unreachable, and where the search
stopped. An empty search never becomes "no prior work" (provenance §3); the
report writes "not found in the searches recorded". The novelty axis confidence
stays at 3 or lower unless the record covers a scholarly index and the closest
works were opened.

**How roles run.**

- Roles run one after another in one reading, each writing its block before
  the next starts. The `skeptical` role starts only after the constructive
  blocks exist, so it attacks the strongest version the others established.
- Roles fill the two logged passes. Pass 1 (constructive): `methods` and
  `domain` state what the paper establishes within their lens. Pass 2
  (adversarial): `skeptical` runs first, then each other role adds the defects
  it found.
- Disagreement between roles is printed as a line in the report (`methods:
  weak; domain: adequate`). It is not averaged. The verdict follows the
  findings, never a vote among roles.
- Agreement between roles is coverage of the paper, not independent
  confirmation: the same reader and the same model sit behind every role.
  Confidence rises only with evidence that was checked.
- Fan-out is opt-in. When the operator asks for independent reads, or the paper
  exceeds what one pass holds, dispatch one subagent per role in a single
  message per `rules/agent-orchestration.md`, each given the claim inventory,
  its role row, and the file path, and returning findings in the finding
  format. Separate contexts reduce anchoring; they do not make the reads
  independent evidence.

## 3. Equation and notation checks

1. **Symbol table.** List every symbol with the place it is defined and every
   place it is used. A symbol used before its definition, defined twice with
   different meanings, or standing for a quantity that carries another symbol
   elsewhere is a finding.
2. **Shapes and units.** The dimensions, tensor shapes, or physical units
   agree on both sides of each equation. Index ranges and summation limits
   match the quantities they sum.
3. **Derivation steps.** Re-derive each headline equation step by step from the
   paper's stated assumptions. Mark each step `holds`, `unjustified`, or
   `fails`. A step that needs an assumption the paper never states
   (independence, smoothness, convexity, boundedness) is a finding that names
   the assumption.
4. **Substitution and limits.** Evaluate the equation at a simple instance
   (zero, one, the identity, a two-point case) and compare with the property
   claimed. An equation claimed to reduce to a known one is reduced, and the
   reduction is shown.
5. **Agreement across forms.** The objective, the algorithm box, the
   pseudo-code, and the prose description state one procedure. A difference
   between the equation in the text and the one in the appendix is a finding.
6. **Claimed properties.** A claim that a quantity is convex, unbiased,
   consistent, monotone, bounded, or differentiable has a proof or a citation,
   and the cited result's conditions hold here (provenance §4).
7. **Constants.** The constants, ranges, and hyperparameters in the equations
   match those in the tables and the appendix.
8. **Unreadable equations.** An equation that did not survive extraction is
   recorded as not read in the not-judged list. The review never states that it
   holds.

## 4. Ablation checks

1. **Coverage.** Every component the paper credits with the gain has an
   ablation by removal or replacement. A credited component with none is a
   finding.
2. **Arithmetic.** Recompute from the table: the full model minus the ablated
   variant equals the reported delta; relative and absolute improvements are
   not mixed; the single-removal deltas compared with the claimed total
   contribution leave no unexplained remainder. A remainder points to an
   interaction the paper does not discuss.
3. **Parity.** Each variant receives the tuning budget, seeds, data, and
   training length of the full model. A tuned full model next to untuned
   ablations inflates every delta.
4. **Variance.** Each delta is compared with run-to-run variation. A delta
   inside the noise is not support for the component.
5. **Interaction.** When the claim is that two components are both necessary,
   a joint removal is expected. One-factor-at-a-time ablations cannot show it.
6. **Setting.** The ablation runs on the data and metric of the headline
   claim, not on an easier setting.

## 5. Baseline and comparison checks

1. **Strength and currency.** The strongest relevant baseline of the period is
   present. A baseline weaker than a simpler known method, or an obvious
   comparator missing from the paper's own bibliography, is a finding.
2. **Provenance of baseline numbers.** Label each baseline number `run by the
   authors`, `copied from its original paper`, or `copied from a third paper`.
   A copied number is valid only when the data split, preprocessing, metric,
   and version match; the review checks the paper's statement that they do.
3. **Parity.** Data, split, preprocessing, metric implementation, tuning
   effort, training and test-time budget, model size, and pretraining data are
   equal across methods. Each asymmetry is a finding.
4. **Tuning.** Baselines are tuned with comparable effort on a validation set.
   The proposed method's hyperparameters are never selected on the test set.
5. **Metric.** The metric answers the claim. The paper reports all the metrics
   it computed, or says why it dropped some.
6. **Statistics.** Each head-to-head comparison meets the replication and
   significance floor in `empirical-comparison-rigor.md`.
7. **Result selection.** The datasets, tasks, and subsets are justified. Failed
   runs and excluded datasets are accounted for.
8. **Looked-up numbers.** A number the review fetches from a leaderboard or a
   source carries the source and the retrieval date. An unreachable source
   leaves the check `unchecked`.

## 6. Footnote, caption, and appendix fairness

Read every footnote, table caption, figure caption, and appendix section
against the main-text claim. A condition that changes the comparison is a
finding whenever the main text claims otherwise: a different split, fewer
trials, other hardware, a smaller baseline, an excluded dataset, "results taken
from", best-of-N selection, a chosen checkpoint, or rounding that decides a
ranking. Record the locus of the footnote or caption.

## 7. Numeric consistency sweep

Compare every number that appears more than once: abstract, introduction,
results, conclusion, tables, and figures. Recompute every derived number.

- Group sizes sum to the stated total; percentages sum to their whole.
- A confidence interval contains its point estimate.
- A p-value matches its test statistic and degrees of freedom where both are
  given.
- The count of datasets, seeds, or runs in the text equals the count shown.
- Figure axes and units agree with the text.

## 8. Reproducibility pointers (no re-run)

The review runs nothing and claims no reproduction. It checks what the paper
gives a reader who wants to re-run it.

- Code and data links exist, carry a licence, and pin a version or commit.
- The environment is stated: versions and hardware.
- Seeds, hyperparameters, and data splits are complete enough to re-implement
  the method from the text.
- The evaluation script or protocol is named.

A link is opened only when the operator allows network access; a link that was
not opened is recorded as `not opened`.

## 9. Citation spot-check

Check the references the headline claims rest on, and every reference the
review itself cites: the work exists, its record matches the entry, and the
opened source supports the sentence that cites it. Use the `citation-auditor`
subagent for a full list. A source that cannot be reached is `unchecked`, never
`not-found`. Look works up by title or identifier only; the manuscript's own
sentences are never passed to a search (`/research-review --paper` step 1).

## 10. Recording a check

Each check lands as one row in the report:

`check · locus · reported · recomputed or observed · result`

The result is `holds`, `fails`, or `not checkable (reason)`. For arithmetic,
print the recomputed value beside the reported one, so a reader sees the check
can return `fails`. A `fails` row becomes a finding with a severity.
A `not checkable` row goes to the not-judged list. A step that has no way to
return `fails` is not recorded as a check.
