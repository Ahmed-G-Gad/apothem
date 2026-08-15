<!-- SPDX-License-Identifier: MIT -->

<!-- REUSE-IgnoreStart -->
# Site internal library

Cross-cutting source-of-truth modules for the documentation site. Everything
here is imported by the `app/` routes, the `components/`, and the `scripts/`;
none of it is a page. When a value here is the authority for a concern, callers
derive from it rather than re-declaring it.

## Modules

- **`i18n.ts`** — the authoritative i18n cohort and locale table. `COHORT_LOCALES`
  carries every locale's code, URL-path segment, and text direction;
  `ROUTED_LOCALES` is the set wired into live Fumadocs routing (currently the
  full twelve-locale cohort), and `ROUTED_NON_DEFAULT_LOCALES` is that set minus
  the default (`en`). `DEFAULT_LOCALE` is the source locale served at the site
  root with no path prefix. **This file is the single source of truth for the
  routed-locale set** — build scripts (`build-llms-txt.mjs`,
  `check-search-index-sizes.mjs`, `export-to-dist.mjs`) re-parse it and fail on
  drift rather than hard-coding a divergent copy.
- **`hreflang.ts`** — builds the per-page `alternates` (hreflang) set from a
  locale-agnostic path, emitting the `en` self-link, `x-default`, and one
  alternate per routed locale that carries a version of the page.
- **`search-index-core.ts`** — the per-locale static search-index transform. The
  site is `output: 'export'`, so the index is emitted at build time and queried
  in the browser; this module holds the pure transform, with its `node --test`
  unit test alongside it (`search-index-core.test.mjs`, run by `npm test`).
- **`search-index.ts`** — builds one Fumadocs `SearchAPI` **per locale** and owns
  the Orama language / tokenizer choice for each. Fumadocs' `createFromSource`
  would emit a single combined index that, with the English fallback tree indexed
  under all twelve locales, exceeds the 100 MB per-file limit of the static host —
  so the CDN refuses it and client search fails outright. One index per locale
  keeps every file small. Mandarin and Japanese carry a dedicated `@orama/tokenizers`
  tokenizer because neither script has whitespace word boundaries.
- **`translated-pages.ts`** — enumerates the slugs a locale has *authored*, read
  from `content/docs/<locale>/` rather than from the loader. The i18n loader merges
  each locale's storage with the English fallback, so asking it would report the
  whole fallback tree as translated; reading the filesystem keeps static params
  tied to the real translated surface.
- **`source.ts`** / **`utils.ts`** — the Fumadocs content-source binding and the
  `cn()` class-name helper the components use.

## Working in this folder

New `.ts` / `.mjs` files begin with the `// SPDX-License-Identifier: MIT` header.
When you add or remove a routed locale, change it in `i18n.ts` only — the parity
assertions in the sibling build scripts turn any un-mirrored copy into a loud
build failure, which is the intended safety net; do not defeat it by editing the
hard-coded copies to match without keeping the assertion.
<!-- REUSE-IgnoreEnd -->
