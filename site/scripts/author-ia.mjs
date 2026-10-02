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

import { readdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// Anchor to the script's own location, not the caller's cwd, so the generator
// resolves the docs tree identically regardless of the directory it is invoked
// from (matching the SCRIPT_DIR anchoring the sibling site scripts use).
const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const SITE_ROOT = join(SCRIPT_DIR, '..');
const DST_ROOT = join(SITE_ROOT, 'content', 'docs');

function meta(title, pages) {
  return JSON.stringify({ title, pages: [...pages, '...'] }, null, 2) + '\n';
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
  '404',
];
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
    'index', 'claude-code', 'cursor', 'gemini-cli', 'github-copilot',
    'codex', 'windsurf', 'zed', 'opencode', 'qwen-code', 'kiro', 'trae',
    'codebuddy', 'antigravity', 'hermes', 'kimi-code', 'open-claw', 'glm',
  ]],
  // `pipeline` is not authored here: update-reference-inventory.mjs generates
  // pipeline/meta.json (English and every locale) from the shipped command
  // definitions, so a new command cannot land without a nav entry.
  concepts: ['Concepts', [
    'index', 'ai-platform-agnosticism', 'agent-architecture',
    'review-fortress', 'cognitive-identity', 'seriousness-tiers',
    'resumable-planning',
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
    'settings-reference', 'doctor', 'naming-conventions', 'frontmatter-schema',
    'markdown-conventions', 'prose-conventions', 'commit-conventions',
    'artifact-schema', 'artifact-registries', 'directory-tree', 'claude-md',
    'ai-conventions', 'authorship-header', 'dependency-pinning-manifest',
    'plans-discipline',
  ]],
  'cli-reference': ['CLI reference', [
    'index', 'quickstart', 'install', 'uninstall', 'update', 'verify',
    'status', 'diff', 'rollback', 'migrate-workspace', 'doctor', 'harnesses',
    'profile', 'completion',
  ]],
  comparison: ['Comparison', [
    'index', 'vs-other-harness-frameworks', 'vs-raw-claude-code',
    'vs-raw-cursor', 'vs-raw-gemini-cli', 'vs-raw-github-copilot',
    'vs-raw-codex', 'vs-raw-windsurf', 'vs-raw-zed', 'vs-raw-opencode',
    'vs-raw-qwen-code', 'vs-raw-kiro', 'vs-raw-trae', 'vs-raw-codebuddy',
    'vs-raw-antigravity', 'vs-raw-hermes', 'vs-raw-kimi-code',
    'vs-raw-open-claw', 'vs-raw-glm',
  ]],
  governance: ['Governance', [
    'index', 'positioning', 'cross-cutting-mandates', 'pre-emission-gate-registry',
    'authoritative-inquiry-registry', 'outward-conformity-registry',
    'release-engineering-policy', 'badge-policy',
  ]],
  security: ['Security', [
    'index', 'openssf-scorecard-target', 'branch-protection-ruleset',
    'webhooks-audit', 'binary-artifacts-sweep',
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
  blog: ['Blog', [
    'index', 'posts/v1-0-1-release', 'posts/multi-harness-adapter-design',
    'posts/cross-harness-convention-convergence',
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
// of the English IA, so they are matched by the kebab locale-segment pattern
// and excluded — mirroring the locale-dir heuristic the sibling
// update-reference-inventory.mjs uses.
const LOCALE_DIR_RE = /^[a-z]{2}(-[a-z]{2})?$/i;

function liveRootKeys() {
  const keys = [];
  for (const entry of readdirSync(DST_ROOT, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!LOCALE_DIR_RE.test(entry.name)) keys.push(entry.name);
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
  const curatedRoot = new Set(rootKeyList.filter((p) => !/^---.*---$/.test(p)));
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

const CHECK_ONLY = process.argv.includes('--check');

if (CHECK_ONLY) {
  console.log(
    'author-ia --check: curated IA is in sync with the live docs tree (no drift).',
  );
} else {
  write('meta.json', rootMeta);
  for (const [dir, [title, pages]] of Object.entries(sections)) {
    write(join(dir, 'meta.json'), meta(title, pages));
  }
  console.log(`Authored ${Object.keys(sections).length + 1} meta.json files.`);
}
