<!-- SPDX-License-Identifier: MIT -->

# Search Record and Study-Level Flow

Reference surface for the [`research-suite`](../SKILL.md) skill, read by
`/research-sources` (Phases 1 to 5) and cited by `/research-synthesis` when it
states a gap. Loads selectively, beside `SKILL.md`. It holds the record of how
the evidence base was searched, the study identity that sits above a source,
the screening disclosures that keep the flow counts auditable, and the
risk-of-bias record.

This surface adds operational detail to R9 (the PRISMA flow and its search
reporting) and to R2 (the search is itself a method a third party can re-run).
`rules/authoritative-referencing-provenance.md` §2 requires a search record
behind every claim about what the literature contains; this surface sets the
fields that record carries and the ledger section it lands in. It introduces no
new R-mandate; R1–R10 is a closed set of ten.

## 1. Where the record lives

The record is the `## Search Record` section of `{suite}/_inputs/source-ledger.md`.
Phase 1 opens it with the planned passes; Phases 2 and 3 complete it. The
discovery lineage in `{suite}/_inputs/notes.md` is distilled into the section
before the notes are deleted. A stage exit that deletes the notes while the
record is missing from the ledger MUST NOT pass the gate.

## 2. The per-pass record

A pass is one query set run against one index or tool for one facet. Each pass
is one row with these fields.

- **Pass and facet.** The pass id, and the sub-query or evidence class it serves.
- **Index or tool, and route.** The index or tool queried, and whether it was a `granted index`, the `open web`, the `in-repo corpus`, or an `operator library`.
- **Query as run.** The exact string submitted to that index, after any translation into its syntax. A query reworded for another index is another pass.
- **Filters and limits.** Date window, language, record type, field restriction, and any result cap.
- **Date run.** The day the pass ran.
- **Reported total.** The count the index states for the query, or `not reported`.
- **Examined count.** The records actually retrieved and read to at least title or abstract.
- **Status.** `complete`, or `incomplete` with the reason: `capped`, `interrupted`, `tool unreachable`, or `turn budget`.
- **Seed.** For a supplementary pass (§5), the sources or terms it started from.

## 3. Reconciliation and incomplete passes

- **Compare the two counts.** A pass whose examined count is below its reported total is `incomplete`. State the shortfall as the pair of numbers and the reason.
- **The identification count is a floor while any pass is incomplete.** The ledger MUST label the count a floor for as long as any pass is `incomplete`, state each shortfall beside it, and MUST NOT present it as the full identification count.
- **Explain a difference, do not force equality.** An index can fold duplicates inside its own total. Record the explanation when the counts differ for that reason.
- **Roll the reconciliation up by evidence class** (§6), because a facet can finish while a class yields nothing.

## 4. Strategy check against known items

Before the counts of a facet are relied on, run its strategy against eligible
items already known: those the spec, the theory grounding, or the operator
names. Record which known items were used and whether each was retrieved. A
known item the strategy misses means the strategy is revised and the pass is
re-run, unless the index does not hold the item; a direct lookup settles that,
and the result is recorded. When no known item exists, record
`no known items; check not run`.

## 5. Supplementary passes

Three supplementary passes extend the main passes. Each MUST run, or be recorded
as not run with the reason, and each is a row in §2 with its seed.

- **Backward chaining.** The reference list of each `included` source.
- **Forward chaining.** The works that cite each `included` source.
- **Term expansion.** Alternate names, acronyms, spelling variants, and the vocabulary of retrieved items, added to the facet's terms and re-run.

The candidates enter at identification and take the same screening and the same
criteria as every other candidate. The flow reports them apart from candidates
found by the main passes. A chaining round that adds no candidate surviving
title-and-abstract screening ends the chaining. With no index that offers
citation data, record `chaining: not run, no index with citation data` and list
it under Gaps; the omission is never silent.

## 6. Evidence classes

Every retained source carries a class for each focus block it feeds (a source can
support one hypothesis and report a null for another): `primary` (it bears on a hypothesis and
supports or tests it), `contrary` (it reports a null, a negative result, a
failed replication, or a stated limitation), `synthesis` (a prior review,
meta-analysis, guideline, or standard), or `background` (a foundational work, a
method or validation precedent, a definition).

- **Search for contrary evidence on purpose.** Phase 1 derives one contrary-evidence facet from the null forms of the hypotheses, with a query group for each null form, and runs it apart from the supporting facets.
- **Search for syntheses and foundational works on purpose.** A facet for each class runs with its own query set.
- **Background works are exempt from the spec's temporal window only.** The exemption and its reason are recorded; every other criterion applies.
- **A synthesis locates primary studies.** Its findings do not count beside the primary studies it pools (§7).
- **Report shortfall by class.** For each class, the ledger gives the examined count and the retained count. A class that retained nothing is written `none found in the searches recorded`; it is never read as consensus or as the absence of contrary evidence (`rules/authoritative-referencing-provenance.md` §3).

## 7. Study identity above the source

A study can have several reports: a protocol, a registry entry, a main results
paper, a follow-up, a secondary analysis, a dataset record. The ledger maps each
source to a study id.

- **Link, do not collapse.** Reports of one study stay separate sources, each with its own citation and extraction, and share a study id. Collapse remains for identical identifiers and for a preprint with its published version.
- **Judge a link from the reports' own statements.** A registry number, a named cohort or dataset, a stated parent study, or an identical sample description. Topical similarity is not a link. A link that cannot be settled is `possible-link` and counts as one study until it is settled.
- **Count studies.** Inclusion counts, corroboration, pooled or effect-size synthesis, and certainty ratings count studies, not reports.
- **Check for shared participants before any pooled synthesis.** Reports whose samples overlap contribute once. Record which report supplies the data for each outcome and list the others as supporting reports.
- **Mark shared data across studies.** Two studies that analyse one collected sample (a cohort, a registry extract, a single data collection) carry a `shared-data` link and do not count as independent of each other. A public benchmark that separate groups each evaluate on their own is a shared resource, not a shared sample: those evaluations are independent runs, and a claim about generalization beyond the benchmark gains nothing from repeating it.

## 8. Flow counts

A record is an entry returned by an index or search. A report is a document
describing a study, sought as full text. A study is the unit of investigation.
The four stage names in `/research-sources` Phase 3 stay; the counts they carry
are these.

| Count | Where the ledger reads it |
| ----- | ------------------------- |
| Records identified, by main passes and by supplementary passes | the search record |
| Records removed as duplicates | the dedup record |
| Records screened, and excluded at screening | the screened-out record |
| Reports sought | records that passed screening |
| Reports not retrieved | the acquisition worklist rows still `unreachable` or `manual-retrieval` |
| Reports assessed for eligibility, and excluded with reasons | the screened-out record, with criterion |
| Studies included | the report-to-study map |
| Reports of included studies | the report-to-study map |

The flow reconciles by subtraction: records identified less duplicates are the
records screened; those screened less exclusions lead to the reports sought;
reports sought less reports not retrieved are the reports assessed; reports
assessed less exclusions are the reports of included studies. A difference
between a record count and a report count is explained by the report-to-study
map. A flow that does not reconcile is a finding.

A report whose full text cannot be retrieved at the eligibility stage enters the
acquisition worklist at that point. It counts as not retrieved while its row is
`unreachable` or `manual-retrieval` at stage exit. A source that stays
unreachable after the operator interview leaves the flow at that count, with
the source-trust decision recorded, and is not counted among the exclusions with
reasons. Eligibility is judged on the text retrieved, and its `basis`
(`full-text`, `abstract-only`, `operator-supplied`, or `secondary-description`)
is recorded.

## 9. Eligibility is independent of rank

- **The spec's criteria alone decide eligibility.** Authority, recency, venue standing, and citation count order candidates; they exclude none at the eligibility stage unless the spec states one as a criterion with its reason.
- **A ceiling trims by rank, and that is a selection step.** Every eligible source dropped by `--max-sources` is recorded `eligible, not extracted (ceiling)` and disclosed per `rules/disclosure-ledger.md`.
- **In systematic-review mode the ceiling is not applied.** The mode is a spec that frames the study as a systematic review or meta-analysis (the research-template systematic-review bundle). If the operator sets a ceiling there, it is a disclosed deviation, and the synthesis states that the evidence base is a subset of the eligible set.

## 10. Reviewer mode and adjudication

Screening, full-text eligibility, risk-of-bias assessment, and extraction each
carry a reviewer mode in the ledger's attestation block.

- **`single model-assisted pass`** is the default. A second run of the same model adds coverage, not an independent reviewer, and does not change the mode (`rules/authoritative-referencing-provenance.md` §6).
- **`independent second reviewer`** names the reviewer's role: the operator or another person who assessed the item without sight of the first decision.
- **`operator-adjudicated`** applies to items where the operator resolved a disagreement or a borderline call through the structured-inquiry channel.

An adjudication record is kept for each item whose first decision changed, and
MAY be kept for any borderline item or full-text exclusion. Each row gives the
item, the stage, the criterion, the first decision, the second decision and who
made it, the resolution, and the date. A disagreement keeps both decisions on
the record.

## 11. Integrity status

Each source in the ledger and its extraction carries an `integrity-status`:
`none-found`, `corrected`, `concern`, `retracted`, `withdrawn`, or `unchecked`,
with the index checked, the date, and the locator of the notice.

- **The article and its notice are separate records.** The field names the notice (its locator, its date, its kind, and one line of what it states), not a yes or no.
- **`none-found` means no notice appeared in the indexes checked on that date.** It never reads as "not retracted". `unchecked` (no reachable index) stays a different value.
- **`retracted` and `withdrawn` are a named eligibility exclusion**, unless the retraction is itself the subject of the study; then the source is included with its status flagged.
- **`corrected`:** extraction reads the corrected version and records the correction. **`concern`:** claims from the source are marked, and the source is not the sole support for a load-bearing claim while the concern stands.
- **Carry the status forward.** The scout's candidate list carries it so that releasing raw agent output does not lose it; synthesis carries it into the map.
- **Re-check it later.** Status changes after the ledger is written. The `fact-checker` pass that `/research-paper` runs when references are resolved, and the one `/research-publish` runs at packaging, re-checks each cited source's status and records the date.

## 12. Risk-of-bias record

Phase 3 assesses each `included` source. The record keeps what an auditor needs
to re-judge it.

- **Name the instrument.** Give the instrument by name and by the edition or date its own source states, chosen for the study design. Re-check the current edition at the time of use; assume none.
- **Keep the item answers.** Record the answers to the instrument's own signalling or checklist items and the locus in the source behind each. A judgment with no recorded answers cannot be audited.
- **Unreported is not low risk.** An item the source does not let the reviewer settle is recorded as `no information`.
- **Domains stay separate.** Each domain keeps its own judgment. A summed or averaged score replaces none of them, and the overall judgment follows the instrument's own rule with the domain judgments shown beside it.
- **The unit is the result.** A source that reports several outcomes, comparisons, or time points gets a judgment for each result it contributes, recorded in that result's focus block. The source-level assessment holds the domains common to all its results.
- **Judgments reach the certainty rating.** `/research-synthesis` rates one body of evidence per outcome and comparison; the result-level judgments of its studies feed the risk-of-bias down-rating, and a source-level judgment applies only where no result-level one exists.

## Bindings (§0.j five-direction)

- **Drives →** ● The `## Search Record`, report-to-study map, reviewer-mode, adjudication, integrity-status, and risk-of-bias sections of `{suite}/_inputs/source-ledger.md`. ● The coverage line in the `/research-synthesis` gap derivation.
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the search record loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R2 reproducibility and R9 reporting-guideline mandates this surface operationalizes). ● `rules/authoritative-referencing-provenance.md` (§2 search record, §3 empty-search limit, §6 model-written reading).
- **Cross-bound with ↔** ↔ `commands/research-sources.md` (the stage that keeps the record). ↔ `commands/research-synthesis.md` (counts studies and states coverage). ↔ `agents/research-scout.md` (returns per-pass fields and integrity status). ↔ `agents/fact-checker.md` (counts independent studies). ↔ [`references/comparator-provenance.md`](comparator-provenance.md) (the comparator ledger co-lands with the source ledger).
