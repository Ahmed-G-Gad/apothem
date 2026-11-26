// SPDX-License-Identifier: MIT

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { flattenIndexOnlyFolders } from './page-tree.ts';

const item = (name, url) => ({ type: 'page', name, url });

test('a folder holding only its index page becomes that page', () => {
  const index = item('Conformity gate', '/docs/conformity-gate');
  const root = {
    name: 'Docs',
    children: [{ type: 'folder', name: 'Conformity gate', index, children: [] }],
  };
  assert.deepEqual(flattenIndexOnlyFolders(root).children, [index]);
});

test('folders with pages, and folders without an index, are kept', () => {
  const index = item('Blog', '/docs/blog');
  const post = item('Post', '/docs/blog/posts/a');
  const withPages = { type: 'folder', name: 'Blog', index, children: [post] };
  const noIndex = { type: 'folder', name: 'Empty', children: [] };
  const root = { name: 'Docs', children: [withPages, noIndex] };
  assert.deepEqual(flattenIndexOnlyFolders(root).children, [withPages, noIndex]);
});

test('nested folders and the fallback tree are cleaned too', () => {
  const index = item('Only', '/docs/a/only');
  const nested = { type: 'folder', name: 'A', children: [{ type: 'folder', name: 'Only', index, children: [] }] };
  const root = { name: 'Docs', children: [nested], fallback: { name: 'Docs', children: [nested] } };
  const out = flattenIndexOnlyFolders(root);
  assert.deepEqual(out.children[0].children, [index]);
  assert.deepEqual(out.fallback.children[0].children, [index]);
  // The input tree is not changed.
  assert.equal(root.children[0].children[0].type, 'folder');
});

test('only the 404 page is hidden from the sidebar', async () => {
  const { isHiddenFromSidebar } = await import('./page-tree.ts');
  assert.equal(isHiddenFromSidebar(['404']), true);
  assert.equal(isHiddenFromSidebar([]), false);
  assert.equal(isHiddenFromSidebar(['install', '404']), false);
  assert.equal(isHiddenFromSidebar(['install']), false);
});
