// SPDX-License-Identifier: MIT

import { createMDX } from 'fumadocs-mdx/next';

const withMDX = createMDX();

/** @type {import('next').NextConfig} */
const config = {
  reactStrictMode: true,
  // Static HTML export. The site is served as a static bundle from GitHub
  // Pages (apothem.ahmedgad.com), so the build emits fully rendered pages with
  // no server runtime; documentation search runs client-side over a static
  // index. Next writes the export to `out/`; the `postbuild` step moves it to
  // `dist/`, the directory the Pages pipeline serves.
  output: 'export',
  // A static export has no on-demand image server, so images are served as
  // authored rather than optimized at request time.
  images: { unoptimized: true },
  // Pin the workspace root to this directory so Turbopack does not infer a
  // parent root from a lockfile higher up the tree (the repo root).
  turbopack: {
    root: import.meta.dirname,
  },
};

export default withMDX(config);
