<!-- SPDX-License-Identifier: MIT -->

# Apothem documentation site

This is the canonical source for <https://apothem.ahmedgad.com/>. The site is a
Next.js application that uses Fumadocs for the documentation collection and
search; the deployment workflow builds this directory and publishes the static
export to GitHub Pages.

The outer directory is named `site/` because it is the full public website:
the landing page, the documentation, generated reference pages, comparison
pages, blog posts, and static assets.

## Content Layout

- `content/docs/` contains the rendered documentation tree — every page,
  comparison, blog post, and reference page the site serves. Section ordering
  is declared in each folder's `meta.json`. Routed non-default locales live in
  sibling `content/docs/<locale>/` roots (`es`, `zh-cn`, …), machine-seeded from
  the English page set.
- `app/` holds the Next.js routes: the English landing page (`app/page.tsx`),
  the docs layout and catch-all route under `app/docs/`, the per-locale routes
  under `app/[lang]/` (the localized landing card and per-locale docs), and the
  search endpoint under `app/api/search/`.
- `components/` holds the landing-page and shared UI components.
- `lib/` is the internal source of truth for cross-cutting concerns: the i18n
  cohort/locale table (`i18n.ts`), the hreflang alternate builder
  (`hreflang.ts`), and the search-index transform core (`search-index-core.mjs`,
  with its `node --test` unit test alongside it). Scripts that hard-code a
  locale set assert parity against `lib/i18n.ts` rather than duplicating it.
- `scripts/` holds the build/guard scripts (each documented in
  `scripts/README.md`): `update-reference-inventory.mjs`, `build-llms-txt.mjs`,
  `author-ia.mjs`, `check-search-index-sizes.mjs`, and `export-to-dist.mjs`.
- `public/` contains static files copied into the published artifact, including
  `CNAME`, `robots.txt`, `security.txt`, `ai.txt`, the `llms.txt` /
  `llms-full.txt` summaries, the logo set, and the social-preview images.

## Local Development

```bash
npm ci
npm run dev              # local dev server (Next.js)
npm run build            # production static export: out/ -> dist/ (served tree)
npm test                 # search-index transform unit test (node --test)
npm run check:search-index   # per-locale search-index size guard (post-build)
npm run ia:check         # curated-IA drift guard (read-only; no rewrite)
```

`npm run build` runs `next build` with `output: 'export'`, which writes the
rendered static bundle to `out/`; the `postbuild` step
(`scripts/export-to-dist.mjs`) renames it to `dist/`, the served tree the Pages
publish pipeline deploys.

### Prerequisites

- **Node.js** with npm, for the Next.js application itself.
- **Python 3.10+ on `PATH`** (as `python` or `python3`). The `predev` and
  `prebuild` steps invoke the Python engine to source-generate the reference
  pages, so `npm run dev` / `npm run build` hard-fail on a machine without a
  Python interpreter on `PATH`.

The `predev` and `prebuild` steps run `scripts/update-reference-inventory.mjs`,
so a clean build regenerates the source-generated reference pages. Regenerate
the `llms.txt` / `llms-full.txt` summaries with
`node scripts/build-llms-txt.mjs` when the documentation set changes.

## Working in this folder

This folder is a self-contained Node/Next.js application, not part of the
Python package. New `.mjs` / `.js` / `.ts` / `.tsx` files begin with the
double-slash form of the single-line SPDX license header; Markdown and MDX use
the comment form valid for each (HTML `<!-- -->` for `.md`, the `{/* */}`
expression for MDX content pages).

- **Source-generated reference pages are not edited by hand.** When a documented
  public surface in the Python package changes (a CLI command or flag, a harness
  adapter, a profile field, an installer flag), refresh the matching reference
  page by re-running `node scripts/update-reference-inventory.mjs` and committing
  the regenerated output in the same change-set. The CI docs-reference-sync drift
  gate enforces this — a dirty `git status` on a reference page after a build
  signals a missed regeneration.
- Public-facing copy stays natural: it does not name internal planning history,
  superseded release stories, or process tooling, and avoids unsupported
  marketing adjectives.
- **No JS/TS linter runs here by design.** The site ships no ESLint or Biome
  config; Next 16 no longer bundles `next lint`. The TypeScript compiler
  (`tsc`, via `next build`) is the type gate. Do not add `eslint-disable`
  directives — they reference a linter that is not installed. Where a native
  `<img>` is intentional over `next/image` (static-export SVGs), state the
  reason in a plain comment rather than a disable pragma.
- The build and dependency artifacts are generated local state — never edit or
  commit them: `.next/` (dev/build cache), `out/` and `dist/` (the static
  export and its renamed served tree), `.source/` (the Fumadocs generated
  source), `next-env.d.ts`, any `*.tsbuildinfo`, and `node_modules/`.
