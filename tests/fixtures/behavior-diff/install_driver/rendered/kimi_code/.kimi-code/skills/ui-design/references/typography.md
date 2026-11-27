<!-- SPDX-License-Identifier: MIT -->

# Typography

Reference for the [`ui-design`](../SKILL.md) skill. This file sets the type system: the number of faces, how to choose and source them, the scale, the setting of headings, body text, and labels, and font loading. App screens use the fixed app steps of the [template](design-md-template.md), as [surface classes](surface-classes.md) says. Rule ids come from the [rule catalog](rule-catalog.md). The chosen faces go in the `faces:` field of the [build record](build-record.md) and the log entry, and the reasons for them go on the log entry's `why:` line. A project that keeps a locked `DESIGN.md` ([template](design-md-template.md)) holds its faces there too.

## 1. Family limits

- A page runs on two running families at most: one for display and one for reading (`typ-00.1`). One family MAY do both jobs. `typ-00.1` counts running families only; a single-job outlier is not one.
- A third face MAY join as an outlier with exactly one job: the wordmark, one headline figure, or code. Code and measurements set in one monospace count as one job.
- An outlier that takes a second job becomes a third running family, which `typ-00.1` flags.
- Several weights of one family count as one family.
- Name the outlier and its one job in the build record's `declared:` field.
- Three families in total, with the third as an outlier, raise no finding. More than three fires `typ-02.b`; its [rule catalog](rule-catalog.md) row holds the guard and settles the overlap with `typ-00.1`. Four families is the waivable ceiling that guard reads. Five or more families can never be waived.

## 2. Choosing a face

1. **Choose the class first.** Decide which family of letterform the concept calls for. The classes come in four groups:

   | Group | Classes |
   |-------|---------|
   | Serif | `slab-serif`, `roman-serif`, `high-contrast-serif` |
   | Sans | `geometric-sans`, `grotesk-sans`, `rounded-sans` |
   | Display | `grotesk-heavy`, `display-heavy`, `display-condensed` |
   | Special | `mono`, `pixel`, `handwritten`, `blackletter` |

2. **Shortlist two or three faces** in that class. Section 4 gives the criteria.
3. **Set the page's real headline in each one.** Compare shape and color on the page itself. Never choose by name, fame, or a loose tie to the subject.
4. **Prefer variable fonts.** Use free-license faces unless the user has confirmed a paid license.
5. **Check the log.** On a custom build, check the display face against `dir-00.6` (section 4), which reads the `faces:` fields of the [build log](build-record.md) and `DESIGN.md`. A pairing match is noted as `rep-02`, by the match rule in the [rule catalog](rule-catalog.md), section "Bookkeeping". The skill ships no preset list of faces.

### Sourcing order

1. A free font library whose license allows self-hosting.
2. A free collection of foundry-grade faces licensed for commercial use.
3. A commercial foundry, but only after the user confirms a license. Then ask the user which foundry.

Record each license as `cpy-03` asks ([copy and honesty](copy-and-honesty.md)). Section 11 says how the files load.

## 3. Habitual faces

### Default faces

A default face is the first answer a generator reaches for, so it reads as no choice at all. A face counts as a default when any of these hold:

- It is a CSS generic family or a platform stack: `system-ui`, `-apple-system`, `sans-serif`, `serif`, or `monospace`.
- It ships as the default in the framework or starter the project uses.
- It ranks in the top 20 families of the published popularity list of the font service or library the face comes from. When no such list is at hand, this sign does not apply.
- It is the platform's stock monospace, or Courier New.

Examples: Inter, Open Sans, Lato, Montserrat, Poppins, Raleway.

A default face is fine in two cases: the user named it, or the project already ships it. Name the case on the log entry's `why:` line. In any other case, a default face in the display role is flagged on pages (`typ-00.3`). App screens MAY use a familiar sans.

### Common first answers

Some well-made faces are now the usual pick for their class. One of these MAY be used, but the log entry's `why:` line states the reason. A face counts as a common first answer when it is in the examples below, or when it is a sans that a software company released for its own product and it sets the whole page. It then reads as that company's look.

Examples: Syne, Playfair Display, Bebas Neue, Fraunces, Space Grotesk.

## 4. Selection criteria

### Display faces

A display face defines the direction. A custom build MUST NOT choose a display face that `dir-00.6` rules out; [direction and themes](direction-and-themes.md), section 6, holds its match rule over the log's `faces:` fields and `DESIGN.md`. Judge each candidate on these points:

- **Fit to class.** The face is a clear member of the chosen class at display size, not a borderline case.
- **Shape at size.** Set the real headline at the display token. Check counters, joins, and the gap between letters at that size.
- **Width.** A wide face steps down in the display role only (section 6). A condensed face suits long headings in narrow columns.
- **Figures.** Check that lining figures exist if the headline holds numbers. Where the face sets only old-style figures, set the numbers in the body face.
- **Coverage.** The face covers every language and symbol the page prints.
- **Axes.** A weight or optical-size axis lets one file serve several roles.
- **License.** The license is free for commercial web use, or the user has confirmed a paid one.

Starting points, two or three per class. Each is open-license; check that it passes the criteria before you use it:

| Class | Examples |
|-------|----------|
| `roman-serif` | Libre Caslon Text, Sorts Mill Goudy, Rosarivo |
| `high-contrast-serif` | Bodoni Moda, Rufina, Linden Hill |
| `slab-serif` | Bitter, Josefin Slab, Kameron |
| `grotesk-sans` | Schibsted Grotesk, Bricolage Grotesque, Familjen Grotesk |
| `grotesk-heavy` | Archivo Black, Dela Gothic One |
| `geometric-sans` | Jost, Urbanist, Kumbh Sans |
| `rounded-sans` | Quicksand, M PLUS Rounded 1c, Baloo 2 |
| `display-condensed` | Big Shoulders Display, Saira Condensed, Mohave |
| `display-heavy` | Bowlby One, Shrikhand, Climate Crisis |
| `mono` | Martian Mono, Cutive Mono, Major Mono Display |
| `pixel` | Silkscreen, Jersey 10, Micro 5 |
| `handwritten` | Kalam, Patrick Hand, Nanum Pen Script |
| `blackletter` | UnifrakturMaguntia, Grenze Gotisch, Pirata One |

### Reading faces

A reading face MAY repeat across builds, since it does not define the direction. Judge it on these points:

- a tall x-height and open counters at 16px;
- clear shapes for `Il1` and `O0`;
- a regular, a true italic, and a bold, at the least;
- tabular figures for any page with numbers in columns;
- for code and measurements, a monospace with clear punctuation and a slashed or dotted zero.

Examples: Atkinson Hyperlegible, Readex Pro, and Mulish for sans; Charis SIL, Gelasio, and Vollkorn for serif; Iosevka, Commit Mono, and Victor Mono for monospace.

## 5. Weights

- Use three weights at most across display and body. The wordmark's weight does not count toward that limit.
- Space them far apart, for example 400 with 700, or 300 with 800. Neighboring middle weights blur the hierarchy.
- A dark-theme body weight step on a variable font ([color and surfaces](color-and-surfaces.md)) is the same weight role, so it does not count as a separate weight. A static face keeps its light-theme weight.

## 6. Scale

The [template](design-md-template.md), section "Reference scale", is the only source of the type ratios, the token sizes, and the display exceptions, for pages and app screens alike. This section states none of them. App screens use the fixed `app-text-*` steps there, with no fluid headings ([surface classes](surface-classes.md)). A custom direction keeps the reference scale. Seven roles exist as tokens, each tied to an element: the five fluid roles, plus `text-base` and `text-sm`.

| Role | Token | Element | Measure |
|------|-------|---------|---------|
| Display | `text-display` | `h1` | up to 20ch |
| Smaller display (long hero headings, statements) | `text-display-sm` | `h1` or statement | up to 24ch |
| Section heading | `text-section` | `h2` | up to 30ch |
| Item title | `text-title` | `h3` | up to 40ch |
| Lead | `text-lead` | intro paragraph | 28 to 60ch |
| Body | `text-base` | `p` | 45 to 75ch |
| Small (labels, captions, metadata) | `text-sm` | `small`, `figcaption`, `th` | |

- `text-xs` is a fixed step with no role of its own. It serves secondary reading text, such as badge counts and legal lines, and never goes below the floor in section 8.
- A theme MAY change face, weight, tracking, and case. It MUST NOT add or change steps (`typ-00.6`). On pages, `typ-00.6` checks the type tokens against the template's set: the fixed `text-*` steps, the five fluid roles, and the display exceptions. On app screens, it checks them against the `app-text-*` steps plus `text-base`, `text-sm`, and `text-xs`.
- Display above the template's display ceiling takes only the sizes its display exceptions list, each a fixed clamp, not a scale step. The graphic-number opener is the one in [copy and honesty](copy-and-honesty.md), section 8. The [hero](hero.md) still fits the fold.
- A wide face in the `text-display` role moves down one step, to `text-display-sm`. Every other role, `text-section` included, keeps its step and absorbs a wide face through tracking or weight.
- Past these roles, build hierarchy with weight and color, not with new sizes.
- **Section heading floor.** The median section heading keeps to the floor in [layout and composition](layout-and-composition.md), "The heading group"; below it, `lay-07.b` fires.

### Headline length

Count the characters of the rendered `h1`, then set it by the band it falls in.

| Rendered length | Token |
|-----------------|-------|
| 24 characters or fewer | `text-display`. One short word MAY take the one-word exception of the template's "Reference scale". |
| 25 to 55 characters | `text-display`. |
| 56 to 90 characters | `text-display-sm`, with any manual break at a natural pause. |
| More than 90 characters | None: rewrite the headline ([copy and honesty](copy-and-honesty.md)). |

`cpy-05`'s headline budget ([copy and honesty](copy-and-honesty.md), section 2) binds every page `h1`. The 56 to 90 character bands serve a headline that keeps that budget with long words, or any headline under `copy: verbatim`.

Put manual line breaks only between phrases. Check them at 375px.

## 7. Display setting

- **Tracking.** Normal-width faces take -0.02em to -0.04em. Condensed or extra-heavy faces take 0em to -0.015em. Letters never touch.
- **Leading.** 1.0 to 1.15, tighter as the size grows. Leading of 1.2 on display type looks inherited from the body. Mixed-case poster headings MAY go down to 0.92.
- **Capitals.** An all-caps heading that can wrap keeps its leading at 1.0 or more; aim for 1.02 to 1.08. An all-caps line MAY go tighter only when it cannot wrap at any width in the supported range ([pre-delivery checklist](pre-delivery-checklist.md), section 1).
- **Measure.** Put the `ch` cap on the heading element itself, not on a wrapper.

## 8. Body text

- Body text MUST be 16px or larger (`typ-00.8`). Leading 1.5 to 1.65, or 1.65 to 1.75 on prose-led pages.
- Measure 45 to 75ch (`pol-02`), or 60 to 75ch on prose-led pages. The letter shape ([page shapes](page-shapes.md)) sets its body at 60 to 64ch; this line is the only home of that measure. Intros and captions of one or two sentences MAY narrow to 28ch.
- Never set body text in all capitals. Never justify it without hyphenation. Never track it past 0.05em.
- Lines that render at 88 characters or more, across three or more lines, are flagged (`typ-00.8`).
- Secondary reading text, such as captions and metadata, under 12px is flagged (`typ-00.8`). So are interface text under 11px and multi-line prose with leading under 1.3.

## 9. Labels and small text

Labels, captions, table headers, metadata, tags, chips, and nav links use the body face one size down. They are in sentence case with no added tracking. Lowercase is fine when the direction's voice is lowercase. A theme MAY name one label face instead.

- Small text set in capitals or small capitals, or tracked, breaks the house rule `typ-01` at the size and tracking limits its row in the [rule catalog](rule-catalog.md) states. That row also holds its two exceptions.
- Test it: remove the case change and the tracking, then read the text again. The meaning stays the same, so the styling added nothing.

### Monospace has to earn its place

Monospace belongs to code, figures, and measurements. Monospace anywhere else is flagged (`typ-00.9`): in labels, captions, metadata rows, table headers, or small text. It dresses the page up as technical. A direction built from monospace as its material closes the finding with a waiver line that meets the material guard.

## 10. One weight, style, and color per heading

- A lone italic word inside an upright heading fires `typ-03.a`; fix the heading.
- One word or phrase picked out by color, weight, highlight, or underline fires `typ-03.b`. Its guard is in the [rule catalog](rule-catalog.md).
- Build emphasis from a line break, or from a second line at another size.
- A fully italic display system is flagged (`typ-00.10`); a waiver line that meets the material guard closes it. A shape that requires an italic line, as page shapes sets for quote-hero and letter, does not fire it. A waived system applies to every heading at that level, in a true italic, with synthesis turned off.

## 11. Font loading

- Ship only the weights the page uses.
- Self-host the font files when the license allows it, from files already in the project or supplied by the user; otherwise list the files in the material request and load from the service. Load from a font service also when the license forbids self-hosting or the user asks for the service. The closing report then names its privacy cost: the service receives the IP address of every visitor.
- A font-service request uses one stylesheet link per family, each with `display=swap`, plus one preconnect per font host.
- Self-hosted faces use `font-display: swap`. Give each one a fallback face of similar build: an `@font-face` rule whose `src` is `local()` of named system fonts. Use `local("Arial")` or `local("Helvetica Neue")` for a grotesk, and `local("Georgia")` for a serif.
- Tune that fallback face with `size-adjust` and the three metric overrides: `ascent-override`, `descent-override`, and `line-gap-override`. The first screen then keeps its layout when the web font arrives. Take these values from the project's font files or docs, from the user, or from a WebSearch result; never guess them. When none of these gives them, leave out `size-adjust` and the three overrides, and list the missing metrics in the material request.
- List `system-ui` after the fallback face in the stack, with no tuning. A generic family cannot be named in `local()`, so it takes no overrides.
- Set `font-synthesis: none`. Load a true italic if any heading uses italic.

## 12. Typographic details

- Figures that compare use tabular numerals (`pol-04`).
- Headings use `text-wrap: balance`, so no heading ends on a stub (`pol-03`). Body text uses `text-wrap: pretty`, so no paragraph ends on one word.
- Quotes, apostrophes, ellipses, and number-unit spacing follow [copy and honesty](copy-and-honesty.md), section 5.

## 13. Wordmark

- On pages with a strong tone, set the wordmark in nav and footer in a face other than the reading face. By default this is the outlier's one job.
- Fold the wordmark into the body family only where identity lives in the body voice itself: letters, manifestos, and long documents. Then use that family's display cut or heaviest weight.
- A wordmark set as the body face in semibold looks unbranded. A starting point: weight 600, tracking -0.015em.

## 14. Missing brand font

When the page centers on a typeface the user has not supplied:

1. List the brand face first in the display token.
2. Put a free face of similar build behind it as the substitute.
3. Say so in one caption. Name the wanted face and the substitute on the log entry's `why:` line ([build record](build-record.md)); component and app scope name them in the closing report.
4. Ask for the font files in the handoff's material request.
