// SPDX-License-Identifier: MIT

// Server-renders the sidebar's disclosure folder (components/sidebar-folder.tsx)
// closed and open, and checks the button-to-list wiring a screen reader relies
// on. The built pages render every section open, so the closed state is
// covered here: the list must stay in the HTML under the id the button's
// `aria-controls` names, carry `hidden`, and the button must report
// `aria-expanded="false"`.
//
// The component is TSX, which Node's type stripping does not read, so the
// test bundles it with esbuild (installed with fumadocs-mdx) into
// node_modules/.cache and keeps every package import external, so the bundle
// shares the site's own React and Fumadocs copies.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { createElement as h } from 'react';
import { renderToString } from 'react-dom/server';
import { FrameworkProvider } from 'fumadocs-core/framework';
import { SidebarProvider } from 'fumadocs-ui/components/sidebar/base';

const SITE = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(SITE, 'node_modules', '.cache', 'sidebar-folder-test', 'sidebar-folder.mjs');

async function loadComponent() {
  mkdirSync(dirname(OUT), { recursive: true });
  await build({
    entryPoints: [join(SITE, 'components', 'sidebar-folder.tsx')],
    outfile: OUT,
    bundle: true,
    format: 'esm',
    platform: 'node',
    jsx: 'automatic',
    packages: 'external',
    tsconfig: join(SITE, 'tsconfig.json'),
    logLevel: 'silent',
  });
  return import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
}

const { DisclosureFolder, runsAnimation } = await loadComponent();

function render({ defaultOpen, pathname = '/ja/docs/other' }) {
  const item = {
    type: 'folder',
    name: 'Install',
    defaultOpen,
    index: { type: 'page', name: 'Install', url: '/ja/docs/install' },
    children: [],
  };
  const tree = h(
    FrameworkProvider,
    { usePathname: () => pathname, useRouter: () => ({}), useParams: () => ({}) },
    h(
      SidebarProvider,
      { defaultOpenLevel: 0 },
      h(DisclosureFolder, { item }, h('a', { href: '/ja/docs/install/windows' }, 'Windows')),
    ),
  );
  return renderToString(tree);
}

function attrs(tag) {
  const out = {};
  for (const m of tag.matchAll(/\s([\w:-]+)(?:="([^"]*)")?/g)) out[m[1]] = m[2] ?? '';
  return out;
}

function toggle(html) {
  const tag = html.match(/<button\b[^>]*>/)?.[0];
  assert.ok(tag, 'no toggle button in the rendered folder');
  return attrs(tag);
}

function elementById(html, id) {
  const escaped = id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const tag = html.match(new RegExp(`<[a-z]+\\b[^>]*\\sid="${escaped}"[^>]*>`))?.[0];
  return tag ? attrs(tag) : null;
}

test('a closed folder keeps its list in the page, hidden, under the id the button names', () => {
  const html = render({ defaultOpen: false });
  const button = toggle(html);
  assert.equal(button['aria-expanded'], 'false');
  assert.ok(button['aria-controls'], 'the closed button lost aria-controls');
  const list = elementById(html, button['aria-controls']);
  assert.ok(list, `aria-controls="${button['aria-controls']}" names no element`);
  assert.equal(list['data-state'], 'closed');
  assert.ok('hidden' in list, 'the closed list is not hidden');
  assert.match(html, /href="\/ja\/docs\/install\/windows"/, 'the closed list dropped its links');
});

test('an open folder shows its list under the id the button names', () => {
  const html = render({ defaultOpen: true });
  const button = toggle(html);
  assert.equal(button['aria-expanded'], 'true');
  const list = elementById(html, button['aria-controls']);
  assert.ok(list, `aria-controls="${button['aria-controls']}" names no element`);
  assert.equal(list['data-state'], 'open');
  assert.ok(!('hidden' in list), 'the open list is hidden');
});

test('the button is named by the section link plus the hint in the page language', () => {
  const html = render({ defaultOpen: false });
  const ids = toggle(html)['aria-labelledby']?.split(' ') ?? [];
  assert.equal(ids.length, 2, 'aria-labelledby should name the link and the hint');
  for (const id of ids) assert.ok(elementById(html, id), `aria-labelledby names a missing id "${id}"`);
  assert.match(html, /ページを表示または非表示/);
});

test('a reduced-motion animation of 0.01 ms or less counts as no animation', () => {
  const style = (animationName, animationDuration) => ({ animationName, animationDuration });
  assert.equal(runsAnimation(style('none', '0s')), false);
  assert.equal(runsAnimation(style('', '0.2s')), false);
  assert.equal(runsAnimation(style('fd-collapsible-up', '1e-05s')), false);
  assert.equal(runsAnimation(style('fd-collapsible-up', '0.01ms')), false);
  assert.equal(runsAnimation(style('fd-collapsible-up', '0s')), false);
  assert.equal(runsAnimation(style('fd-collapsible-up', '0.15s')), true);
  assert.equal(runsAnimation(style('fd-collapsible-up', '150ms')), true);
  assert.equal(runsAnimation(style('none, fd-collapsible-up', '0s, 0.15s')), true);
});
