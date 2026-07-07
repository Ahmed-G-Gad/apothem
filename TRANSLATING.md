<!-- SPDX-License-Identifier: MIT -->

# Translating Apothem

Apothem's documentation ships in twelve languages. English is the source of
truth; every other locale is a translation that tracks it. This guide explains
how to claim a locale, translate, and get a translation reviewed and published.

## Supported locales

| Locale | Native name | Path | Writing system | Direction |
| --- | --- | --- | --- | --- |
| English | English | `/` | Latin | LTR |
| Chinese (Simplified) | 简体中文 | `/zh-cn/` | Han (Simplified) | LTR |
| Spanish | Español | `/es/` | Latin | LTR |
| Portuguese (Brazil) | Português (Brasil) | `/pt-br/` | Latin | LTR |
| French | Français | `/fr/` | Latin | LTR |
| German | Deutsch | `/de/` | Latin | LTR |
| Japanese | 日本語 | `/ja/` | Kanji/Kana | LTR |
| Korean | 한국어 | `/ko/` | Hangul | LTR |
| Russian | Русский | `/ru/` | Cyrillic | LTR |
| Indonesian | Bahasa Indonesia | `/id/` | Latin | LTR |
| Arabic | العربية | `/ar/` | Arabic | RTL |
| Hindi | हिन्दी | `/hi/` | Devanagari | LTR |

## How translations are organized

Each locale's pages live under `site/content/docs/<locale>/`, mirroring the
English tree under `site/content/docs/`. A page that has no translation in a
locale falls back to the English version automatically, so partial translations
ship safely — a translated page replaces its English fallback the moment it
lands.

## Claiming a locale

1. Open a GitHub Discussion (or comment on the translation tracking issue)
   stating the locale you want to own and your regional variant (see below).
2. One contributor owns a locale at a time; cohorts may split a locale's pages
   by section. Coordinate in the discussion thread.
3. Read this guide and your locale's glossary before starting.

## Regional variant decisions

State the variant you translate to, and keep it consistent across the locale:

- **Chinese:** Simplified (the shipped locale is `zh-cn`). Do not mix in
  Traditional forms.
- **Spanish:** choose Latin American or peninsular and hold it; prefer neutral
  Latin American vocabulary where a term differs.
- **Portuguese:** the shipped locale is `pt-br` (Brazilian); do not mix in
  European Portuguese forms.
- **Formality:** match the English register — direct, technical, second person
  where English uses "you". Avoid honorifics that English does not imply.

## Glossary discipline

Each locale has a glossary file for domain terms and their agreed rendering.
Before translating, fill in your locale's glossary and follow it:

- **`apothem`** — the brand name. **Never translate or transliterate it.** It
  stays `apothem` in every locale, including RTL scripts.
- **`harness`** — render with your locale's agreed term for an AI assistant or harness;
  record the choice in the glossary so it is uniform across pages.
- **`hook`**, **`adapter`**, **`materialize`**, **`profile`**, **`conformity
  gate`** — record one rendering each and reuse it everywhere.
- Code, CLI commands, flags, file paths, and config keys are **never
  translated** — only the prose around them.

## Review and publication gate

- Translations land via GitHub pull request. Tag your locale's reviewer cohort.
- A locale publishes when **at least 80%** of its pages have a completed human
  review on top of any machine-seeded draft. Below that threshold the locale
  stays in draft and continues to serve the English fallback.
- Machine translation (DeepL for structure, a polish pass for tone and
  technical vocabulary) may seed a draft, but **no page publishes without human
  review** — machine output is a starting point, never the shipped text.

## Right-to-left locales

Arabic ships right-to-left. The site sets `dir="rtl"` for the `ar` locale
automatically. When translating, keep code blocks, CLI commands, and inline
paths left-to-right; only the surrounding prose flows RTL.

## Questions

Open a [GitHub Discussion](https://github.com/ahmed-g-gad/apothem/discussions) or
file an [issue](https://github.com/ahmed-g-gad/apothem/issues) with the `i18n` label.
