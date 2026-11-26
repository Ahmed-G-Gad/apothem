// SPDX-License-Identifier: MIT

// The docs sidebar sits inside a <nav> landmark (components/docs-landmarks.tsx),
// which hides it from Fumadocs' direct-child width rule, so app/global.css sets
// the sidebar width again through the wrapper. These tests keep that copy equal
// to the value Fumadocs ships, and keep the wrapper shape the rule matches.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = join(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);

function fumadocsSidebarSource() {
  const pkg = dirname(require.resolve('fumadocs-ui/package.json'));
  return readFileSync(join(pkg, 'dist', 'layouts', 'docs', 'slots', 'sidebar.js'), 'utf8');
}

test('the site sidebar width equals the width Fumadocs sets', () => {
  const upstream = fumadocsSidebarSource().match(/md:layout:\[--fd-sidebar-width:(\d+px)\]/);
  assert.ok(upstream, 'Fumadocs no longer sets the sidebar width with md:layout:[--fd-sidebar-width:…]');
  assert.match(
    fumadocsSidebarSource(),
    /data-sidebar-placeholder/,
    'Fumadocs no longer marks the sidebar placeholder with data-sidebar-placeholder',
  );
  const css = readFileSync(join(SITE, 'app', 'global.css'), 'utf8');
  const local = css.match(
    /#nd-docs-layout:has\(> nav > \[data-sidebar-placeholder\]\)\s*\{\s*--fd-sidebar-width:\s*(\d+px);/,
  );
  assert.ok(local, 'app/global.css no longer sets the sidebar width through the nav wrapper');
  assert.equal(local[1], upstream[1]);
});

test('the sidebar width rule sits outside every cascade layer', () => {
  // The layout container sets the width to 0px from a class in the
  // `utilities` layer; a rule inside an earlier layer (such as `base`) loses to
  // it whatever its selector. Only an unlayered rule wins, so the @media block
  // holding the rule must open at brace depth 0, outside any @layer block.
  const css = readFileSync(join(SITE, 'app', 'global.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
  const at = css.search(/@media[^{]*\{\s*#nd-docs-layout:has\(> nav > \[data-sidebar-placeholder\]\)/);
  assert.notEqual(at, -1, 'the sidebar width rule is missing from app/global.css');
  let depth = 0;
  for (const ch of css.slice(0, at)) {
    if (ch === '{') depth += 1;
    else if (ch === '}') depth -= 1;
  }
  assert.equal(depth, 0, 'the sidebar width rule is nested inside a block such as @layer');
});

test('the sidebar is still wrapped in exactly one nav element', () => {
  const source = readFileSync(join(SITE, 'components', 'docs-landmarks.tsx'), 'utf8');
  assert.match(source, /<nav aria-label="Documentation" className="contents">\s*<Sidebar \{\.\.\.props\} \/>\s*<\/nav>/);
});
