<!-- SPDX-License-Identifier: MIT -->

<!-- REUSE-IgnoreStart -->
# Site build & guard scripts

Node build-and-guard scripts for the documentation site. Each is a self-contained
`.mjs` using only Node built-ins, anchored to its own location (`SCRIPT_DIR`) so
it resolves the same tree regardless of the working directory it is invoked from.
Run any of them from `site/`.

## Scripts

- **`update-reference-inventory.mjs`** — source-generates the reference pages
  under `content/docs/reference/` from the Python package's public surface, plus
  the generated blocks on `architecture/source-layout.mdx` (top-level CLI
  commands), `conformity-gate/index.mdx` (validator table) and
  `pipeline/index.mdx` (command index), a page under `pipeline/` for every
  shipped command without a hand-written one, and the `pipeline/meta.json` nav in
  English and every locale. Runs as the `predev` and `prebuild` npm hooks; a
  dirty `git status` under `content/docs/` after a build signals a missed
  regeneration (the CI docs-reference-sync drift gate enforces it). Do not
  hand-edit the generated pages or blocks.
- **`build-llms-txt.mjs`** — walks `content/docs/**` and emits the English-only
  `public/llms.txt` (compact index) and `public/llms-full.txt` (concatenated
  bodies). Runs in `prebuild`. `assertLocaleParity()` fails the build if its
  hard-coded locale set drifts from `lib/i18n.ts`, so a newly-routed locale
  cannot leak its translated pages into the English artifacts.
- **`author-ia.mjs`** — authors the Fumadocs `meta.json` information-architecture
  files (section ordering), except `pipeline/meta.json`, which
  `update-reference-inventory.mjs` generates. Carries `assertNoDrift`, which
  fails if a live doc page is missing from a curated list. Run `node scripts/author-ia.mjs` to
  regenerate the metas, or `--check` (the `ia:check` npm script) to run the drift
  guard read-only without rewriting — the check-only mode is the CI-safe form.
- **`check-search-index-sizes.mjs`** — guards the per-locale static search-index
  sizes in the built output. Re-derives `ROUTED_LOCALES` from `lib/i18n.ts` via
  `assertLocaleParity()` and fails on drift. Runs after a build
  (`check:search-index` npm script).
- **`export-to-dist.mjs`** — the `postbuild` step: renames Next's `out/` static
  export to `dist/`, the served tree the Pages publish pipeline deploys, baking
  the correct per-locale `lang`/`dir` into each locale's HTML.

## Working in this folder

New `.mjs` files begin with the `// SPDX-License-Identifier: MIT` header. A
script that hard-codes a locale set MUST assert parity against `lib/i18n.ts`
rather than duplicating it silently — follow the `assertLocaleParity()` pattern
the sibling scripts use so a locale added to the i18n cohort fails the build here
instead of silently skewing an artifact.
<!-- REUSE-IgnoreEnd -->
