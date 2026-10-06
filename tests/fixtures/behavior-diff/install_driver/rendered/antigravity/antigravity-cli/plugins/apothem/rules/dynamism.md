---
trigger: glob
description: "No static substitutions for dynamic-source-of-truth values — every version, badge, release-reference, and docs-version surface renders dynamically from a single source of truth; static-string embeds across the 7 closed-set surfaces are structural failures."
globs: "**/README.md, **/__init__.py, **/site/**, **/pyproject.toml, **/*social-card*, **/.github/workflows/release*.yml"
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

## Bindings (§0.j five-direction)

- **Drives →** Every version-, badge-, release-, and docs-version-bearing artifact across the apothem repo (README badges, install snippets, `__init__.py` `__version__`, site config, social-card pipeline). The mechanical matcher at `conformity/static_version_grep.py` operationalises the Obligations static-embed prohibition. Every release-pipeline step that refreshes the seven surfaces.
- **Satisfies →** Dynamic version rendering across the closed set of seven surfaces; zero-static-embed posture; the release-pipeline freshness invariant.
- **Established by ↑** The operator's directive to render version numbers dynamically and resolve GitHub version mismatch dynamically.
- **Gated by ←** The `pathFilter` version-surface globs (demand-loaded when a version-bearing surface — README, `__init__.py`, docs site, `pyproject.toml`, social-card, release workflow — is touched). The pre-emission gate at `rules/pre-emission-gate.md` row 8 (the mechanical matcher's verdict gates emission). `rules/host-discovery.md` (the host's source-of-truth artifact for each dynamic class is discovered, not assumed).
- **Cross-bound with ↔** `rules/persistent-conventions-vigilance.md` (CM-22 — dynamism is a ratified ecosystem convention; new surfaces trigger the §4 Ecosystem Gap Detection routing). `rules/host-discovery.md` (M1 — every dynamic source-of-truth surface is discovered from the host's ratified manifest / config / build files before the dynamic rendering mechanism is wired). `rules/disclosure-ledger.md` (M2 — every static-to-dynamic conversion and every new-surface inquiry outcome is recorded in the ledger). `rules/pre-emission-gate.md` (M4 — bar 8 of the gate fires the `static-version-grep` matcher and consumes its verdict). `conformity/static_version_grep.py` (the mechanical matcher this rule's static-embed prohibition operationalises). `rules/propagation.md` (version and badge propagation is one surface of the whole-repo propagation mandate).
