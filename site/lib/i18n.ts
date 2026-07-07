// SPDX-License-Identifier: MIT

/**
 * Locale-cohort declaration for the Apothem documentation site.
 *
 * This module is the single source of truth for the site's internationalization
 * posture. It declares the Modern Dev Cohort (twelve locales), the source
 * locale, the per-locale BCP-47 codes, label, and text direction, and which
 * locales carry authored content.
 *
 * The site is built on Next.js App Router + Fumadocs. Every cohort locale is
 * machine-seeded from the English page set under `content/docs/<locale>/`, so
 * all twelve are wired into routing via ROUTED_LOCALES and each is navigable
 * from its own content. The seeded set tracks the English tree closely; the
 * loader's `fallbackLanguage: 'en'` covers any page a locale has not yet
 * authored, so a locale is navigable across the whole site rather than only
 * its seeded pages. The hreflang / `lang` mechanism (see `lib/hreflang.ts` and
 * `app/layout.tsx`) emits alternate-language links resolved per-file from the
 * filesystem (see `lib/translated-pages.ts`).
 *
 * Per-page seed state is internal review-tracking metadata, carried by the
 * `machineTranslated` frontmatter flag (see `source.config.ts`), never a
 * shipped per-page status badge. The seeded pages are machine-translated;
 * per-locale human review attestation is in progress. The shipped translated
 * facade is current-version-only per the i18n-discipline and
 * freshness-naturalism rules, so this registry carries no per-locale lifecycle
 * label.
 *
 * The cohort and per-locale rationale are governed by the i18n-discipline rule
 * set; amendments to the cohort route through structured inquiry, never a
 * silent edit here.
 */

import type { I18nConfig } from 'fumadocs-core/i18n';

/** Text direction for a locale's pages. */
export type LocaleDirection = 'ltr' | 'rtl';

export interface CohortLocale {
  /** BCP-47 language tag used in `hreflang` and `<html lang>` (e.g. `zh-CN`). */
  readonly code: string;
  /** URL path segment, kebab-cased per the routing convention (e.g. `zh-cn`). */
  readonly path: string;
  /** Native-language label for the locale switcher. */
  readonly label: string;
  /** Text direction; `rtl` for Arabic, `ltr` otherwise. */
  readonly dir: LocaleDirection;
}

/** The site's canonical absolute base URL, used to build absolute hreflang URLs. */
export const SITE_URL = 'https://apothem.ahmedgad.com';

/** The source locale. English is served at the site root (no path prefix). */
export const DEFAULT_LOCALE = 'en';

/**
 * The Modern Dev Cohort — twelve locales. EN is the source; the eleven targets
 * are each machine-seeded from the English page set under
 * `content/docs/<locale>/`, with `fallbackLanguage: 'en'` covering any
 * not-yet-authored page. Per-page seed state is tracked by the
 * `machineTranslated` frontmatter flag (see `source.config.ts`), not here.
 * Per-locale selection rationale lives in the i18n-discipline locale-cohort
 * rule.
 */
export const COHORT_LOCALES: readonly CohortLocale[] = [
  { code: 'en', path: '', label: 'English', dir: 'ltr' },
  { code: 'zh-CN', path: 'zh-cn', label: '简体中文', dir: 'ltr' },
  { code: 'es', path: 'es', label: 'Español', dir: 'ltr' },
  { code: 'pt-BR', path: 'pt-br', label: 'Português (Brasil)', dir: 'ltr' },
  { code: 'fr', path: 'fr', label: 'Français', dir: 'ltr' },
  { code: 'de', path: 'de', label: 'Deutsch', dir: 'ltr' },
  { code: 'ja', path: 'ja', label: '日本語', dir: 'ltr' },
  { code: 'ko', path: 'ko', label: '한국어', dir: 'ltr' },
  { code: 'ru', path: 'ru', label: 'Русский', dir: 'ltr' },
  { code: 'id', path: 'id', label: 'Bahasa Indonesia', dir: 'ltr' },
  // Arabic is the cohort's sole RTL locale; `dir: 'rtl'` drives the per-locale
  // `<html dir>` RTL rendering (see app/layout.tsx head script + export-to-dist.mjs).
  { code: 'ar', path: 'ar', label: 'العربية', dir: 'rtl' },
  { code: 'hi', path: 'hi', label: 'हिन्दी', dir: 'ltr' },
] as const;

/**
 * The locales wired into the live Fumadocs routing. All twelve cohort locales
 * are routed: each is machine-seeded from the English page set under
 * `content/docs/<code>/`, with `fallbackLanguage: 'en'` covering any
 * not-yet-authored page.
 * `en` is the source locale, served at the site root. Each routed entry is the
 * locale's URL-path / content-directory segment (`zh-cn`, `pt-br`), which
 * equals the Fumadocs language key for that locale's `content/docs/<segment>/`
 * tree.
 */
export const ROUTED_LOCALES: readonly string[] = ['en', 'es', 'zh-cn', 'pt-br', 'fr', 'de', 'ja', 'ko', 'ru', 'id', 'hi', 'ar'] as const;

/** Non-default routed locales — the locales that carry a URL path prefix. */
export const ROUTED_NON_DEFAULT_LOCALES: readonly string[] = ROUTED_LOCALES.filter(
  (code) => code !== DEFAULT_LOCALE,
);

/**
 * The live Fumadocs i18n configuration consumed by the content `loader()`.
 *
 * - `languages` is the full routed cohort — every cohort locale is routed and
 *   machine-seeded from the English page set, so the routed page count is the
 *   English page set fanned across all twelve locales, with `fallbackLanguage`
 *   covering any not-yet-authored page.
 * - `defaultLanguage: 'en'` keeps English as the source locale.
 * - `hideLocale: 'default-locale'` strips the `en` prefix from generated URLs
 *   so English pages keep their existing root URLs (`/docs/...`), unchanged.
 * - `parser: 'dir'` selects the directory-per-locale file layout
 *   (`content/docs/es/...`), keeping English content at `content/docs/...`.
 * - `fallbackLanguage: 'en'` lets a locale with partial translation fall back
 *   to the English page tree for not-yet-translated pages, so a seeded locale
 *   is navigable across the whole site rather than only its seeded pages.
 */
export const i18n: I18nConfig = {
  languages: [...ROUTED_LOCALES],
  defaultLanguage: DEFAULT_LOCALE,
  hideLocale: 'default-locale',
  parser: 'dir',
  fallbackLanguage: DEFAULT_LOCALE,
};

/**
 * The locale-switcher item list Fumadocs' `RootProvider` consumes. Only routed
 * locales are offered, since a switcher entry for an unrouted locale would
 * point at a non-existent page. The `locale` value is the URL-path form (the
 * Fumadocs language key, matching `i18n.languages` = ROUTED_LOCALES), NOT the
 * BCP-47 code — otherwise code≠path locales (zh-CN→zh-cn, pt-BR→pt-br) would be
 * filtered out and, if listed, would route to a non-existent upper-cased path.
 */
const routeKey = (locale: CohortLocale): string =>
  locale.code === DEFAULT_LOCALE ? locale.code : locale.path;

export const LOCALE_SWITCHER_ITEMS = COHORT_LOCALES.filter((locale) =>
  ROUTED_LOCALES.includes(routeKey(locale)),
).map((locale) => ({ name: locale.label, locale: routeKey(locale) }));
