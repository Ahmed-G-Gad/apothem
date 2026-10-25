---
name: "dynamism"
description: "No static substitutions for dynamic-source-of-truth values — every version, badge, release-reference, and docs-version surface renders dynamically from a single source of truth; static-string embeds across the 7 closed-set surfaces are structural failures."
pathFilter: "**/README.md, **/__init__.py, **/site/**, **/pyproject.toml, **/*social-card*, **/.github/workflows/release*.yml"
alwaysApply: false
paths:
  - "**/README.md"
  - "**/__init__.py"
  - "**/site/**"
  - "**/pyproject.toml"
  - "**/*social-card*"
  - "**/.github/workflows/release*.yml"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Dynamism — No Static Substitutions for Dynamic-Source-of-Truth Values

## Obligations

Every changing value MUST render from one live authority. Version, release, badge, docs-version, runtime `__version__`, and social-card-stamp values MUST NOT be inlined as static strings. A static embed is structural drift, not acceptable maintenance debt.

**Closed surface set (7).** npm version badge · npm downloads badge · GitHub Release badge · README latest-release prose · docs version selector · runtime `__version__` · social-card version stamp. A candidate eighth surface MUST route through `rules/authority-inquiry.md` before it joins the set.

**Source invariant.** One displayed value MUST resolve through exactly one authority — registry endpoint, GitHub Releases, `pyproject.toml`, docs-version generator, git-tag stream, or release pipeline. Divergent sources for the same value are findings.

**Permitted static contexts.** Historical CHANGELOG entries, git-tag annotations, and SPDX / license headers MAY hold literal versions.

**Release closure.** A release event MUST leave zero stale displays. A non-self-updating surface — especially a raster card — MUST be re-rendered during release or retired.

## Failure tells

A hard-pinned install snippet. A literal-version badge URL. `__version__ = "x.y.z"` while the manifest is authoritative. Social-card version text with no release re-render step. Any `static-version-grep` hit marked acceptable.

## Enforcement

Always-on at every seriousness level. `conformity/static_version_grep.py` sweeps the 7 closed surfaces; the pre-emission gate consumes its verdict.
