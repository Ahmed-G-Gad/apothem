// SPDX-License-Identifier: MIT

// Check the built docs pages for two kinds of reader-visible defect that the
// source never shows, because they only appear once the pages are rendered:
//
// 1. Sidebar sections a keyboard cannot open or close. Every collapsible list
//    in the sidebar must be controlled by a <button> that carries
//    aria-expanded and aria-controls pointing at the list, and no sidebar link
//    may hold the open/close chevron (a toggle only a mouse click reaches).
//    See components/sidebar-folder.tsx.
// 2. Literal "**" in a page's text outside code: bold that CommonMark could
//    not close, for example bold that ends in punctuation right before a
//    letter, as happens before a Korean or Japanese particle.
//
// Run after a build, from site/: `node scripts/check-built-docs.mjs` (the
// `check:built-docs` npm script). Reads dist/ (or out/). Exits 1 on a defect.

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const BUILD_DIR = ['dist', 'out'].map((d) => join(SITE_ROOT, d)).find((d) => existsSync(d));
if (!BUILD_DIR) {
  console.error('check-built-docs: no dist/ or out/ folder; run `npm run build` first.');
  process.exit(2);
}

function* htmlFiles(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('_')) continue;
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* htmlFiles(path);
    else if (entry.name.endsWith('.html')) yield path;
  }
}

function attrs(tag) {
  const out = {};
  for (const m of tag.matchAll(/([\w:-]+)(?:="([^"]*)")?/g)) out[m[1]] = m[2] ?? '';
  return out;
}

function stripBlocks(html, tags) {
  let text = html;
  for (const tag of tags) {
    text = text.replace(new RegExp(`<${tag}\\b[\\s\\S]*?</${tag}>`, 'g'), ' ');
  }
  return text;
}

const defects = [];
let pages = 0;
let sections = 0;

for (const file of htmlFiles(BUILD_DIR)) {
  const rel = relative(BUILD_DIR, file).split(sep).join('/');
  if (!rel.includes('docs')) continue;
  const html = stripBlocks(readFileSync(file, 'utf8'), ['script', 'style']);
  if (html.includes('http-equiv="refresh"')) continue; // a redirect stub
  pages += 1;

  const start = html.indexOf('id="nd-sidebar"');
  if (start !== -1) {
    const aside = html.slice(start, html.indexOf('</aside>', start));
    const tags = [...aside.matchAll(/<(div|button|a)\b[^>]*>/g)].map((m) => [m[1], attrs(m[0])]);
    const controlled = new Map(
      tags
        .filter(([name, a]) => name === 'button' && 'aria-expanded' in a && a['aria-controls'])
        .map(([, a]) => [a['aria-controls'], a]),
    );
    for (const [name, a] of tags) {
      if (name === 'div' && a.id && 'data-state' in a) {
        sections += 1;
        if (!controlled.has(a.id)) {
          defects.push(['sidebar list with no aria-expanded button controlling it', `${rel}: #${a.id}`]);
        }
      }
    }
    for (const m of aside.matchAll(/<a\b[^>]*>([\s\S]*?)<\/a>/g)) {
      if (m[1].includes('data-icon')) {
        const href = attrs(m[0].slice(0, m[0].indexOf('>') + 1)).href;
        defects.push(['sidebar link holding the open/close icon (mouse-only toggle)', `${rel}: ${href}`]);
      }
    }
  }

  const mainStart = html.indexOf('<main');
  if (mainStart !== -1) {
    const main = html.slice(mainStart, html.indexOf('</main>', mainStart));
    const text = stripBlocks(main, ['pre', 'code']).replace(/<[^>]+>/g, ' ');
    const at = text.indexOf('**');
    if (at !== -1) {
      const context = text.slice(Math.max(0, at - 30), at + 32).replace(/\s+/g, ' ').trim();
      defects.push(['literal ** in the page text', `${rel}: "${context}"`]);
    }
  }
}

if (pages === 0 || sections === 0) {
  console.error(
    `check-built-docs: found ${pages} docs page(s) and ${sections} sidebar section(s); ` +
      'the build output does not look like the docs site.',
  );
  process.exit(2);
}
if (defects.length > 0) {
  console.error(`check-built-docs: ${defects.length} defect(s) in ${pages} built docs pages:`);
  // Group by kind so one noisy kind cannot hide the others.
  const kinds = new Map();
  for (const [kind, where] of defects) {
    if (!kinds.has(kind)) kinds.set(kind, []);
    kinds.get(kind).push(where);
  }
  for (const [kind, where] of kinds) {
    console.error(`- ${where.length} x ${kind}`);
    for (const line of where.slice(0, 5)) console.error(`    ${line}`);
  }
  process.exit(1);
}
console.log(
  `check-built-docs: ${pages} built docs pages, ${sections} sidebar sections checked; no defects.`,
);
