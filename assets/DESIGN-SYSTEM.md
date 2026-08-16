<!-- SPDX-License-Identifier: MIT -->

# apothem design system

The single source of truth for the apothem brand: the mark, the palette, the
type scale, the spacing rhythm, and the elevation set. Machine-readable token
values live alongside this document in [`design-tokens.css`](design-tokens.css)
(CSS custom properties) and [`design-tokens.json`](design-tokens.json) (W3C
design-token format). Those two files are the reference every surface is
checked against. No surface imports them at build time today — the
documentation site restates the values in its own theme variables — so a token
change has to be carried into each surface by hand, and the values here are
what that carry is verified against.

Dark mode is the default. Every light value is a remap of a dark default, never
the other way around.

## The mark

Apothem is a geometry term: the **apothem** of a regular polygon is the
perpendicular distance from the center to the midpoint of an edge. The mark is
that definition, made radiant:

- a **regular flat-top hexagon** — the polygon,
- **six apothems** fanning from the center to every edge midpoint — five quiet
  in slate, one bold **emerald apothem** to the top edge: the namesake, and the
  only saturated element. The fan reads as one center reaching every facet — the
  product's own story, one shared profile materialized across many destinations,
- the apothems land on the edge **midpoints**, not the visible corners, so the
  eye still reads the distinction the word names: the reach to an edge, not to a
  vertex,
- a faint **inscribed apothem-circle** through the six edge midpoints, drawn
  under the hexagon — the apothem is the circle's radius, so the ring traces the
  apothem distance itself and ties the six reaches into one measured whole,
- a slate **center node** carrying a small **emerald source-node** at its heart —
  the shared origin every apothem departs from — quiet slate **termini** at the
  five other edges, and a bright **emerald terminus** anchoring the namesake.

The mark is frameless: the hexagon is the silhouette, legible on any surface.
Geometry is fixed — hexagon circumradius `R`, apothem `a = R · cos 30° ≈
0.866 R`. The 220-unit master places the center at `(110, 110)` with `R = 80`,
so `a ≈ 69.3` and the apothem runs `(110, 110) → (110, 40.7)`; the inscribed
circle is that same `a ≈ 69.3` radius about the center. The `favicon.svg`
monogram stays deliberately minimal — at tab size the inscribed circle and
source-node would clutter the 16 px silhouette, so it carries only the hexagon
and its emerald apothem.

### Asset coverage

Every brand file, its variant role, and its refresh disposition. Editable SVG
sources live under `src/`; the runtime SVGs, raster sets, and social PNGs are
regenerated from them by `scripts/dev/rebuild-assets-resvg.py` (see
[`README.md`](README.md)).

| Asset | Variant role | Disposition |
|-------|--------------|-------------|
| `src/logo.svg` → `logo.svg`, `logo.png`, `logo-16…1024.png` | Primary mark, light (includes the `logo-192.png` / `logo-512.png` `purpose: any` manifest icons) | Refreshed to the apothem-hexagon mark |
| `src/logo-dark.svg` → `logo-dark.svg`, `logo-dark-16…1024.png` | Primary mark, dark | Refreshed |
| `src/logo-animated.svg` → `logo-animated.svg` | Animated mark (apothem draws in; reduced-motion-safe) | Refreshed |
| `src/icon-maskable.svg` → `logo-maskable-192.png`, `logo-maskable-512.png` | Maskable PWA icons (`purpose: maskable`), full-bleed dark tile | Refreshed |
| `logo-wordmark.svg` | Horizontal lockup: mark + wordmark + tagline, light | Refreshed |
| `logo-wordmark-dark.svg` | Horizontal lockup, dark | Refreshed |
| `favicon.svg` → `favicon.ico`, `favicon-16/32.png` | Compact tab monogram (filled hexagon) | Refreshed for 16 px legibility |
| `src/apple-touch.svg` → `apple-touch-icon-120…180.png` | Apple touch-icon set, dark tile | Regenerated from the `src/apple-touch.svg` master |
| `github-avatar.svg` | 420 px org/repo avatar on a dark tile | Refreshed |
| `src/og-banner.svg` → `og-banner-1200x630.png` | Open Graph share card, dark | Refreshed |
| `src/twitter-card.svg` → `twitter-card.png` | Twitter/X share card, dark | Refreshed |
| `social-preview.svg` | GitHub social-image / README preview, light | Refreshed |

## Color

Two ramps carry the brand — a cool **slate** neutral and an **emerald** accent —
plus three semantic hues. Every step is named `--apothem-color-{ramp}-{step}`.
The brand anchors (`slate-900 #0f172a`, `slate-50 #f8fafc`, `emerald-500
#10b981`, `emerald-400 #34d399`) are preserved from the prior identity; the
ramps fill in around them.

### Slate (neutral)

| Step | Hex | Step | Hex |
|------|-----|------|-----|
| 50  | `#f8fafc` | 600 | `#475066` |
| 100 | `#eef2f7` | 700 | `#333c50` |
| 200 | `#dce3ec` | 800 | `#1c2434` |
| 300 | `#c2ccda` | 900 | `#0f172a` |
| 400 | `#94a2b8` | 950 | `#080c15` |
| 500 | `#65748c` |     |        |

### Emerald (accent)

| Step | Hex | Step | Hex |
|------|-----|------|-----|
| 50  | `#ecfdf5` | 600 | `#059669` |
| 100 | `#d1fae5` | 700 | `#047857` |
| 200 | `#a7f3d0` | 800 | `#065f46` |
| 300 | `#6ee7b7` | 900 | `#064e3b` |
| 400 | `#34d399` | 950 | `#022c22` |
| 500 | `#10b981` |     |        |

### Semantic hues

`success` reuses emerald. `warning` is amber (`#fbbf24` / `#f59e0b` /
`#b45309`), `danger` is red (`#f87171` / `#ef4444` / `#b91c1c`), `info` is sky
(`#7dd3fc` / `#38bdf8` / `#0369a1`) — each with a dark-surface step, a mid step,
and a light-surface text step.

### Semantic aliases

Consumers reference these, not the ramp steps. The accent carries **two roles**:
a graphic fill (icons, the mark, borders — needs ≥ 3:1) and a text/link color
(needs ≥ 4.5:1). Emerald is light enough that the same step cannot serve both on
a light surface, so the aliases split by role and mode.

| Alias | Dark default | Light remap |
|-------|--------------|-------------|
| `--apothem-surface` | `slate-900` | `slate-50` |
| `--apothem-surface-raised` | `slate-800` | `white` (`#ffffff`) |
| `--apothem-surface-sunken` | `slate-950` | `slate-100` |
| `--apothem-text` | `slate-50` | `slate-900` |
| `--apothem-text-muted` | `slate-300` | `slate-600` |
| `--apothem-text-subtle` | `slate-400` | `slate-500` |
| `--apothem-border` | `slate-700` | `slate-200` |
| `--apothem-border-strong` | `slate-600` | `slate-300` |
| `--apothem-accent-graphic` | `emerald-400` | `emerald-600` |
| `--apothem-accent-text` | `emerald-400` | `emerald-700` |
| `--apothem-accent-strong` | `emerald-500` | `emerald-700` |

### Contrast (WCAG 2.1 AA)

AA floors: 4.5:1 normal text, 3:1 large text and non-text UI. Every pair the
system pairs by design clears its floor:

| Foreground | Background | Ratio | Role | AA |
|------------|-----------|------:|------|----|
| `slate-50` | `slate-900` | 16.9:1 | body text, dark | ✓ text |
| `slate-300` | `slate-900` | 11.0:1 | muted text, dark | ✓ text |
| `slate-400` | `slate-900` | 6.9:1 | subtle text, dark | ✓ text |
| `emerald-400` | `slate-900` | 9.3:1 | accent/link, dark | ✓ text |
| `slate-900` | `slate-50` | 16.9:1 | body text, light | ✓ text |
| `slate-600` | `slate-50` | 7.7:1 | muted text, light | ✓ text |
| `slate-500` | `slate-50` | 4.5:1 | subtle text, light | ✓ text |
| `emerald-700` | `slate-50` | 5.2:1 | accent/link, light | ✓ text |
| `emerald-600` | `slate-50` | 3.6:1 | accent graphic, light | ✓ UI |

`emerald-500` on white is ~2.4:1 — used only as a graphic on **dark** surfaces,
never as text or as a graphic on light. That is why the light accent graphic is
`emerald-600` and the light accent text is `emerald-700`.

## Typography

System UI stack — no embedded font payload, so SVG rasters rebuild
deterministically and pages render without a web-font round-trip.

- **Sans:** `Inter, Segoe UI, system-ui, -apple-system, Helvetica Neue, Arial, sans-serif`
- **Mono:** `JetBrains Mono, SFMono-Regular, Consolas, Liberation Mono, monospace`

Modular scale, ratio **1.250** (major third), 1 rem base:

| Token | rem | px | Role |
|-------|-----|----|------|
| `font-size-0` | 0.75 | 12 | fine print, chips |
| `font-size-1` | 0.875 | 14 | captions, secondary |
| `font-size-2` | 1 | 16 | body |
| `font-size-3` | 1.25 | 20 | lead, h4 |
| `font-size-4` | 1.5625 | 25 | h3 |
| `font-size-5` | 1.9531 | 31 | h2 |
| `font-size-6` | 2.4414 | 39 | h1 |
| `font-size-7` | 3.0518 | 49 | display |

Weights `450 / 550 / 650 / 760` (regular → bold). Line-heights `1.15 / 1.35 /
1.5 / 1.7` (tight → relaxed). Tracking `-0.01em / 0 / 0.02em`.

## Spacing, radius, elevation

Spacing base **0.25 rem (4 px)**; the index equals the multiple, so arithmetic
is obvious: `space-4` is `4 × 4 px = 16 px`.

`1:4 · 2:8 · 3:12 · 4:16 · 6:24 · 8:32 · 12:48 · 16:64` (px).

Radius: `0 · 4 px · 8 px · 12 px · 20 px · full`. Elevation: five steps,
dark-first — a 1 px top-inset highlight over a low-alpha drop, rather than large
soft blurs; light mode swaps to softer cool shadows.

## Consuming the tokens

Import the CSS export and reference semantic aliases:

```css
@import url("./design-tokens.css");

.button {
  background: var(--apothem-accent-graphic);
  color: var(--apothem-surface);
  padding: var(--apothem-space-2) var(--apothem-space-4);
  border-radius: var(--apothem-radius-2);
  font: var(--apothem-font-weight-semibold) var(--apothem-font-size-2) / var(--apothem-leading-snug) var(--apothem-font-sans);
}
```

Build tooling that prefers JSON consumes [`design-tokens.json`](design-tokens.json)
(W3C format, with `{color.slate.900}`-style references resolved by the
toolchain).
