<!-- SPDX-License-Identifier: MIT -->

# Comparator Provenance

Reference surface for the [`research-suite`](../SKILL.md) skill. Houses the
selection and provenance discipline for executed comparators — the baselines a
study runs against, not merely the literature it cites. Loads selectively,
beside `SKILL.md`, so the router's entry-point stays tight.

This surface adds operational detail to two existing rigor mandates — R1
(authoritative sources) and R4 (citation integrity) — for the specific case of
**executed** comparators: baselines a study actually runs, measures, and
compares against. It introduces no new R-mandate; R1–R10 is a closed set of
ten. Where R1 and R4 govern the sourcing and resolution of any load-bearing
claim, this surface operationalizes them for the comparison set a study stands
or falls on, so a headline claim of improvement rests on comparators that are
real, sourced, and fairly run.

## Comparator Selection

The comparison set MUST represent the state of the art the study claims to
advance, drawn across the method families the field itself recognizes.

- **State families in the field's own terms.** The comparator set MUST span the method families the field recognizes, named in the terms the field itself uses; this surface does not prescribe which families exist. A comparison set that omits a family the field treats as current is incomplete and MUST record the omission and its rationale.
- **Prefer nearest-recent, authoritative-origin comparators.** Within each recognized family, selection SHOULD prefer the nearest-recent comparator of authoritative origin — the most current instance a competent reviewer would expect to see contested. A superseded comparator MAY be retained only when the field still treats it as a reference point, and the retention rationale is recorded.
- **Fix the set at design time.** The comparison set SHOULD be fixed in the study design before data collection, so the selection cannot drift toward comparators that flatter the result. A comparator added or dropped after the set is fixed is a deviation and MUST be disclosed.

## Provenance Resolution

Every selected comparator MUST resolve to a retrievable origin before it earns
a place in a headline claim.

- **Resolve to a retrievable source.** Each comparator MUST resolve to a retrievable source — a permalink or DOI that a third party can open and confirm. A comparator whose origin cannot be opened is not yet admissible.
- **Pin the implementation where one exists.** Where a reference implementation exists, the comparator MUST resolve to a commit-pinned artifact — a fixed revision, not a moving branch — so the exact instance run is recoverable. Where no reference implementation exists, the comparator is marked reimplemented, and the reimplementation's provenance is recorded in its place.
- **Never fabricate.** A comparator, a comparator result, or a comparator citation MUST NEVER be invented, approximated from memory, or otherwise fabricated. An invented comparator is a structural failure of the same class as a phantom citation under R4.

## The Cannot-Confirm / Cannot-Fetch Marker

An unsourceable or unfetchable comparator is disclosed, never quietly dropped
and never quietly retained.

- **Mark, do not hide.** A comparator whose source cannot be confirmed MUST carry an explicit `cannot-confirm` marker; one whose artifact cannot be retrieved MUST carry an explicit `cannot-fetch` marker. The marker is recorded in the ledger, not omitted.
- **Exclude from headline claims until resolved.** A marked comparator MUST be excluded from every headline claim until the marker is resolved. The study MAY still record the attempt, but a claim of superiority MUST NOT rest on a comparator that has not resolved.
- **Disclose the gap.** The presence of a marked comparator MUST be disclosed in the study's working trace and carried forward, so a reader sees which parts of the field the comparison could not reach and why.

## The Per-Comparator Provenance Ledger

Each comparator MUST carry a provenance record. The ledger fields are the
minimal set a reviewer needs to confirm the comparator is real, retrievable,
and fairly run.

- **Name / family.** The comparator's identifier and the recognized method family it represents.
- **Source permalink / DOI.** The retrievable origin that resolves the comparator per R1 and R4.
- **Implementation status.** One of `commit-pin` (a pinned reference implementation), `reimplemented` (no reference implementation; provenance of the reimplementation recorded), or `unavailable` (paired with a `cannot-confirm` or `cannot-fetch` marker).
- **Version / config used.** The exact revision, version, or configuration the study ran, so the measured instance is unambiguous.
- **Confirmation status.** Whether the source resolved, is `cannot-confirm`, or is `cannot-fetch`.
- **Fairness notes.** The tuning and budget-parity conditions under which the comparator was run — equal budget, equal tuning effort, and any asymmetry that a fair comparison must disclose.

The comparison set is fixed in `/research-design`, and the ledger is populated
in the comparator/baseline provenance pass of `/research-sources` (Phase 4b);
it co-lands with the source ledger so a single retrievable record carries both
the cited literature and the executed baselines. The `fact-checker` agent
adversarially verifies each comparator source resolves — refute-by-default —
before any comparator earns a place in a headline claim; an entry the
fact-checker cannot resolve is returned to a `cannot-confirm` state.

## Bindings (§0.j five-direction)

- **Drives →** ● The comparator-selection and provenance-ledger decisions in `/research-sources` (Phase 4b — the comparator/baseline provenance ledger). ● The comparison set fixed in `/research-design`.
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the comparator-provenance surface loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R1 authoritative-source and R4 citation-integrity mandates this surface operationalizes for executed comparators).
- **Cross-bound with ↔** ↔ `agents/fact-checker.md` (adversarially resolves each comparator source). ↔ [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md) (the comparators these provenance records govern). ↔ `{suite}/_inputs/source-ledger.md` (where the comparator ledger co-lands with the cited-source ledger).
