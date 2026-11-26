// SPDX-License-Identifier: MIT

// Author the Fumadocs information-architecture meta.json files for the
// ported docs tree. One meta.json per section + the docs-root meta.json.
//
// Fumadocs reads `meta.json` per directory: `{ "title", "pages": [...] }`.
// `pages` is the explicit ordering; `index` is the section landing page;
// `"..."` (rest glob) appends any unlisted pages so nothing is dropped.
//
// Run from `site/`: `node scripts/author-ia.mjs`
//
// Pass `--check` to run the drift guard WITHOUT rewriting any meta.json (a
// read-only mode for CI / pre-commit): it asserts every live doc page is
// accounted for in the curated lists and exits non-zero on drift, leaving the
// tree untouched. The `ia` / `ia:check` npm scripts wrap the two modes.

import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

// Anchor to the script's own location, not the caller's cwd, so the generator
// resolves the docs tree identically regardless of the directory it is invoked
// from (matching the SCRIPT_DIR anchoring the sibling site scripts use).
const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const SITE_ROOT = join(SCRIPT_DIR, '..');
const DST_ROOT = join(SITE_ROOT, 'content', 'docs');

// A section's `index` page is left out of the written `pages` list on purpose.
// Fumadocs then makes the folder title itself the link to the overview page.
// Listing `index` as well showed every section twice: the folder title
// ("Blog", "Reference") followed by its overview page as a first child with the
// same or a near-same name. The curated lists below keep `index` so the drift
// guard still accounts for it.
function meta(title, pages) {
  return (
    JSON.stringify({ title, pages: [...pages.filter((p) => p !== 'index'), '...'] }, null, 2) +
    '\n'
  );
}

function write(rel, content) {
  writeFileSync(join(DST_ROOT, rel), content, 'utf8');
}

// --- Root meta: section ordering + root pages, grouped with separators. ---
// The `---Label---` entries are Fumadocs group separators, not pages; the
// drift guard skips them and matches only the real page/section keys.
const rootPages = [
  'index',
  '---Get started---',
  'install',
  'tutorials',
  'usage',
  'how-to',
  'how-to-guides',
  '---Platform---',
  'harnesses',
  'platforms',
  'pipeline',
  'concepts',
  'architecture',
  '---Reference---',
  'reference',
  'cli-reference',
  'comparison',
  'glossary',
  '---Operate---',
  'governance',
  'security',
  'conformity-gate',
  'runbooks',
  'examples',
  '---Learn---',
  'faq',
  'developer-guide',
  'internationalization',
  'blog',
  '---Project---',
  'changelog',
  'community',
  'brand',
];
// Root pages that exist but are left out of the sidebar on purpose. The root
// meta has no rest glob, so a key missing from `rootPages` is not shown. The
// 404 page is the not-found fallback: the sitemap and llms.txt leave it out
// too, and a "Page not found" sidebar entry would lead readers to an error.
const HIDDEN_ROOT_PAGES = ['404'];
const rootMeta =
  JSON.stringify({ title: 'Documentation', pages: rootPages }, null, 2) + '\n';

// --- Per-section metas (index first, then curated order, then rest glob). ---
const sections = {
  install: ['Install', [
    'index', 'quickstart', 'concepts', 'harness-setup', 'updating',
    'uninstalling', 'troubleshooting',
  ]],
  usage: ['Usage', [
    'index', 'getting-started', 'authoring-plans', 'writing-rules',
    'using-agents', 'hook-development', 'conformity-gate',
    'large-codebase-onboarding',
  ]],
  tutorials: ['Tutorials', ['index', 'getting-started']],
  'how-to': ['How-to guides', [
    'index', 'editing-the-profile', 'adding-a-harness',
    'installer-environment-variables', 'evals',
  ]],
  harnesses: ['Harnesses', [
    'index', 'claude-code', 'cursor', 'gemini-cli', 'github-copilot', 'codex',
    'windsurf', 'zed', 'opencode', 'qwen-code', 'kiro', 'trae', 'codebuddy',
    'antigravity', 'hermes', 'open-claw', 'kimi-code', 'glm',
  ]],
  // `pipeline` is not authored here: update-reference-inventory.mjs generates
  // pipeline/meta.json (English and every locale) from the shipped command
  // definitions, so a new command cannot land without a nav entry.
  concepts: ['Concepts', [
    'index', 'ai-platform-agnosticism', 'resumable-planning',
    'agent-architecture', 'review-fortress', 'cognitive-identity',
    'seriousness-tiers',
  ]],
  architecture: ['Architecture', [
    'index', 'source-layout', 'shared-profile-schema',
    'harness-adapter-abstraction', 'cohort-packaging-contract',
    'installation-workflow', 'self-contained-runtime', 'vendoring-strategy',
    'agents', 'cicd-pipeline',
  ]],
  reference: ['Reference', [
    'index', 'cli', 'profile-fields', 'harness-registry', 'rules', 'skills',
    'commands', 'agents', 'hooks', 'output-styles', 'mcp', 'settings',
    'settings-reference', 'naming-conventions', 'frontmatter-schema',
    'markdown-conventions', 'prose-conventions', 'commit-conventions',
    'artifact-schema', 'artifact-registries', 'directory-tree', 'claude-md',
    'ai-conventions', 'authorship-header', 'dependency-pinning-manifest',
    'plans-discipline',
  ]],
  'cli-reference': ['CLI reference', [
    'index', 'quickstart', 'install', 'uninstall', 'update', 'rollback',
    'backups', 'verify', 'status', 'diff', 'doctor', 'harnesses', 'profile',
    'migrate-workspace', 'completion',
  ]],
  comparison: ['Comparison', [
    'index', 'vs-other-harness-frameworks', 'vs-raw-claude-code',
    'vs-raw-cursor', 'vs-raw-gemini-cli', 'vs-raw-github-copilot',
    'vs-raw-codex', 'vs-raw-windsurf', 'vs-raw-zed', 'vs-raw-opencode',
    'vs-raw-qwen-code', 'vs-raw-kiro', 'vs-raw-trae', 'vs-raw-codebuddy',
    'vs-raw-antigravity', 'vs-raw-hermes', 'vs-raw-open-claw',
    'vs-raw-kimi-code', 'vs-raw-glm',
  ]],
  governance: ['Governance', [
    'index', 'positioning', 'cross-cutting-mandates', 'pre-emission-gate-registry',
    'authoritative-inquiry-registry', 'outward-conformity-registry',
    'release-engineering-policy', 'badge-policy',
  ]],
  security: ['Security', [
    'index', 'openssf-scorecard-target', 'openssf-best-practices',
    'branch-protection-ruleset', 'webhooks-audit', 'binary-artifacts-sweep',
  ]],
  runbooks: ['Runbooks', [
    'index', 'release-cycle', 'deployment-checklist', 'release-recovery',
    'pages-enablement', 'publisher-account-setup',
    'new-harness-adapter-authoring', 'cross-machine-sync-checklist',
    'solo-maintainer-merge',
  ]],
  examples: ['Examples', [
    'index', 'custom-rule', 'minimal-hook', 'authoring-a-harness-adapter',
    'plan-walkthrough',
  ]],
  brand: ['Brand', [
    'index', 'palette', 'harness-colors', 'logo-usage', 'rebuild-recipe',
  ]],
  community: ['Community', [
    'index', 'roadmap', 'discussions', 'code-of-conduct',
  ]],
  // The posts are listed flat under Blog; `!posts` keeps the rest glob from
  // also appending the `posts` folder, which showed every post a second time
  // inside an extra "Posts" folder.
  blog: ['Blog', [
    'index', 'posts/v1-6-0-release', 'posts/multi-harness-adapter-design',
    'posts/cross-harness-convention-convergence', '!posts',
  ]],
  'conformity-gate': ['Conformity gate', ['index']],
};

// Recursively collect the page keys a section directory carries: every
// `.md`/`.mdx` file, mapped to the posix-relative stem the curated `pages`
// arrays use (`index`, `posts/v1-0-0-release`). Locale subtrees never appear
// here — the per-section directories under content/docs/ hold English source
// only; the routed-locale copies live in sibling `<locale>/` roots.
function livePageKeys(dir) {
  const keys = [];
  const root = join(DST_ROOT, dir);
  let entries;
  try {
    entries = readdirSync(root, { withFileTypes: true });
  } catch {
    // A curated section with no directory yet is not a drift error: the write
    // below creates it. The guard only fails on live pages the list omits.
    return keys;
  }
  for (const entry of entries) {
    if (entry.isDirectory()) {
      for (const nested of livePageKeys(join(dir, entry.name))) {
        keys.push(`${entry.name}/${nested}`);
      }
    } else if (/\.mdx?$/i.test(entry.name)) {
      keys.push(entry.name.replace(/\.mdx?$/i, ''));
    }
  }
  return keys;
}

// meta.json-parity drift guard. A meta.json's `pages` list is the explicit
// ordering; the trailing `'...'` rest glob appends any unlisted page so the
// generator never DROPS a page, but an unlisted page lands unordered at the
// tail and the curated intent silently rots behind the live tree. This guard
// makes that rot a hard failure: every live page under a section MUST appear
// in that section's curated list. A rerun therefore cannot regenerate the IA
// while quietly leaving a real page out of the authored order — the operator
// is forced to add it (or intentionally exclude it) before the meta is
// rewritten.
// Top-level keys the root meta must account for: every root-level `.md`/`.mdx`
// singleton plus every non-locale subdirectory under content/docs/. Routed
// locale subtrees (`es`, `zh-cn`, …) are their own content roots, not sections
// of the English IA. Their names come from ROUTED_LOCALES in lib/i18n.ts, the
// site's one locale list, so an English section with a two-letter name is never
// mistaken for a locale.
function routedLocaleDirs() {
  const src = readFileSync(join(SITE_ROOT, 'lib', 'i18n.ts'), 'utf8');
  const match = src.match(/export const ROUTED_LOCALES[^=]*=\s*\[([^\]]*)\]/);
  if (!match) {
    throw new Error('author-ia: could not read ROUTED_LOCALES from lib/i18n.ts');
  }
  const defaultMatch = src.match(/export const DEFAULT_LOCALE\s*=\s*'([^']+)'/);
  const defaultLocale = defaultMatch ? defaultMatch[1] : 'en';
  return [...match[1].matchAll(/'([^']+)'/g)]
    .map((m) => m[1])
    .filter((locale) => locale !== defaultLocale);
}
const LOCALE_DIRS = routedLocaleDirs();

function liveRootKeys() {
  const keys = [];
  for (const entry of readdirSync(DST_ROOT, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!LOCALE_DIRS.includes(entry.name)) keys.push(entry.name);
    } else if (/\.mdx?$/i.test(entry.name)) {
      keys.push(entry.name.replace(/\.mdx?$/i, ''));
    }
  }
  return keys;
}

function assertNoDrift(sectionMap, rootKeyList) {
  const drift = [];
  // Root level: every root singleton + non-locale section directory MUST be
  // named in the root meta. Group separators (`---Label---`) are not pages.
  const curatedRoot = new Set([
    ...rootKeyList.filter((p) => !/^---.*---$/.test(p)),
    ...HIDDEN_ROOT_PAGES,
  ]);
  for (const key of liveRootKeys()) {
    if (!curatedRoot.has(key)) drift.push(key);
  }
  // Per-section level: every live page under a section MUST be in its list.
  for (const [dir, [, pages]] of Object.entries(sectionMap)) {
    const curated = new Set(pages);
    for (const key of livePageKeys(dir)) {
      if (!curated.has(key)) {
        drift.push(`${dir}/${key}`);
      }
    }
  }
  if (drift.length > 0) {
    throw new Error(
      `author-ia: ${drift.length} live doc page(s) missing from the curated ` +
        `meta.json lists — add each to its section in scripts/author-ia.mjs ` +
        `before regenerating the IA:\n  ${drift.sort().join('\n  ')}`,
    );
  }
}

assertNoDrift(sections, rootPages);

// --- Locale metas: the English order, the locale's own labels. ---
// Each routed locale carries its own meta.json per section, with a translated
// `title` and translated `---Label---` group separators. The page order must
// still be the English one: a page added to an English list but not to a
// locale list is either missing from that locale's sidebar or appended
// unordered at its tail by the rest glob. So the locale `pages` array is
// derived from the English one here, and only the labels are kept from the
// locale file.
const SEPARATOR_RE = /^---.*---$/;

// A missing file is normal (a new section or locale); a file that is there but
// does not parse is an error. Falling back to English for it would silently
// overwrite the locale's translated labels.
function readJson(rel) {
  let text;
  try {
    text = readFileSync(join(DST_ROOT, rel), 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') return undefined;
    throw error;
  }
  try {
    return JSON.parse(text.replace(/^﻿/, ''));
  } catch (error) {
    throw new Error(`author-ia: ${posix(rel)} is not valid JSON: ${error.message}`);
  }
}

function posix(rel) {
  return rel.split(sep).join('/');
}

// The locale's group labels are matched to the English groups by position. A
// locale file whose number of groups differs from the English list (an English
// group was added, removed or split) would put every later label over the
// wrong group, so that is an error: the new label needs a translator.
function localePages(englishPages, current, rel) {
  const englishCount = englishPages.filter((p) => SEPARATOR_RE.test(p)).length;
  const localeSeparators = (current?.pages ?? []).filter((p) => SEPARATOR_RE.test(p));
  if (current && localeSeparators.length !== englishCount) {
    throw new Error(
      `author-ia: ${posix(rel)} has ${localeSeparators.length} sidebar ` +
        `group label(s) and the English list has ${englishCount}. Edit its ` +
        `---Label--- entries to match the English groups, translated, then rerun.`,
    );
  }
  let ordinal = 0;
  return englishPages.map((p) => {
    if (!SEPARATOR_RE.test(p)) return p;
    const label = localeSeparators[ordinal] ?? p;
    ordinal += 1;
    return label;
  });
}

// Every meta.json this script owns, as [path, content] pairs: the English
// root and section metas, then each locale's. Write mode writes them all and
// --check compares them all, so a hand edit to any of them is caught.
function authoredMetaFiles() {
  const out = [['meta.json', rootMeta]];
  for (const [dir, [title, pages]] of Object.entries(sections)) {
    out.push([join(dir, 'meta.json'), meta(title, pages)]);
  }
  for (const loc of LOCALE_DIRS) {
    const rootRel = join(loc, 'meta.json');
    const root = readJson(rootRel);
    out.push([
      rootRel,
      JSON.stringify(
        { title: root?.title ?? 'Documentation', pages: localePages(rootPages, root, rootRel) },
        null,
        2,
      ) + '\n',
    ]);
    for (const [dir, [title, pages]] of Object.entries(sections)) {
      const rel = join(loc, dir, 'meta.json');
      const current = readJson(rel);
      out.push([rel, meta(current?.title ?? title, pages)]);
    }
  }
  return out;
}

const CHECK_ONLY = process.argv.includes('--check');
const metaFiles = authoredMetaFiles();

if (CHECK_ONLY) {
  const stale = metaFiles
    .filter(([rel, content]) => {
      try {
        return readFileSync(join(DST_ROOT, rel), 'utf8').replace(/\r\n/g, '\n') !== content;
      } catch {
        return true;
      }
    })
    .map(([rel]) => posix(rel));
  if (stale.length > 0) {
    console.error(
      `author-ia --check: ${stale.length} meta.json file(s) differ from the ` +
        `sidebar lists in scripts/author-ia.mjs (every language follows the English ` +
        `order) — run \`node scripts/author-ia.mjs\`:\n  ${stale.sort().join('\n  ')}`,
    );
    process.exit(1);
  }
  console.log(
    'author-ia --check: curated IA is in sync with the live docs tree (no drift).',
  );
} else {
  for (const [rel, content] of metaFiles) {
    mkdirSync(dirname(join(DST_ROOT, rel)), { recursive: true });
    write(rel, content);
  }
  const localeCount = metaFiles.length - Object.keys(sections).length - 1;
  console.log(
    `Authored ${Object.keys(sections).length + 1} English and ${localeCount} locale meta.json files.`,
  );
}
