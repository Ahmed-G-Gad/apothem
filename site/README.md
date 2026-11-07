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
- `components/` holds the landing-page and shared UI components, including
  `localized-link.tsx`, the MDX link component of the per-locale docs route.
- `lib/` is the internal source of truth for cross-cutting concerns: the i18n
  cohort/locale table (`i18n.ts`), the hreflang alternate builder
  (`hreflang.ts`), the body-link localizer (`locale-links.ts`), and the
  search-index transform core (`search-index-core.ts`), each with a
  `node --test` unit test alongside it. Scripts that hard-code a
  locale set assert parity against `lib/i18n.ts` rather than duplicating it.
  Each module is described in `lib/README.md`.
- `mdx-components.tsx` is the MDX component map every rendered page resolves
  through — the Fumadocs defaults plus any per-render override. A component the
  content tree uses must be reachable from here or the page fails to render.
- `scripts/` holds the build/guard scripts (each documented in
  `scripts/README.md`): `update-reference-inventory.mjs`, `build-llms-txt.mjs`,
  `author-ia.mjs`, `check-search-index-sizes.mjs`, `export-to-dist.mjs`, and
  `github-slugger-table.mjs`.
- `public/` contains static files copied into the published artifact, including
  `CNAME`, `robots.txt`, `security.txt`, `ai.txt`, the `llms.txt` /
  `llms-full.txt` summaries, the logo set, and the social-preview images.

## Local Development

```bash
npm ci
npm run dev              # local dev server (Next.js)
npm run build            # production static export: out/ -> dist/ (served tree)
npm test                 # unit tests of the build helpers (node --test)
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
- **A link on a translated page keeps the reader in their language.** Write a
  docs link once, as `/docs/<page>` or `/docs/<page>#<id>`, the same in every
  language. The per-locale docs route (`components/localized-link.tsx`, with
  `lib/locale-links.ts`) points it at the language's own copy of the page when
  there is one, and maps the English `#id` to the id of the translated heading at
  the same position; the link stays on the English page when the language has not
  translated the page or the two pages have other headings. So a cross-page
  `#fragment` is always the English id, and a same-page `(#fragment)` is the
  translated page's own id, because every page slugs its ids from its own heading
  text. Only Markdown links are localized, not the `href` of explicit JSX, `<a>` included.
  `python scripts/dev/check_site_anchor_links.py` checks this on every page
  without a build (the `quality` job runs it as
  `tests/unit/docs/test_site_anchor_links.py`): a fragment must name a heading of
  the page the link opens, a translation that records the current English text
  keeps the English headings, no component carries a `/docs` href, no hand-written
  `/<language>/docs/<page>` link names a page that language has not translated,
  and no heading is setext or empty. A heading
  whose text the script cannot slug exactly takes an explicit id,
  `## Heading [#id]`. Renaming a heading changes its id, so fix the links to it
  on every page, translations included, or keep the old id with `[#old-id]`. The
  script's slug table comes from the installed
  github-slugger (`scripts/github-slugger-table.mjs`; `npm test` fails when the
  two differ). The site chooses a link's target page while it renders, so
  `docs-build` also runs `python scripts/dev/check_built_docs_links.py site/dist`
  on the export: a translated page's links open the language's own page when the
  site could use it, and every fragment lands.
- Public-facing copy stays natural: it does not name internal planning history,
  superseded release stories, or process tooling, and avoids unsupported
  marketing adjectives.
- **Arabic pages isolate every left-to-right run.** In `content/docs/ar/`, each
  Latin run and inline code span in Arabic text sits in `<bdi>`, a code span as
  ``<bdi>`code`</bdi>``. Characters that belong to a term stay inside it: a
  command's slash (`<bdi>/plan</bdi>`), a version's plus
  (`<bdi>Node.js 18+</bdi>`), a section sign (`<bdi>§CM-7</bdi>`). One `<bdi>`
  holds a range (`<bdi>R1–R10</bdi>`), a chain joined by arrows or by a
  space-separated `>` (`<bdi>spec → generate → review</bdi>`), a label with its
  arrow (`**<bdi>Drives →</bdi>**`), a quoted English label, and a two-word term
  such as ``<bdi>POSIX `sh`</bdi>``; two separate isolates side by side display
  in reverse order. An ISO date gets its own isolate (`<bdi>2026-11-03</bdi>`):
  after an Arabic letter its digits count as Arabic numbers and the hyphens
  between them stay neutral, so a bare date displays as `03-11-2026`. Bold text
  that follows an attached letter such as `و` goes inside the isolate
  (`و<bdi>**GNU Stow**</bdi>`), because `**` between a letter and `<` cannot
  open bold and would show as two asterisks. In a block with no Arabic, each
  code span and each
  bracketed part gets its own isolate; link text that spells out its URL or
  email is one isolate. An arrow between Arabic phrases is mirrored (`←` for
  the English `→`), because the bidirectional algorithm does not mirror arrows.
  Frontmatter renders as plain text in the page header, the previous/next cards
  and the meta tags (site search renders it as Markdown), so a title or
  description isolates each run that would otherwise display out of order, such
  as a leading slash command, with the YAML escapes `\u2066` … `\u2069` inside a
  double-quoted string, never a `<bdi>` tag. A title that opens with a Latin
  word and goes on in Arabic, such as one that starts with `Apothem`, starts
  with the escape `\u200F` (a right-to-left mark), so a header or tab that
  takes its direction from the first strong character still runs right to
  left. Generated reference regions stay
  as the generator writes them. A page that
  `node scripts/translation-sources.mjs` reports as stale can still depart from
  these rules; it is brought into line when its translation is updated.
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
