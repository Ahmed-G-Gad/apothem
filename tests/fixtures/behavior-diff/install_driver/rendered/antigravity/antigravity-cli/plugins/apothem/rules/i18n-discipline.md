---
trigger: glob
description: "Locale-cohort selection, framework i18n integration, machine-seed translation with optional human review, per-locale glossary, RTL discipline, and hreflang / lang attribute discipline for every host-project translated surface."
globs: "**/site/**, **/docs/**, **/_inputs/locale-glossary-*.md, **/next.config.*"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Internationalization (i18n) Discipline

## Purpose

Govern every translated surface — site pages, docs, marketing copy, error strings — across the host project. Translation is a production-ready criterion: a surface ships in every cohort locale or surfaces the gap as an inquiry; it never silently English-only-drifts.

## Obligations

### 1. Locale-Cohort Discipline

The **Modern Dev Cohort** is twelve locales: **EN, ZH-CN, ES, PT-BR, FR, DE, JA, KO, RU, ID, AR, HI** (EN source, eleven translation targets).

Cohort discovery walks the host's translated corpus (`site/content/docs/<locale>/`, the host i18n config's locale registrations) per `rules/host-discovery.md`. A host-ratified cohort wins. Where the host is silent, the Modern Dev Cohort is the default, surfaced via `rules/authority-inquiry.md` with options annotated per `rules/option-annotation.md`. Cohort amendments route through the structured-inquiry channel — never invented, never silently expanded.

(Companion Sub-Rule Anchor) See `rules/i18n-discipline-locale-cohorts.md` §1 for per-locale selection rationale and amendment protocol.

### 2. Framework i18n Integration

Translated sites register every cohort locale with the host's i18n framework — the framework's locale-registration surface (e.g., a Next.js i18n module, a Docusaurus `i18n` config, or the host's equivalent) — with the language switcher enabled and per-page frontmatter declaring `lang` and (for RTL) `dir: rtl`. Routing is `/<locale>/<slug>`; the source locale sits at `/` as the framework's default locale.

### 3. Machine-Seed + Optional Human Review

Initial translations are **machine-seeded** (DeepL preferred; GPT-4 fallback) and the seed is the shipped form. Human review is **encouraged** but **not** a gating banner; seed state is internal metadata (the `machineTranslated` flag), never a visible badge. The shipped facade is **current-version-only** per `rules/freshness-facade.md`: every locale presents as a complete translation with no `[Machine-seeded — pending review]` / `pending` / `partial` banner, and an unauthored page falls back silently to EN. A coverage gap surfaces as a finding per `rules/production-ready-prs.md`, never a banner.

(Companion Sub-Rule Anchor) See `rules/i18n-discipline-locale-cohorts.md` §4 for the banner-free facade policy and the fallback-vs-banner distinction.

### 4. Per-Locale Glossary Discipline

Each cohort locale maintains a glossary at `_inputs/locale-glossary-<locale>.md` mapping source terms to the locale's idiom. The glossary is authoritative; reviewers honor it; machine-seed prompts cite it. Cross-glossary drift — the same source term mapped to two target terms across pages — is a finding.

### 5. RTL Discipline

Arabic (AR) is the cohort's sole RTL locale. AR pages carry `dir="rtl"` at `<html>`; theme CSS uses logical properties (`margin-inline-start` over `margin-left`); bidirectional content uses `<bdi>` / Unicode `LRI` / `PDI` markers.

(Companion Sub-Rule Anchor) See `rules/i18n-discipline-locale-cohorts.md` §2 for the RTL CSS-token catalog.

### 6. hreflang / `lang` Attribute Discipline

Every translated page emits an `hreflang` link-tag set covering every cohort locale plus `x-default` (pointing to the EN root). Each page's `<html lang="...">` matches its locale code. Per-locale canonical URLs are absolute, permalinked, cohort-consistent — never pointing across locales.

(Companion Sub-Rule Anchor) See `rules/i18n-discipline-locale-cohorts.md` §3 for the hreflang shape and canonical-URL discipline.

## Disclosure surface

Translation outcomes recorded in the ledger per `rules/disclosure-ledger.md`:

- `[I18n — locale: <code>; pages-translated: <N>/<total>; status: <complete | coverage-gap>]` per release.
- `[I18n — glossary-drift: <term>; locale: <code>; resolution: <chosen-form>]` per glossary reconciliation.
- `[I18n — cohort-amendment: <added | removed>: <locale>; inquiry-id: <id>; rationale: <driver>]` per cohort change.

## Failure tells

A site shipping EN-only while the host's i18n config declares twelve locales. A shipped translated page carrying a `[Machine-seeded — pending review]` / `pending` / `partial` deferral banner. Hardcoded `margin-left` in theme CSS used by AR pages. A page with `<html lang="en">` served at `/zh-cn/`. Missing `hreflang` tags. Glossary terms invented per-page rather than centralized.

## Bindings (§0.j five-direction)

- **Drives →** Every translated page across the host's site / docs / marketing surfaces. Every host i18n-config locale registration. The per-locale glossary. The current-version-only translated facade (no deferral banner).
- **Satisfies →** The Modern Dev Cohort locale baseline; i18n-discipline always-on coverage; the host's production-ready criterion for translated surfaces; the current-version-only facade for translated surfaces.
- **Established by ↑** Operator-ratified locale coverage and the banner-free clean-facade decision; the host's i18n configuration surface; `rules/production-ready-prs.md` §5 visibility-surface gap-surfacing.
- **Gated by ←** The trivial-vs-non-trivial threshold (EN-only projects skip the cohort discipline until i18n is introduced). The host's ratified i18n framework.
- **Cross-bound with ↔** `rules/i18n-discipline-locale-cohorts.md` (companion sub-rule). `rules/host-discovery.md` (M1 — cohort discovered, not invented). `rules/authority-inquiry.md` (M5 — cohort amendments via the structured-inquiry channel). `rules/disclosure-ledger.md` (M2 — per-locale outcomes recorded). `rules/production-ready-prs.md` (M15 — full authored-page-set coverage per cohort locale). `rules/freshness-facade.md` (the shipped translated facade is current-version-only — no machine-seeded / pending / partial deferral banner). `rules/option-annotation.md` (M7 — amendment inquiries carry Recommended + driver).
