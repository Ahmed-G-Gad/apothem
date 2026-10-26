<!-- SPDX-License-Identifier: MIT -->

# Figure Integrity

Reference surface for the [`research-suite`](../SKILL.md) skill, read by
`/research-analysis` (Phase 5, the visual-leverage bar), by `/research-review`
when it scores a paper's figures, by `/research-publish` when it formats them for
a venue, and by the `diagram-authoring` skill when it draws a data-driven chart.
Houses the honesty, disclosure and accessibility floor a research figure meets
before it is embedded in a paper. Loads selectively, beside `SKILL.md`, so the
router's entry-point stays tight.

This surface adds operational detail to an existing rigor mandate: it
operationalizes **R7 — Statistical rigor** (a figure carries the interval and the
replication unit its claim rests on), with the provenance rule and the
experimental-image rules serving **R2 — Reproducibility**. It introduces no new R-mandate; R1–R10 is a closed set of ten.
It states properties a figure has and fixes no palette, library or numeric
threshold; the host's chart tooling and the venue's requirements supply those.

## Encoding Honesty

- **A bar or filled area is read from its baseline.** Its length or extent encodes
  the quantity, so the axis starts at zero or at another baseline the quantity
  has. Where no baseline is meaningful, a point or interval mark replaces the bar.
- **Breaks are named; ranges are earned.** A point or line plot MAY use a non-zero
  range. A drawn axis break is named in the caption, and the range is neither
  widened past the data to flatten variation nor trimmed to exaggerate it.
- **Panels read together share limits.** Panels compared side by side use the same
  axis limits, or the caption states that they differ and why.
- **One quantity per axis.** A second y-axis needs a justification in the caption;
  without one, the series go in separate panels.
- **Size encodes by area.** A mark whose size encodes a quantity scales its area,
  not its radius. Perspective 3D is not used where a flat plot shows the
  comparison.
- **A logarithmic axis cannot show zero.** The axis label names the transform, and
  the caption says what became of zero and negative values.

## Uncertainty and Raw Data

- **Say what the interval measures.** An error bar or band is either the spread of
  the observations (a standard deviation, a percentile range) or the precision of
  an estimate (a standard error, a confidence interval, a credible interval); the
  label names which and, for an interval on an estimate, its level. The caption
  states how many independent units each interval rests on and what those units
  are, counted per
  [`analysis-discipline.md`](analysis-discipline.md#unit-of-analysis-and-dependence).
- **Show the observations where feasible.** An aggregate mark hides the
  distribution beneath it; individual points, or a density or binned summary at
  large n, accompany it.
- **A significance mark names its test.** The mark states the test and the
  multiplicity correction applied. It is never presented as a measure of
  uncertainty and never replaces the interval.
- **A gap stays a gap.** Missing and censored values are marked distinctly, and no
  line is drawn across a gap. The caption counts the values it cannot place and the
  values removed by an exclusion rule, and names that rule.

## Binning, Smoothing and Normalization

- **Binning.** The caption or methods give the bin edges or width and the rule that
  fixed them. A conclusion that changes under a second defensible binning is shown
  under both.
- **Smoothing.** The method and its bandwidth, window or span are stated. A smoothed
  or fitted curve is drawn apart from the observations, names its model, and stops
  where the measurements stop.
- **Normalization.** The axis label or caption gives the formula and the reference
  it divides by or subtracts (baseline, control, total or reference group), and
  the supplementary material keeps the unnormalized values.

## Colour and Accessibility

- **Match the colour scale to the data.** A sequential scale encodes ordered
  magnitude, a diverging scale encodes deviation around a meaningful centre (zero,
  a reference value, the SESOI) and is used for nothing else, and a categorical
  scale encodes unordered groups. A rainbow scale is not used for ordered data. A
  colour bar carries its unit and any transform, and compared panels share colour
  limits.
- **Colour is never the only cue.** A reader who cannot tell the hues apart MUST
  still be able to tell the series apart, so each series carries a second cue, such
  as a marker shape, a line style or a direct label (WCAG 2.1 success criterion
  1.4.1, Use of Color).
- **Marks keep contrast against their background** (WCAG 2.1 success criterion
  1.4.11, Non-text Contrast). The figure SHOULD stay distinguishable when
  reproduced in grayscale, which the second cue on each series already supports.
- **A complex figure SHOULD carry a text description or a data table** that gives
  the finding and the numbers it rests on (WCAG 2.1 success criterion 1.1.1,
  Non-text Content).

The success criteria are those of the W3C's Web Content Accessibility Guidelines
2.1 (<https://www.w3.org/TR/WCAG21/>). The guidelines address web content; this
surface applies the criteria by analogy to a figure in a paper, and a venue rule
that is stricter governs.

## Provenance and Final-Size Inspection

- **A figure is a view of recorded records (R2).** A script generates it from a
  recorded data path, with the seed and version pins recorded, and no value is
  edited or redrawn by hand. The figure carries the diagram metadata header per
  `rules/visual-leverage.md`.
- **Inspect the delivered file at the size the reader sees it.** Labels stay
  legible, line weights stay visible, fonts are embedded, and no raster has been
  enlarged past its captured resolution. The venue's requirements for size and
  format govern (`/research-publish` Phase 2).

## Experimental Images

This section applies to a micrograph, gel, blot, photograph or any other image
presented as an observation.

- **The original stays traceable.** The unprocessed file is retained and named
  in the deposit, and the figure can be traced to it.
- **Adjustments are global and stated.** Brightness, contrast, gamma, cropping and
  colour mapping are applied to the whole image and named in the legend or methods,
  and none of them hides or creates a feature the original does not support.
- **A seam is shown.** A composite, or panels taken from different gels, exposures
  or experiments, is divided by a visible boundary and says so in the legend.
- **No region is treated apart from the rest.** No region is sharpened,
  smoothed, cloned or erased on its own, and background is not cleaned up region
  by region.
- **Scale and resolution are honest.** An image of a physical object carries a scale
  bar or a stated magnification, and enlargement past the captured resolution is not
  presented as added detail.

## Bindings (§0.j five-direction)

- **Drives →** ● The figure and table decisions in `/research-analysis` (Phase 5, M9). ● The Clarity and statistical-review axes of `/research-review`. ● The figure-format line of the `/research-publish` submission checklist. ● The experimental-image checks of the `/research-review` consistency audit. ● The data-driven chart step of the `diagram-authoring` skill.
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the figure-integrity floor loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R7 mandate this surface operationalizes, with its R2 provenance aspect).
- **Cross-bound with ↔** ↔ [`references/analysis-discipline.md`](analysis-discipline.md) (the unit of replication, the interval type and the missing-data handling a figure reports). ↔ [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md) (the plot types a head-to-head comparison shows; this surface governs how they are drawn). ↔ [`references/experiment-program-scaffold.md`](experiment-program-scaffold.md) (a figure is a view of the records, never an independent source of a number). ↔ `rules/visual-leverage.md` (the M9 metadata header).
