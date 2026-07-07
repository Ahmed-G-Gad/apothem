---
name: "i18n-discipline-locale-cohorts"
description: "Path-filtered companion sub-rule to i18n-discipline.md — carries the Modern Dev Cohort selection rationale + per-locale reach data, the RTL CSS-token catalog, and the hreflang link-tag shape + canonical-URL discipline. Demand-loaded on site / docs / locale-glossary / i18n-config touches."
pathFilter: "**/site/**, **/docs/**, **/_inputs/locale-glossary-*.md, **/next.config.*"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: i18n Discipline — Locale Cohorts (Companion Sub-Rule)

## Purpose

Carry the operational depth of the i18n discipline the parent rule `rules/i18n-discipline.md` anchors. Path-filtered: loads when the assistant edits site content, documentation pages, per-locale glossary files, or the host i18n config that registers locales. The parent retains the always-on directives (cohort, framework i18n, review gate, glossary, RTL, hreflang summaries); this companion carries the cohort rationale (§1), the RTL CSS-token catalog (§2), and the hreflang link-tag shape (§3).

## Obligations

### 1. Modern Dev Cohort — Selection Rationale and Amendment Protocol

The Modern Dev Cohort is twelve locales — **EN, ZH-CN, ES, PT-BR, FR, DE, JA, KO, RU, ID, AR, HI** — each chosen against a concrete driver:

| Locale | Code | Driver class (per `rules/interactive-questions-canonical-shapes.md` §3.2.1) |
|---|---|---|
| English | EN | Class 6 observed-state — source locale; ~70% of Stack Overflow questions, ~63% of npm package descriptions |
| Mandarin (Simplified) | ZH-CN | Class 6 — largest developer population (GitHub state-of-the-octoverse); largest dev-tooling translation gap |
| Spanish | ES | Class 6 — second-largest dev language by Stack Overflow surveys; pan-American + Iberian reach |
| Portuguese (Brazilian) | PT-BR | Class 6 — Brazil is a top-5 developer market; PT-PT readers find PT-BR comprehensible (asymmetric reach) |
| French | FR | Class 6 — francophone Africa + EU; high developer concentration in Paris / Montréal hubs |
| German | DE | Class 6 — DACH developer density; strong open-source contribution per-capita |
| Japanese | JA | Class 6 — high-context language; high localization expectation; mature dev community |
| Korean | KO | Class 6 — Seoul tech hub; high translation-quality expectation |
| Russian | RU | Class 6 — CIS developer reach; significant open-source contribution |
| Indonesian | ID | Class 6 — fastest-growing dev population in Southeast Asia |
| Arabic | AR | Class 6 — MENA reach + RTL representation; the cohort's sole RTL locale |
| Hindi | HI | Class 6 — Indian subcontinent reach; Devanagari script representation |

**Amendment protocol.** Adding or removing a cohort locale MUST route through the structured-inquiry channel per `rules/authority-inquiry.md`, citing a concrete driver (locale-specific reach data, host-project audience evidence, or a ratified locked decision). Silent cohort expansion is non-conformant — long-lived ratifications never auto-expand. Outcomes land in the disclosure ledger as `[I18n — cohort-amendment: …]`.

**Exclusions and why.** Italian, Polish, Turkish, Vietnamese, Thai, Dutch, Swedish are common dev locales but excluded from the default against the twelve-locale ship-cost ceiling. A host with measurable audience evidence for an excluded locale adds it via the amendment protocol; the cohort never silently grows.

### 2. RTL CSS-Token Catalog

Arabic pages render right-to-left. Shared theme CSS MUST use **logical properties** exclusively; physical properties leak when one stylesheet serves both LTR and RTL.

| Physical (forbidden in shared stylesheets) | Logical (required) |
|---|---|
| `margin-left` | `margin-inline-start` |
| `margin-right` | `margin-inline-end` |
| `padding-left` | `padding-inline-start` |
| `padding-right` | `padding-inline-end` |
| `border-left` | `border-inline-start` |
| `border-right` | `border-inline-end` |
| `left: <n>` (positioning) | `inset-inline-start: <n>` |
| `right: <n>` | `inset-inline-end: <n>` |
| `text-align: left` | `text-align: start` |
| `text-align: right` | `text-align: end` |
| `float: left` / `float: right` | `float: inline-start` / `float: inline-end` |

**Bidirectional content.** A mixed-direction string (e.g., an English code snippet inside an Arabic paragraph) carries a `<bdi>` wrapper around the foreign-direction substring. Unicode bidi controls (`LRI` U+2066, `RLI` U+2067, `PDI` U+2069) are used where HTML wrapping is unavailable (Markdown alt text, JSON-embedded UI strings).

**Icon mirroring.** Directional icons (arrows, back / forward, breadcrumb chevrons) are mirrored via `transform: scaleX(-1)` scoped to `[dir="rtl"]` selectors; non-directional icons (gears, search lenses, profile silhouettes) are NOT mirrored.

**Failure tells.** A `margin-left: 1rem` in a stylesheet served to AR pages (RTL leak). A `<` chevron pointing the wrong way on an AR breadcrumb (un-mirrored directional icon). An English code snippet inside an Arabic paragraph rendering as visually-reversed letters (missing `<bdi>` wrapper or LRI/PDI markers).

### 3. hreflang Link-Tag Shape and Canonical-URL Discipline

Every translated page emits an `hreflang` link-tag set in its `<head>` covering every cohort locale plus `x-default`. The canonical shape for a Modern-Dev-Cohort page at slug `/<slug>`:

```html
<link rel="alternate" hreflang="en" href="https://<host>/<slug>/" />
<link rel="alternate" hreflang="zh-CN" href="https://<host>/zh-cn/<slug>/" />
<link rel="alternate" hreflang="es" href="https://<host>/es/<slug>/" />
<link rel="alternate" hreflang="pt-BR" href="https://<host>/pt-br/<slug>/" />
<link rel="alternate" hreflang="fr" href="https://<host>/fr/<slug>/" />
<link rel="alternate" hreflang="de" href="https://<host>/de/<slug>/" />
<link rel="alternate" hreflang="ja" href="https://<host>/ja/<slug>/" />
<link rel="alternate" hreflang="ko" href="https://<host>/ko/<slug>/" />
<link rel="alternate" hreflang="ru" href="https://<host>/ru/<slug>/" />
<link rel="alternate" hreflang="id" href="https://<host>/id/<slug>/" />
<link rel="alternate" hreflang="ar" href="https://<host>/ar/<slug>/" dir="rtl" />
<link rel="alternate" hreflang="hi" href="https://<host>/hi/<slug>/" />
<link rel="alternate" hreflang="x-default" href="https://<host>/<slug>/" />
```

**Per-page invariants.**

- `<html lang="...">` matches the page's locale code (`lang="en"`, `lang="zh-CN"`, `lang="ar"`, …).
- AR pages additionally carry `<html dir="rtl">`.
- The `<link rel="canonical">` is the page's own absolute URL — never points across locales. An AR page canonicalizes to the AR URL, not the EN URL.
- `x-default` points to the source-locale (EN) URL — the fallback for visitors whose `Accept-Language` matches no cohort entry.
- Locale codes follow BCP-47 (`zh-CN`, not `zh_cn`; `pt-BR` in the `hreflang` attribute, though the URL path uses kebab-case `/pt-br/`).

**Symmetry invariant.** The hreflang set is **identical** across every locale's version of the page — the EN, ZH-CN, and AR pages each list every locale. Asymmetric hreflang (a locale omitting some peers) breaks Google's cross-locale clustering and is a finding.

**Missing-translation case.** When a page is not yet translated into a cohort locale, that locale's `hreflang` tag is **omitted**, not pointed at the EN fallback. Omission communicates accurately that no translation exists; pointing the omitted locale at EN would lie to search engines and degrade cross-locale ranking.

**Failure tells.** An AR page whose `<link rel="canonical">` points to the EN URL (cross-locale canonical leak). Asymmetric hreflang sets (the EN page lists twelve peers but the ZH-CN page lists six). Locale codes in `_` form rather than BCP-47 `-` form (`zh_CN`). Missing `dir="rtl"` on the AR `<html>`. Missing `x-default`.

### 4. Banner-Free Facade Policy

The shipped translated surface is **current-version-only** per `rules/freshness-facade.md`: every cohort locale presents as a complete, current translation, and no page carries a deferral banner. The policy:

- **The seed is the shipped form.** Machine-seeded pages ship as-is. Human review, where reviewers exist, raises quality in place — it never gates a page behind a `[Machine-seeded — pending review]` banner, a `pending` / `partial` status badge, or any deferral narrative.
- **Internal metadata, not a shipped badge.** Per-page seed state is carried by the `machineTranslated` frontmatter flag (internal review-tracking metadata read by tooling, e.g. `site/source.config.ts`), never surfaced to the visitor as a status label. The locale registry (`site/lib/i18n.ts`) carries no per-locale lifecycle status field.
- **Fallback is the mechanism, not a banner.** A cohort locale that has not yet authored a page falls back **silently** to the EN source through the loader's `fallbackLanguage`. The visitor reads the EN page at the locale's URL; no on-page banner announces the fallback. The hreflang set still **omits** the unauthored locale per §3's missing-translation case, so search engines see the gap honestly while the visitor sees a clean page.
- **Coverage gaps surface to maintainers, not visitors.** Production-readiness (per `rules/production-ready-prs.md`) requires the full authored page set per cohort locale. A coverage gap is a finding recorded via `rules/disclosure-ledger.md` (the `[I18n — locale: <code>; pages-translated: <N>/<total>; status: <complete | coverage-gap>]` marker), surfaced to the maintainer — never rendered as a shipped banner.

**Failure tells.** A shipped translated page carrying a visible `[Machine-seeded — pending review]` / `pending` / `partial` deferral banner. A per-locale status badge rendered to the visitor. A `contentStatus` / lifecycle-status field re-introduced into the locale registry. A fallback page announcing "showing English instead" on-page rather than falling back silently.

## Enforcement

Path-filtered (the four glob patterns in this rule's `pathFilter` field — `**/site/**`, `**/docs/**`, `**/_inputs/locale-glossary-*.md`, `**/next.config.*`), demand-loaded companion to `rules/i18n-discipline.md`. The parent carries the always-on directives (cohort, framework i18n, machine-seed + optional review, glossary, RTL, hreflang summaries); this companion carries the cohort-selection rationale + amendment protocol (§1), the RTL CSS-token catalog (§2), the hreflang link-tag shape + canonical-URL discipline (§3), and the banner-free facade policy (§4).

## Bindings (§0.j five-direction)

- **Drives →** Every locale-cohort amendment routing through the canonical structured-inquiry channel. Every translated page's hreflang link-tag emission. Every theme CSS file's logical-property discipline on the RTL-serving rulesets. Every per-locale glossary file's path conforming to `_inputs/locale-glossary-<locale>.md`.
- **Satisfies →** `rules/i18n-discipline.md` §1 + §3 + §5 + §6 anchors (the parent rule's pointers to this companion's full cohort rationale, banner-free facade policy, RTL token catalog, and hreflang shape). The Modern Dev Cohort locale baseline with per-locale rationale; the current-version-only translated facade.
- **Established by ↑** `rules/i18n-discipline.md` (parent-rule anchor). Operator-ratified locale coverage. The BCP-47 language-tag specification (the upstream standard for locale codes). The CSS Logical Properties Level 1 specification (the upstream standard for logical properties).
- **Gated by ←** The path-filter (the four glob patterns) — this rule demand-loads only on site / docs / locale-glossary / i18n-config touches. `rules/i18n-discipline.md` always-on baseline (parent rule must be live for the anchors to surface).
- **Cross-bound with ↔** `rules/i18n-discipline.md` (parent rule; §1 / §3 / §5 / §6 anchors bind this companion). `rules/host-discovery.md` (M1 — cohort discovery walks the host's existing translated corpus). `rules/authority-inquiry.md` (M5 — cohort amendments route through the structured-inquiry channel). `rules/option-annotation.md` (M7 — cohort options carry concrete-driver rationale per §3.2.1). `rules/disclosure-ledger.md` (M2 — cohort amendments + per-locale completion outcomes recorded). `rules/production-ready-prs.md` (M15 — full authored-page-set coverage per cohort locale gates production-ready). `rules/freshness-facade.md` (the §4 banner-free facade is current-version-only — no machine-seeded / pending / partial deferral banner).
