<!-- SPDX-License-Identifier: MIT -->

# Imagery and Data

Reference for the [`ui-design`](../SKILL.md) skill. This file covers pictures, product captures, icons, logos, video, and charts: where each one comes from, how large it is, how it is framed, and what it MUST NOT pretend to be. Rule ids and grading live in the [rule catalog](rule-catalog.md). A flag in this file that cites no id grades under the catch-all `img-00.<section>`. What the page needs comes from the material inventory in [page anatomy](page-anatomy.md). The hero visual's size is set in [hero](hero.md).

## 1. Where pictures come from

Fill each picture position from the highest tier that works. User material wins any position.

| Tier | Source | Condition |
|------|--------|-----------|
| 1 | The user's own photos and recordings | Always first |
| 2 | Captures of the live product | The product runs or can be started (section 2) |
| 3 | The product rebuilt in HTML and CSS | Capture is impossible (section 4) |
| 4 | Openly licensed photographs, in the theme's treatment | The subject is photographable, and the user approved each pick |
| 5 | Generated stills | The host offers an image generator and the user asked for one |
| 6 | Large type | The page centers on words, or no tier above fits |

Real material makes a page look made. Gradients and drawings in a picture's place make it look generated.

### Openly licensed photographs

Other files call these library photos. They reach the page by one of two routes:

- **From the user.** The user hands over openly licensed photos along with their source pages.
- **From an open archive.** The archive MUST state each photo's license, as Wikimedia Commons does. Ask the user in chat before searching; the search tool does not ask on its own. Search terms name the subject, never the client or the product, unless the user approves that query. Show the user each candidate: its archive page, its author, and its license. Fetch only the candidates the user approves. Each fetch follows [direction and themes](direction-and-themes.md), section "Safe fetching": its address checks and its archive-photo scope.

Rules for both routes:

- Accept four licenses only: public domain, CC0, CC BY-SA, and CC BY. Skip anything else.
- Record five facts for each photo (`cpy-03`): a short id, the license with a link to its text, the source URL of its archive page, and the credit the license requires. The fifth is `modified`, written when a filter, a plate, or a crop alters the photo. The id goes in the build record's `imagery:` field and the build log's `photos:` field. The other four go in the handoff material request ([build record](build-record.md)).
- A modified CC BY or CC BY-SA photo is an adaptation, so its credit names the license and says the photo was modified. A CC BY-SA photo that takes a treatment is credited as CC BY-SA and offered under it, or it is placed untreated.
- MUST NOT type an image address from memory (`cpy-03`). Every address comes from the user or from an archive page fetched in this session. A remembered address carries no license record.
- MUST NOT hotlink stock sites or use paid stock (`cpy-03`). No license record can be made for a hotlinked file, and paid stock needs a license the user holds.
- Each approved file lives in the project and is served from there. [Direction and themes](direction-and-themes.md), section "Safe fetching", sets who saves it and when.
- Accept raster files only: JPEG, PNG, WebP, or AVIF. When a host tool reports both the content type and the file's opening bytes, check both. Otherwise take the type from the fetch response and the file extension, and record the byte check as not run.
- Serve no SVG from an outside source, and no raster file that still carries EXIF or XMP metadata (`img-00.1`). "Safe fetching" in [direction and themes](direction-and-themes.md) sets which SVG files count as project material, how an outside SVG becomes a raster, and how metadata is stripped.
- Credit every one of these photos (section 7).

### Generated stills

Generated stills never start on their own. They need an image generator on the host and the user's request. That holds even when no archive photo fits the subject. Prompt as a photographer: one concrete subject, a place, the light, the lens. Keep text out of the frame, and keep anyone from looking into the camera. Inspect each result and discard any with broken anatomy or broken objects. An accepted still is treated like an archive photo, and the build record names the generator.

### Strategy by subject

| Subject | Lead material | Photo count |
|---------|---------------|-------------|
| A place, material, food, drink, object, craft, outdoor setting, event, or people at work | Photography. The hero photo is the biggest element of the opening screen. It fills the screen edge to edge under the headline. Or it stands next to the copy at the hero visual size in [hero](hero.md), section 6 | Hero plus two to four, one of them large, with pure-content sections between |
| Software | The interface is the hero visual | One or two scene photos at most |
| Word-led pages: docs, APIs, command-line tools, type specimens, manifestos | Type and code | One full-bleed photo band at most |

An off-topic picture is removed. It is never kept to make up a count.

Choosing among openly licensed photos:

- Label each photo by hand before you place it. Note its subject, its mood, and its color temperature (warm, neutral, or cool). Choose by reading those labels against the theme's photo treatment and the section's job. No script picks photos.
- Prefer ids absent from the `photos:` fields of the log entries `rot-01` compares ([rule catalog](rule-catalog.md), `rot-01`).
- Search with a concrete subject. Before you accept a near match, search again around the place, the material, or the activity.

### The remove-it test

Imagine the page with the image deleted. When the visitor would learn nothing less, the image is undersized or idle. Make it larger, swap it, or drop it. Generic establishing shots are a finding (`img-00.1`): a night skyline, a laptop on a desk, an office front.

### Pictures never stand in for facts or people

Numbers, names, and claims are set in type. A stranger's photo MUST NOT pose as a customer, a colleague, or a testimonial (`cpy-02`, [copy and honesty](copy-and-honesty.md)).

## 2. Capturing the product

A real screen persuades better, and more honestly, than a picture of one.

1. **Find it.** Look for a web address, a running dev server, a package with `dev` or `start` scripts, a built app, or a location the user gave.
2. **Start it** only under the run gate in `SKILL.md`, section "Agent operations", with the approval Step 0 obtained. Without that approval, ask the user for a running URL. When none comes, list the needed screens in the material request and continue from source.
3. **Stage it.** Bring it to a state that shows the page's message.
4. **Capture at 2x.** Take the first-screen and full-page sizes in the [pre-delivery checklist](pre-delivery-checklist.md), section 1, or one element by selector. The routes below other than the host's browser are host-conditional. Each runs only when the host offers its tool, and a route that runs project code also needs the run gate and the approval Step 0 obtained. Otherwise list the screens in the material request.
   - Desktop apps built on web views: through their debugging port.
   - Other desktop apps: the operating system's screenshot tool.
   - Mobile apps: the simulator.
   - Command-line tools: real terminal output, set as text in a code block.
5. **Check each capture** for personal data, stray error states, and debug overlays.
6. **Take four:** the main screen for the hero, a large cropped detail further down, a second screen, and the phone layout.

A rebuild is allowed only when the product cannot run yet, or when captures would expose private data. The handoff then lists the screens to capture ([build record](build-record.md)).

## 3. Framing captures

- Show a capture inside a picture position with the theme's radius and an inset hairline (section 7).
- MUST NOT draw browser bars, window dots, address pills, title bars, device frames, notches, or terminal and editor chrome (`img-00.3`). A lone frame around real content is no exception. The static check warns on class and selector names that suggest them; a render or a reading confirms the finding or dismisses it.
- Crop to the most persuasive region. Text stays readable at display size.
- Display at scale 2. Never enlarge past native resolution. Never retouch.
- Mark each capture as a product image. The photo share in section 5 leaves product images out.

## 4. Rebuilding the product

Rebuild only when nothing is reachable: an idea, or a product not built yet. Never mock a product that can be captured.

- Rebuild the main screen in HTML and CSS with genuine controls, the prompt's own words, and the theme's surfaces and type. Use at least 8 elements.
- Sample values MUST read as samples (`cpy-01`, `cpy-02`): `example.com` addresses, generic labels, round amounts. Never figures that read as claims.
- The rebuild sits in a replaceable position (section 8).
- At handoff, list which screens to capture once possible.

A working control, such as a calculator using the user's real prices or a booking form, MAY appear once per page, as a section or as the close. It is not the default hero.

## 5. Scale, crop, and share

### Scale

A photo is large or absent: at least 6 of 12 columns and 440px tall, or full-bleed. A hero photo beside text takes the hero visual size in [hero](hero.md), section 6. Small thumbnails read as clip art. Two exceptions hold. A set of three or more where every image carries a fact MAY run smaller. So MAY the secondary picture in an uneven pair, such as the 4 in 8 + 4.

### Crop and ratio

- One subject per frame, cropped tight and turned toward the text.
- Vary ratios and sizes down the page. Full-width images take 21:9 or 16:9. Images set next to text take the aspect range of the text and visual split in [layout and composition](layout-and-composition.md), "Compositions". Squares come in pairs.
- Pair sizes unevenly, such as 8 + 4 columns.
- Equal-size triplets only for a genuine set: three dishes, three rooms.

### Page share

- Under the hero, photos cover 33% or less of the page area at 1440 wide. Photo-led and project-cards shapes ([page shapes](page-shapes.md)) MAY reach 45%.
- Product images do not count toward the share.
- With three or more pictures present, coverage above 36% is a finding (`img-03.a`). The limit is 45% on photo-led and project-cards shapes.
- Two photo-led sections MUST NOT sit next to each other (`img-03.b`). The section between is carried by the theme's other material: type, figures, rules, color fields, tables, forms, or the product.
- In doubt, remove the least useful picture and state its fact in large type.

## 6. Text over a photo

- Set text on the photo's quietest region. Never center white type on a busy image.
- Lay a scrim of the theme's ink under it, at 35 to 65% opacity, starting at the text's edge and covering only the text's side.
- A theme that rejects gradients uses a flat ink plate instead.
- Text meets the `acc-01` ratios against every part of the image beneath it ([color and surfaces](color-and-surfaces.md)).

## 7. Captions, treatment, frame, and credits

### Fact captions

A caption states one fact from the brief, set as a label next to or under the image. Examples: a plate's price, a room's opening hours, a date, a place. Credits never go in a caption. A stand-in image is never captioned as the user's own people, premises, or goods.

### One photo treatment per theme

Every theme declares one treatment. It applies to every picture in a position, the user's own included, so mixed sources look printed on the same stock.

The filters stay mild by rule. Sepia stays at or below 0.3. Saturation stays between 0.6 and 1. Brightness stays between 0.9 and 1.1. Contrast stays within 0.05 of 1, except that a grayscale base lifts contrast by 10 to 20 percent to keep its tonal range.

| Treatment | What it does | CSS filter |
|-----------|--------------|-----------|
| natural | Leaves the photo as shot | none |
| warm | Pushes toward amber | `saturate(0.9) sepia(0.2)` |
| muted | Pulls color back | `contrast(0.95) saturate(0.7)` |
| monochrome | Drops all color | `grayscale(1) contrast(1.15)` |
| duotone (two tokens) | Gray base, then two plates | `grayscale(1) contrast(1.1)` |
| tint (one token) | Gray base, then plates in one hue | `grayscale(1) contrast(1.1)` |

- **Plates.** Duotone and tint add a `multiply` plate beneath and a `lighten` plate on top, both from theme tokens. A tint on a dark page runs from paper to the token. On a light page it runs from the token mixed 55% toward `ink` to the token mixed 82% toward `paper`, so no literal color enters the mix (`tok-01`).
- **Tonal range.** Pick images with a broad tonal range. A duotone or tint flattens pale subjects, such as snow or white walls, into empty fields.
- **Pseudo-elements.** When the plates use both pseudo-elements, the keyline or scrim moves to a sibling.
- **Adjustments.** A treatment MAY add numeric adjustments. Each takes a value n inside its range and maps to a filter as below. The ranges keep a lone adjustment inside the limits above. When filters stack, their factors multiply: the product of every `saturate()`, of every `contrast()`, and of every `brightness()` in the chain stays inside those limits, and the chain holds one `sepia()` at most. On a grayscale base, the contrast product stays between 1.1 and 1.2.

| Adjustment | Range of n | Filter |
|------------|------------|--------|
| contrast | -5 to 5 | `contrast(1 + n/100)` |
| saturation | -40 to 0 | `saturate(1 + n/100)` |
| vibrance | -80 to 0 | `saturate(1 + n/200)` |
| exposure | -10 to 10 | `brightness(1 + n/100)` |
| highlights | -10 to 10 | `brightness(1 + n/300)` |
| shadows | -10 to 10 | `brightness(1 + n/400)` |
| sepia | 0 to 30 | `sepia(n/100)` |

### Frame

Frame each picture with the theme's radius and a 1px inset outline, offset by -1px. A picture takes no focus, so the `acc-03` row allows this outline at rest. The outline color is `color-mix(in oklch, var(--ink) 8%, transparent)`, with the `ink` share kept between 6 and 10 percent, a token-derived form (`tok-01`). Add the theme's texture where it has one ([color and surfaces](color-and-surfaces.md), section 8). The border-and-shadow limit in [color and surfaces](color-and-surfaces.md), section 7, holds for every frame.

### Credit line

Credit every openly licensed photo in one footer line. The line opens with the label "Photographs" and lists the credits in the footer's small text. Each credit names the author and the license, with a link to the license text, and adds "modified" when a filter, a plate, or a crop alters the photo. The line carries `data-wordcount="skip"`, the marker [copy and honesty](copy-and-honesty.md), section 2, defines, so the page word count leaves it out.

## 8. Replaceable picture positions

A picture the user will replace sits in a named position. Each position is in one of two states:

- **Holding a stand-in.** The position shows something real: an archive photo, a product capture, or a product rebuild. It shows no placeholder wording, ratio notes, or "sample" chips.
- **Empty.** The position shows only its wash. A page carries two empty positions at most (`img-04.a`). Each one is listed in the handoff material request with its size and intended content (`img-04.b`).

A section the user named but gave no material for MAY use one of those two empty positions ([copy and honesty](copy-and-honesty.md), section 13).

**Markup.** A position is a `figure` flagged as a position. It carries:

- an attribute that names the intended content;
- a real size: `aspect-ratio` plus a minimum height, for example 4:5 at 440px;
- `srcset` and `sizes`, intrinsic `width` and `height`, and `alt` per `acc-06` (empty when adjacent text names the subject);
- an `object-position` on the focal point, and the inset outline;
- a fact caption outside the frame.

Each image points at a real file.

- **Swap script.** A small script maps position names to files and swaps them in without moving the layout. When a stand-in's file does not load, the script removes it, and the position is left empty.
- **Loading wash.** The position's `wash` fill shows while loading and in an empty position. When the direction declares `wash-2`, the fill runs from `wash` to `wash-2` ([template](design-md-template.md)).
- **Keep flag.** Children that a swap leaves in place, such as credits or plate numbers, carry a keep flag.
- **Layering.** Text over a photo lives in a sibling layer: the image at `var(--z-raise)`, the text at `calc(var(--z-raise) + 1)` (`tok-01`). Never inside the photo's own position.
- **Limits.** At most 4 positions per row. Subjects with no photo, such as team members or venues, are listed as text with names and roles. They never become rows of blank frames.

### Empty-picture and wireframe checks

- An empty picture is a position, or a gradient block in a picture's place, 160x120 or larger, showing only its wash. Each one counts toward the `img-04.a` limit of two.
- A gradient block in a picture's place that is not a named position is a finding (`img-00.8`). Turn it into a position or remove it.
- Past the limit, fill the extra positions with archive photos or product views, or state their subjects in type.
- A position that renders under 40px on either side at 1440 is a finding (`img-00.8`).

## 9. Responsive images and loading

- Every image has explicit `width` and `height` (`prf-01`). Every image has `srcset` with `w` descriptors. Use `picture` for alternate crops.
- Set `sizes` to the real layout, capped at the container. A half-width image takes `(width >= 90rem) 640px, (width < 60rem) 100vw, 50vw`. A full-bleed image takes `100vw`. `vw` inside a `sizes` attribute is a layout hint; the `100vw` ban in [layout and composition](layout-and-composition.md), "Viewport units and safe areas", governs CSS widths only.
- Offer widths 960, 1280, and 1920. Hero and full-bleed images add 2400 and 2880, which covers 1440 at 2x. Offer no width wider than the original.
- Hero and full-bleed sources need at least 2400px on the long edge. 1920px looks soft.
- Crop with the container: `aspect-ratio` on it, `object-fit: cover`, and an `object-position` that keeps the subject in view.
- The hero image is the largest paint. It gets `fetchpriority="high"`; a lazy hero image is the `warn` source of section 12 (`img-00.12`). An LCP video's poster is preloaded. Every other image below the fold is lazy.

## 10. Banned imagery

Everything in this section is banned. An item that cites no id of its own grades under `img-00.10`.

- **Drawn illustrations** larger than an icon: objects, plants, animals, people, products, buildings, landscapes, scenes. Replace each with a photo, the product, or large type. Abstract filler art where a product view belongs is `img-02.b`.
- **The drawn-illustration test.** The render check treats a text-free SVG of 120px or more as drawn in two cases: it has 3 or more curved paths, or it has 6 or more shapes with 3 or more fills.
- SVG is limited to icons from one set, the user's logo, labeled charts and diagrams of real data or systems, and plain geometry: rules, grids, dot texture.
- **Counting devices:** a quantity shown as a run of identical marks, 24 or more, such as dots, ticks, squares, or bars. Write the number instead. Charts whose marks vary in size or color are exempt.
- **Imitation materials:** a hero UI built from styled divs outside a position.
- **Torn edges:** a `polygon()` clip-path with 12 or more vertices on an image, posing as a torn photo edge.
- **Fake objects and grids:** bevel or emboss effects imitating objects; grid or stripe backgrounds with nothing beneath. A grid needs a canvas, map, or measuring tool under it.
- Illustration packs, mascots, 3D blobs, and isometric scenes.
- Stock faces offered as proof, and invented customer logo walls (`cpy-02`).
- Mesh-gradient blobs, glowing orbs, or aurora effects behind text ([color and surfaces](color-and-surfaces.md)).
- Images that zoom or spin on hover.
- Text baked into images (`img-01`).
- Photos of screens showing another company's interface.

Real geometry stays allowed: diagrams, charts, an animated line.

## 11. Icons and logos

### Icons

- One icon family per page (`img-02.a`); one stroke and one style within it (`pol-05`). Line-style sets are the default. A second set is allowed only for brand or platform marks, in two places at most.
- Take icons from a set already in the project. With none, the material request asks the user to add a named, licensed icon package. Once the user adds it as a project dependency, it is project material and its license is recorded (`cpy-03`). Until then, leave icons out; each control that needed one keeps a visible text label.
- Sizes 16, 20, 24, or 32px, native to the set's grid. A 24-unit viewBox renders at 24px, never 19.
- Color with `currentColor`. Beside multi-line text, align the icon to the first line.
- On the icon side of a button, padding equals the button's vertical padding.
- MUST NOT use emoji as icons (`img-02.a`).
- No icon in a colored disc or tile, and no row of equal columns with an icon over each heading (`img-02.c`).
- No thick colored stripe down a card's side (`img-00.11`).

### Logos

- Show only the user's own logos, in monochrome, one treatment per row.
- Logo height: 20 to 28px in the footer, 32 to 48px elsewhere.
- Show platform marks only for platforms the page names. Take each from an icon set already in the project, or from a file the user supplies.
- When neither exists, fetch the mark under the platform-mark scope in [direction and themes](direction-and-themes.md), section "Safe fetching". The file address comes from the platform's brand or press page fetched in this session, or from the user. The skill saves the file only when the host offers a download tool. Otherwise it asks the user to save the file at a named project path. Serve it from there.
- Never load a mark from a third-party server at run time.
- MUST NOT build a wall of customer logos the user did not supply (`cpy-02`).

## 12. Video and 3D

### Video

- Use footage the user owns.
- A background loop is `muted loop playsinline` with a `poster`, and it carries no `autoplay` attribute. The poster shows by default. Script calls `play()` only when `prefers-reduced-motion` is `no-preference` and the video is in the viewport, and it shows the play and pause button at the same moment. Without script, the poster shows, or the video offers native `controls` (`acc-11`).
- Video that plays on its own meets the baseline rule `acc-11`, and video that carries information meets `acc-23`. The [rule catalog](rule-catalog.md) rows state what each requires.
- Serve AV1 or VP9 in WebM first, then H.264 in MP4. Keep under 2MB per 10 seconds.
- A lazy-loaded hero video, or a lazy first image, is a `warn` source (`img-00.12`). The [rule catalog](rule-catalog.md), section "Grades", states how it closes.

### 3D and motion libraries

Use 3D or WebGL only for a three-dimensional product the visitor turns, always with a still fallback. Motion starts from CSS and registered custom properties. An orchestration library is for coordinating entrances in a component framework. A timeline library is for pages where the timeline is the product ([interaction and motion](interaction-and-motion.md)).

## 13. Charts

### Form follows the data

| Data | Form |
|------|------|
| One value | A stat tile: a large number and a worded qualifier |
| Two to seven values | A row of stats, or horizontal bars |
| A time series | A line chart, or a sparkline inside another component |
| More than 7 categories | A table |
| Parts of a whole | One stacked horizontal bar |

No pie, donut, or gauge charts. No chart with a single bar.

**One series argues.** One series takes the accent. Every other series stays neutral. When every series shouts, none is heard.

### Construction

Hand-write each chart as inline SVG for its data. No chart library.

- **Bars:** 24px thick at most, gaps of 2 to 4px, the axis start set by `dat-01`, only the data end rounded, at 2px radius or less.
- **Lines:** 2px. Markers, 6px or larger, only where an annotation sits or where a marker shape is a series' second cue (below).
- **Grid:** 3 to 5 horizontal gridlines, solid 1px in the rule color, never dashed. The axis is the first gridline, not a heavier stroke.
- **No ornament:** no shadows, 3D, or gradient-filled marks. The one gradient allowed is a sparkline fading to transparent.
- **Sparklines:** no axes, grid, or second color.
- **One y-axis.** Two series in different units become two small charts side by side. Dual axes manufacture correlation.

### Color

- The series that carries the point takes the accent, and a lone series takes it too. Every other series takes a neutral lightness ramp between `ink-2` and `muted`, with steps 12 to 15 points of L apart. The ramp MAY extend past `muted` toward paper while each step meets the `acc-01` non-text ratio. Declare each step as a token (`tok-01`). Assign the steps in a set order and never cycle them. Context and reference series are muted. A chart carries two neutral series at most. Past that, split it into small multiples or label each series directly.
- Every series mark needed to read the chart, such as a line, a bar, or a marker, meets the `acc-01` non-text ratio against the chart ground, or carries a direct text label that states its value (SC 1.4.11). Marks that touch, such as the segments of a stacked bar, meet that ratio against each other, are split by a 2px gap in the ground color, or carry direct labels.
- A ramp along the accent hue, or a second hue, appears only under a declared multi-role palette posture, and only from roles already declared ([color and surfaces](color-and-surfaces.md)).
- Each series carries a cue besides color (`dat-01`, `acc-02`). Give it a direct label at the line's end or on the bar, or a second channel: a dash pattern, a marker shape, or its own position, as in small multiples. A swatch beside a label is extra and never the only cue.
- Labels and values stay in ink or muted tones.
- Numbers use tabular figures ([typography](typography.md)).

### Honesty

- Use real numbers. A missing figure gets a marked blank ([copy and honesty](copy-and-honesty.md), section 13). An invented series is worse than a gap (`cpy-02`).
- Axes follow `dat-01` as the [rule catalog](rule-catalog.md) row states it. A zoomed axis label names its start value, for example "axis starts at 94%".
- Sample data appears only inside a rebuilt product sample or in code. It is internally consistent: totals add up, dates run in order. The material request lists it as sample ([build record](build-record.md), section 6).

**Dashboards.** A dashboard shows fewer, truer numbers: one lead figure tile, one supporting chart, and one table. Not a wall of KPI gauges.
