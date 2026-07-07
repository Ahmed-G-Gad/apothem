<!-- SPDX-License-Identifier: MIT -->

# Link-check fixture — live `/docs` site routes

These root-absolute links resolve to real pages under `site/content/docs/`,
exercising both the leaf-page (`<path>.mdx`) and the folder-index
(`<path>/index.mdx`) resolution paths. The link-check validator MUST pass this
fixture. If a referenced route is renamed, update the link here in the same
change-set.

- [FAQ](/docs/faq) — leaf page (`faq.mdx`)
- [Glossary](/docs/glossary) — leaf page (`glossary.mdx`)
- [Reference](/docs/reference) — folder index (`reference/index.mdx`)
