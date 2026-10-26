<!-- SPDX-License-Identifier: MIT -->

# Talk and Poster Adaptation

Reference surface for the [`research-suite`](../SKILL.md) skill, read by
`/research-disseminate` when it plans a talk or a poster and by
`/research-publish` for the compiled-document check. It houses talk intake, the
time budget, the question and backup list, the paper-to-poster procedure, the
figure rule, the host hand-off, and the compiled-artifact check. Loads
selectively, beside `SKILL.md`, so the router's entry-point stays tight.

This surface adds operational detail to three existing rigor mandates: **R4** as
`/research-disseminate` applies it (a public claim traces to the published
paper), **R2** (a figure is a view of recorded data) and **R7** (the qualifiers
of a result survive condensation). It introduces no new rigor mandate; R1–R10 is
a closed set of ten. The stage posture does not change: a talk or a poster
restates the published paper and adds no claim.

## Scope

- **In scope.** A talk that presents the one paper the publication record covers (a short conference talk, a lightning or spotlight talk, a seminar) and the poster for that paper.
- **Out of scope.** A dissertation defense presents a body of work, and a journal-club talk presents someone else's paper; neither is planned here. For a presentation of a document, `skills/teaching-pack/SKILL.md` with `--slides` builds an outline, and `/research-review` covers critique.

## Talk intake

Before any slide is planned, ask through the structured-inquiry channel per
`rules/interactive-questions.md`. Take the venue's talk and poster constraints
from the venue-rule register in `{suite}/_outputs/publication-record.md` §1. A
constraint the register lacks is read from the venue's official page, and the
page and the date read are recorded in `{suite}/_outputs/dissemination-plan.md`
§3. The plan MUST NOT assume any of these:

- the slot length, in minutes;
- the talk kind;
- the audience, meaning its field and its prior knowledge of the topic;
- whether questions share the slot or follow it;
- the format the venue states for slides (aspect ratio, file type, language).

## Time budget

1. Start from the slot. Subtract the time for in-slot questions (none when they follow the slot), for transitions between sections, and for a reserve the operator confirms. The remainder is the speaking time.
2. Allocate the speaking time to the talk's sections: question and motivation, approach, results, limits and implications, conclusion. The sections MUST sum exactly to the speaking time, and the speaking time plus the in-slot questions, transitions and reserve MUST sum exactly to the slot. The plan prints both sums.
3. Derive the slide count from the allocated time at a pace the operator confirms. The plan states the pace; it never carries a default.
4. Follow the paper's order: question, approach, results, limits, implications. The motivation and background slides carry only what the paper states and cites, and a fresh literature search adds none. The implications slide carries only implications the paper states (R4). A headline number on a slide keeps the qualifiers named in step 5 of the poster procedure (R7).
5. Write the cut plan: an ordered list of what to drop when the talk runs behind, each entry naming its slide. The conclusion and the headline result MUST NOT appear on it.

The arithmetic is the same for every talk kind. A shorter slot removes sections
from the plan and lists them as dropped; it never skips the sums.

## Anticipated questions and backup material

Build the question list from these sources only:

- the residual MEDIUM and LOW findings that `/research-publish` carried into the publication record §1;
- the not-judged list the review report records for each axis, which §1 also carries;
- the limits and threats to validity the paper itself states;
- the ablations and extended results the main talk leaves out;
- questions the operator supplies through the structured-inquiry channel.

A question from any other source is the operator's to add, never the plan's to
guess. Each entry carries the question, the prepared answer, and the locus in the
paper that supports the answer (R4). A question whose honest answer needs
evidence the paper lacks is marked `outside-the-paper`: the prepared reply says
the paper does not address it, and any new evidence routes to `/research-review`;
the plan never answers it with a new claim.

List the backup material beside the questions. Each backup slide names the
question it serves and the paper figure or table it draws from, and follows the
figure rule below. Backup slides sit after the conclusion and are outside the
time budget.

## Poster adaptation

1. **Read the specification.** Take the poster's size, orientation, accepted file type and submission stage from the venue-rule register in the publication record §1. When they are absent, read them from the venue's official page and record the page and the date in the dissemination plan §3, or ask.
2. **Fix the budgets at intake.** Record the number of headline messages, the word budget and the figure budget as operator-confirmed values. The plan carries no default for any of the three.
3. **Choose the headline messages from the paper.** Each headline traces to a contribution the paper states in its abstract or results. A claim the paper makes only in passing is not promoted to a headline.
4. **Map sections to panels.** Record a table with one row per manuscript section: the panel it feeds, what carries over, what is dropped.
5. **Condense with the qualifiers attached.** Every headline number keeps the sample size, effect size and uncertainty interval the paper reports for it, and the limitation the paper attaches to it (R7, R4). A number on the poster without its qualifiers fails the claim-match check.
6. **List what was dropped.** Every section, result and reference left off the poster is listed in the plan, never removed silently.
7. **Point to the full record.** The poster carries the reserved DOI or the archive link from the publication record, so a reader can reach the paper and its evidence. The link passes item 6 of the compiled-artifact check.

## Figures in talks and posters

- A data figure is the paper's own figure file, or it is regenerated from the recorded data by the analysis stage's script (R2). It is never redrawn, traced or re-rendered by a generative image tool or by hand. A regeneration keeps the data, axes, scales and labels of the paper's figure; a change to what the figure shows is a change to a claim.
- The adaptations allowed are cropping, uniform scaling, and font or colour changes made in the regeneration script. A crop never removes an axis, a label or a legend entry, and an edit that touches a plotted mark, an axis or a label is not an adaptation.
- An image that records an observation (a photograph, a micrograph, a scan) is the paper's own file. A generative tool never supplies, extends or sharpens one.
- A conceptual diagram that plots no data is drawn through `skills/diagram-authoring/SKILL.md`, and the plan labels it as schematic.
- The plan keeps a figure-provenance table: the slide or panel, the paper figure number or the regeneration script with its data path, and the adaptation applied.
- A figure is checked at the size the audience sees it, on the projector or at poster reading distance, for label size, line weight and distinguishability without colour, per `skills/research-suite/references/figure-integrity.md`.
- Each results figure SHOULD carry a text alternative of one or two sentences stating what it shows and its main result, in the speaker notes or the alternative-text field.

## Host-skill hand-off

The plan does not itself build the deck or the poster. When the operator asks
for a draft and the host exposes a builder, find a slide, poster or document
skill by capability through `rules/host-discovery.md`, with the same capability
match and the same one-candidate, several-candidates and no-candidate handling as
the hand-off in `skills/teaching-pack/references/slide-outline.md`. The files
passed are the talk or poster plan, the figure-provenance table and the figure
files.

When the builder returns a file, open it if it can be read and compare it with
the plan: slide titles and order, slide count against the budget, every figure
against the provenance table (the paper's file or its regeneration, not a
redraw), and every number against the paper. Report each difference. Record the
skill used and the file passed in the plan; the builder is a tool use for the
statement required by `rules/authoritative-referencing-assurance.md` §5. A deck
or poster the builder did not produce is never reported as made; when no builder
is found, or the stage cannot invoke one, deliver the plan and say that nothing
was built.

## Compiled-artifact check

This check applies to every PDF the stage produces or receives: a poster, an
exported slide deck, the manuscript. A clean build log is not evidence, because
it does not show overlaps, clipped content or print properties. The check reads
the compiled file itself, in four parts. An item that does not apply to a file
(printed codes in a manuscript that has none, a print specification for a file
that is never printed) is recorded as not applicable, with the reason.

**Read from the file.**

1. **Geometry.** Read the exact page dimensions and the page count, and compare them with the venue's or printer's written specification.
2. **Fonts.** List the fonts the file uses. Every font MUST be embedded unless the venue's or printer's specification says otherwise; an unembedded font makes the line `unmet`.
3. **Raster images.** For each raster image, divide its pixel dimensions by its placed dimensions to get the effective resolution, and compare that with the floor the venue or printer states. An image enlarged beyond its pixels adds no detail and is not presented as if it did.
4. **Document properties.** Read the file's metadata fields (author, creator, producer and similar) and compare them with the confirmed author line and the venue's anonymity policy. Under a double-blind policy the fields hold no identity, and the other file-property surfaces in `skills/research-suite/references/blinding-and-disclosure.md` apply (R6).

**Read from the rendered page.**

5. **Layout.** Render each page to an image and inspect the edges, margins, columns, overlaps and clipping, and each figure and table in place. For a large-format poster, also view a reduced-scale render from the distance that corresponds to reading the full size.
6. **Printed codes and links.** Scan or resolve each printed code or link from the rendered page. It MUST reach the destination recorded in the publication record.

**Asked of the venue or the printer.**

7. **Print requirements.** Bleed, safe margin, colour profile, the print-standard PDF variant, and a resolution floor the specification does not state are asked per `rules/authority-inquiry.md`, never assumed.

**Copies.**

8. **Derived files.** A compressed, resized, converted or re-exported copy is a new artifact. Keep the original and run the check again on the copy.

Discover the inspection tooling through `rules/host-discovery.md`; do not
assume a named utility. Run the commands through the host's shell where the
stage is granted one; otherwise list the exact commands for the operator and
read the output they return. Record the commands, the output and the outcome per
item. An item that was not run is `unmet`.

The check reads dimensions, counts, fonts, resolution and document properties.
It does not verify margins or point sizes against the venue's typographic rules,
which the venue's unmodified official template establishes, and it does not
establish anonymity beyond the fields it reads.

## Checklist lines this surface adds

The dissemination-readiness checklist gains one `met` / `unmet` line, with
evidence for `met`, for each of these:

- the talk's sections sum to the speaking time, the speaking time plus in-slot questions, transitions and reserve sum to the slot, and the slide count follows from the speaking time;
- every prepared answer traces to the paper, and each `outside-the-paper` question is routed;
- every figure appears in the figure-provenance table with a paper or regeneration source;
- the poster's section-to-panel map and dropped list are present, and every headline number carries its qualifiers;
- the hand-off outcome is recorded, either the builder and the file passed or the statement that nothing was built;
- the compiled-artifact check passed for each poster or deck PDF the stage produced or received, or is recorded as not applicable because none exists.

## Bindings (§0.j five-direction)

- **Drives →** ● The talk and poster plans in `/research-disseminate` (Phase 2) and the readiness lines it adds at Phase 4. ● The compiled-document check on the manuscript PDF in `/research-publish` (Phase 2 and the submission checklist).
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the talk-and-poster surface loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R2, R4 and R7 mandates this surface operationalizes).
- **Cross-bound with ↔** ↔ `commands/research-disseminate.md` (plans the talk and the poster by this surface). ↔ `commands/research-publish.md` (applies the compiled-artifact check to the manuscript). ↔ [`references/blinding-and-disclosure.md`](blinding-and-disclosure.md) (the anonymity policy the document-properties check enforces). ↔ [`references/figure-integrity.md`](figure-integrity.md) (final-size legibility and colour-independent encoding). ↔ `skills/teaching-pack/references/slide-outline.md` (the hand-off pattern this surface reuses). ↔ `skills/diagram-authoring/SKILL.md` (schematic diagrams). ↔ `rules/host-discovery.md` (tool and builder discovery). ↔ `rules/authority-inquiry.md` (printer-side and venue facts are asked, never assumed).
