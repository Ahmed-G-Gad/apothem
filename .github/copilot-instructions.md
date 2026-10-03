<!-- SPDX-License-Identifier: MIT -->

# GitHub Copilot Instructions

These are the repository-scoped instructions for GitHub Copilot when generating
code, prose, or commits in this repository. They are mandatory and ship with
every published checkout. They are coherent with [`AGENTS.md`](../AGENTS.md)
and [`CLAUDE.md`](../CLAUDE.md); where shared disciplines overlap (plans
locality, authorship headers, ambiguity handling, naming, release freshness,
human-only authorship, agent-guidance surface locality, session closure,
public-surface plain-language, operating loop, and synthesis posture), the
surfaces are semantically equivalent and `AGENTS.md` is the canonical project
voice.

## Project Context

This repository is Apothem, a host-agnostic AI-harness configuration manager.
It reads a shared profile (`~/.config/apothem/profile.yaml`) and materializes
harness-native config files for the seventeen registered adapters —
Antigravity, Claude Code, CodeBuddy, Codex, Cursor, Gemini CLI,
GitHub Copilot, Hermes, Kimi Code, Kiro, Open-Claw, OpenCode, Qwen Code, Trae,
Windsurf, Zed, and GLM (Z.ai). The shared profile carries rules, slash-commands, skills, hooks,
output-styles, settings, schemas, and docs. The
engine is invoked as `python -m apothem`; the Claude Code plugin, the npm
shim (`npx @ahmed-g-gad/apothem`), and the one-shot script installers run the
same module surface. From a checkout, `PYTHONPATH=src python -m apothem` puts
the vendored dependencies (`src/apothem/_vendor`) on `sys.path`; the host
interpreter must provide `click` and `rich`. It is single-author maintained. The source layout is the
canonical authoring layout; harness adapters convert or relocate cohorts at
install time when a target harness expects a different native surface.
Consumers include Codex, Claude Code, GitHub Copilot, and the optional
assistants opted in under
[`site/content/docs/reference/ai-conventions.mdx`](../site/content/docs/reference/ai-conventions.mdx). The published tree is
the canonical artifact; nothing is stored elsewhere and copied in.

Agent-facing operating guidance lives in two surfaces: the root `AGENTS.md`
is the single repo-internal agent-instruction canon, and each folder's
per-folder operating contract lives in that folder's `README.md` (the README
serves both the human and the agent reader). Materialized harness-output
`AGENTS.md` files under `src/apothem/harnesses/*/templates/` are product
surfaces Apothem generates for downstream tools — they are not repo-internal
companions and are exempt from this canon.

## Operating Loop & Synthesis Posture

Three shared claims this surface preserves, semantically equivalent to
[`AGENTS.md`](../AGENTS.md) and [`CLAUDE.md`](../CLAUDE.md):

- **Operating loop.** The planning pipeline (`/plan`) flows into the hardening
  pipeline (`/fortress`), which closes at the release gate — plan → harden →
  ship. The planning suite's executed work (the phases `/plan-execute` lands)
  is the surface `/fortress` hardens to a release-gated state.
- **Synthesis posture.** A non-trivial mission **SHOULD** be accomplished
  through genuinely-independent critique-synthesis multi-agent work that keeps
  the main conversation lean — raw agent output is released after a single-pass
  synthesis — grounded in current authoritative sources, with beyond-mission
  remediation disclosed per the disclosure-ledger discipline. The capability is
  specified at
  [`src/apothem/rules/multi-agent-workflow.md`](../src/apothem/rules/multi-agent-workflow.md)
  and reachable via `/workflow`; it is opt-in and default-off under the agnostic
  posture, so a clean install never auto-invokes it.
- **Session closure.** Every session — an ad-hoc exchange as much as a plan
  phase — ends with a formal, verifiable close: a Recommended Next Step, a
  done / deferred ledger, and a verification attestation of what was checked and
  how it came out. The discipline is specified at
  [`src/apothem/rules/session-closure.md`](../src/apothem/rules/session-closure.md).
  A session that trails off mid-thread, claims done without a checked outcome,
  or buries deferred work silently is a structural failure.

## Coding Conventions

Files and folders use **kebab-case** (`some-name.ext`,
`some-folder/sub-folder/`). The canonical-uppercase exceptions are
`CLAUDE.md`, `README.md`, `LICENSE`, `CHANGELOG.md`, `SECURITY.md`,
`CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, and the few all-caps top-level files
their respective conventions require.

Directive prose uses the **RFC 2119** modal hierarchy: `MUST`, `MUST NOT`,
`SHOULD`, `SHOULD NOT`, `MAY`. Suggestions inside generated code carry the
same hierarchy when expressing requirements (e.g., a docstring stating "this
function MUST be called from the main thread").

Markdown uses ATX headings (`#`, `##`, …) with exactly one `H1` per file.
Frontmatter, when present, uses **kebab-case keys**. Code fences are
language-tagged. Lists use `-` for unordered items.

For Python: target Python 3.10+; use modern syntax (`list[int]`,
`dict[str, Any]`, `X | None`); use `dataclasses` (or `pydantic.BaseModel` when
validation is part of the contract) for data containers; prefer
`pathlib.Path` over `os.path`; use `typing.Protocol` for structural types;
keep generated code passing `ruff check` and `mypy --strict` against the
project's configured strict-mode scope.

For shell: target POSIX bash where the host has bash, PowerShell 7 elsewhere;
use `set -euo pipefail` (bash) or `Set-StrictMode -Version Latest` plus
`$ErrorActionPreference = 'Stop'` (PowerShell); pass `shellcheck` (bash) or
`Invoke-ScriptAnalyzer` (PowerShell) clean.

Commits follow **Conventional Commits**: `type(scope): subject` with
imperative mood and a subject under 72 characters. Release tags follow
**Semantic Versioning**: `vMAJOR.MINOR.PATCH`. Branches follow
`type/short-description` (e.g., `feat/add-multi-surface-validator`,
`fix/banner-injector-edge-case`).

## File Headers

Every applicable new file Copilot generates **MUST** begin with the canonical
`SPDX-License-Identifier: MIT` header line per
[`site/content/docs/reference/authorship-header.mdx`](../site/content/docs/reference/authorship-header.mdx), in the
comment family matching the filetype. There is one line per file — the
bordered branded banner box (copyright / website / email / GitHub /
license-pointer lines) is retired; the root `LICENSE` carries the full
copyright instrument. The byte-exact fixture is at
[`src/apothem/schemas/authorship-header.txt`](../src/apothem/schemas/authorship-header.txt). Per comment
family:

- hash files (`.py`, `.sh`, `.yaml`, `.toml`, …): `# SPDX-License-Identifier: MIT`
- double-slash (`.js`, `.ts`, `.mjs`): `// SPDX-License-Identifier: MIT`
- markdown / HTML: `<!-- SPDX-License-Identifier: MIT -->`
- C-block (`.css`, `.c`): `/* SPDX-License-Identifier: MIT */`
- semicolon (`.ini`): `; SPDX-License-Identifier: MIT`
- double-dash (`.sql`): `-- SPDX-License-Identifier: MIT`

To add the SPDX line, run the canonical injector:

```bash
python scripts/inject-header.py --mode fix-in-place <path>
# or
bash scripts/inject-header.sh --mode fix-in-place <path>
```

The injector is idempotent, detects the filetype variant from the path, and
inserts the SPDX line at the correct position (after a shebang if present;
after any frontmatter — which must stay byte-first so documentation
generators can parse it; immediately above the first content line otherwise).

The SPDX line is **exempt** for the following classes — the validator returns
`not-applicable` and Copilot **MUST NOT** insert a header into them:

- `LICENSE` (carries its own copyright instrument)
- JSON files (no comment syntax — use a sibling `*.NOTICE.md` if attribution
  is required)
- Lockfiles (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`,
  `Pipfile.lock`, `poetry.lock`, `go.sum`, …)
- Generated files (those with a `Generated by …` marker or
  `linguist-generated=true` in `.gitattributes`)
- Vendored third-party content (under `vendor/`, `third_party/`,
  `node_modules/`)
- `.audit/` files (gitignored ephemera)
- `<project-root>/.apothem/plans/` files (a legacy
  `<project-root>/.plans/` tree is upgraded via `apothem migrate-workspace`) —
  gitignored ephemera; provenance is the plan's frontmatter)
- Empty markers (`.keep`, `.gitkeep`)
- Binary files

The full glob list is at
[`src/apothem/schemas/header-exceptions.txt`](../src/apothem/schemas/header-exceptions.txt). Adding a
new exemption requires an explicit operator confirmation and an ADR under the
repository's ratified ADR location.

## Plans Discipline

Copilot **MUST NOT** generate code, scripts, or prose that write to a
harness configuration directory (e.g. `~/.claude/.plans/` for Claude Code)
or any other global plans location. Planning artifacts —
architecture sketches, work-breakdown structures, refactor strategies,
debugging journals, exploration notes, prompt drafts — live exclusively at
`<project-root>/.apothem/plans/`, the sole canonical plans home. A legacy
`<project-root>/.plans/` tree is no longer canonical; operators upgrade an
existing one via `apothem migrate-workspace`.

The `<project-root>/.apothem/plans/` directory (a legacy
`<project-root>/.plans/` tree is upgraded via `apothem migrate-workspace`) is
**gitignored** per the canonical
`.gitignore` snippet documented in
[`site/content/docs/reference/plans-discipline.mdx`](../site/content/docs/reference/plans-discipline.mdx). Plans **MUST
NEVER** be committed to a project's git history. If a plan converges to a
durable decision, the decision is **promoted** to an ADR under
the project's ratified ADR directory; the plan itself is then archived to
`.apothem/plans/_archive/` or discarded.

Plan filenames follow `YYYY-MM-DD--<kebab-case-slug>.md`. Plans transition
through the lifecycle states **draft → in-progress → converged** (promote to
ADR) **or abandoned**, recorded in each plan's frontmatter `status:` field.

When Copilot suggests a refactor strategy, a debugging walkthrough, a
multi-step task list, or any other artifact written *to think with* rather
than *to ship*, it MUST route the suggestion to a fresh
`<project-root>/.apothem/plans/YYYY-MM-DD--<slug>.md` file, never to a chat
transcript that ends up pasted into source.

## Release Facade

Public release surfaces must remain current-version-only: one visible release
tag, one GitHub Release, and one Pages deployment, with no public-facing
narrative that references earlier release work or internal planning history.
Apothem distributes through several install paths — tool-native plugins and
extensions (the Claude Code plugin via `/plugin marketplace add ahmed-g-gad/apothem`,
a Gemini CLI extension via `gemini extensions install`, a Qwen Code extension
via `qwen extensions install`, a Codex plugin via
`codex plugin marketplace add`, and a VS Code-family extension packaged as
`apothem.vsix`, which the release workflow attaches to each new GitHub
Release), the npm shim (`npx @ahmed-g-gad/apothem` — also the
install path for OpenCode and every other adapter-only tool, which expose no
harness-native plugin surface), and the
one-shot script installers (`install.sh` / `install.ps1`) — and each
tagged release attaches its signed artifacts (sdist + wheel + SBOM + cosign
signature + SLSA provenance) to the single GitHub Release page as
verification evidence. The GitHub Release is published only after local gates
and the CI, Clean Install Gate, Harness Matrix, and Conformity workflows are
green; publication is never the first validation step.

## Living Documentation

Any change to a documented public surface (a CLI command or flag, a harness
adapter, a profile field, an installer flag or environment variable, a
configuration key, or any surface with a page under `site/content/docs/`)
**MUST** update that documentation page in the same change-set; source-generated
reference pages are kept current by re-running
`node site/scripts/update-reference-inventory.mjs` and committing the
regenerated pages, and the CI docs-reference-sync drift gate enforces it.

## Harness Installation Discipline

Adapters install Apothem cohorts through each harness's documented native
surface. A cohort may be converted when the native format differs, such as
Codex TOML agents or Gemini TOML commands. When a harness has no matching
native primitive for rules, hooks, templates, skills, or agents, the files land
under an Apothem-owned support subtree and are referenced from the native
instruction anchor; they are not forced into vendor-reserved directories.

## Structured Inquiry Behavior

When Copilot is uncertain about a value it would otherwise have to invent, it
**MUST NOT** silently fabricate. It inserts a clearly-marked clarification
comment of the form:

```python
# TODO(clarify): which retention period applies to this audit log — 30, 90, or 365 days?
```

```typescript
// TODO(clarify): is the API base URL the staging or production endpoint?
```

```bash
# TODO(clarify): should this script run under the deploy user or the application user?
```

The `TODO(clarify): ...` marker is the surface-equivalent of a harness-native
structured-inquiry channel: a structured, reviewable, never-silent record that
an assumption was deferred to the human. Where the surface allows (chat panel,
PR comment thread, IDE peek view), Copilot also surfaces the question verbatim
so the developer sees it without scanning the diff.

When uncertain, Copilot **MUST NEVER** fabricate the following data classes:

- **Identity** — names, emails, handles, organizations, team affiliations,
  copyright lines.
- **Scope direction** — which subtree, which branch, which environment
  (dev / staging / prod), which target.
- **Preference** — formatter / linter / test-framework / CI provider where
  the host has not ratified one.
- **Security** — secret-rotation cadence, allowed shells, allowed network
  egress, accepted-risks list.
- **Naming** — a new convention introduced where the host has none.
- **Infrastructure** — endpoints, hosts, ports, regions, queue names, table
  names.
- **Version pins** — which version of which dependency where the host has
  not pinned and the choice matters.

In every one of these cases, the correct response is a `TODO(clarify): ...`
marker with the question stated specifically, never a plausible-looking
placeholder that compiles.

## Forbidden Patterns

The following patterns are forbidden in generated code, prose, and commit
messages:

- **Marketing adjectives** — `powerful`, `seamless`, `robust`,
  `industry-leading`, `cutting-edge`, `world-class`. Marketing adjectives
  are forbidden in user-facing artifacts unless concretely substantiated by
  a measurement or citation immediately adjacent.
- **Hedging filler** — `basically`, `kind of`, `in some sense`,
  `more or less`, `pretty much`. Hedging filler is forbidden in directive
  text (rules, schemas, contracts, runbooks). Where uncertainty is genuine,
  state the uncertainty precisely (e.g., "this benchmark holds within ±5%
  on the reference hardware") rather than gesturing at it.
- **`console.log`-equivalent debug detritus** — `print()`, `console.log`,
  `eprintln!`, `fmt.Println` left in committed code as ad-hoc debugging
  output. Use the project's logger at the appropriate level instead.
- **Hard-coded absolute paths to user home** — `/home/alice/...`,
  `/Users/alice/...`, `C:\Users\Alice\...`. Use `${HOME}`, `~`,
  `os.path.expanduser`, `pathlib.Path.home()`, or installer-time
  substitution.
- **Committing secrets, tokens, or API keys** — never. The `secret-scan`
  validator and pre-commit hooks block this; do not work around them.
- **Committing files under `<project-root>/.apothem/plans/`** (a legacy
  `<project-root>/.plans/` tree is upgraded via `apothem migrate-workspace`) —
  never. The directory is gitignored; assume any plan write is local-only.
- **Non-human git authorship attribution** — git authorship surfaces (commit
  author, `Co-Authored-By` trailers, `Signed-off-by`, tag annotations) MUST
  name human contributors only. AI tools, assistants, models, IDE extensions,
  and runtimes MUST NOT be added as co-authors.
- **Contradicting [`AGENTS.md`](../AGENTS.md)** — when this file and
  `AGENTS.md` overlap on a shared discipline, they are semantically
  equivalent. A surface-specific override requires an inline
  `<!-- coherence-override: <claim-id> -->` marker paired with an ADR under
  the repository's ratified ADR location; a silent contradiction is a build
  failure.

## Output Format

Generated code carries:

- A **documented public surface** — every public function, class, or module
  has a docstring or header comment stating its preconditions,
  postconditions, and failure modes. Generated private helpers carry
  docstrings only when the logic is non-obvious.
- **Types where the language supports them** — Python type hints on every
  signature (no `Any` without a justifying comment); TypeScript types on
  every export; Go return types on every function; Rust types throughout.
- **Tests where a test scaffolding exists** — when the project ships a
  test directory, every new public function emits at least one
  behavior-descriptive test alongside the implementation. AAA shape
  (Arrange / Act / Assert), one assertion per test, no test depends on
  test ordering.
- **The canonical `SPDX-License-Identifier: MIT` header line** at the file
  head, injected via the canonical injector (see *File Headers* above).
- **No commented-out code** — source control is the canonical archive for
  removed code; the working tree is the live state.

Generated commit messages follow **Conventional Commits** with a body that
explains *why* the change was made (not what — the diff already shows what).
Subject lines are imperative-mood and stay under 72 characters. Breaking
changes carry the `!` marker (e.g., `refactor(api)!: rename …`) and a
`BREAKING CHANGE:` paragraph in the body.

When Copilot's suggestion shape is a refactor proposal, design walkthrough,
or other multi-step plan rather than concrete code, the suggestion is routed
to `<project-root>/.apothem/plans/YYYY-MM-DD--<slug>.md` per *Plans Discipline*
above — not pasted inline into source as a multi-paragraph comment block.

## Review Checklist

Before approving any pull request — whether the reviewer is human or Copilot
itself in PR-review mode — verify each of the following:

- The canonical `SPDX-License-Identifier: MIT` header line is present at the
  head of every applicable new file (per *File Headers*).
- All filenames are kebab-case, with canonical-uppercase exceptions only.
- No file under `<project-root>/.apothem/plans/` (a legacy
  `<project-root>/.plans/` tree is upgraded via `apothem migrate-workspace`) is
  staged for commit; no path references a harness configuration directory
  (e.g. `~/.claude/.plans/` for Claude Code) as a write target.
- No claim in the diff contradicts [`AGENTS.md`](../AGENTS.md). When they
  overlap, they say the same thing in different framings.
- Local validators run green: `make lint && make validate && make test`
  (or the project's per-language equivalents — `ruff check`, `mypy --strict`,
  `pytest`, `shellcheck`, `Invoke-ScriptAnalyzer`).
- Every `TODO(clarify): ...` comment introduced by the diff is either
  resolved (the clarification is captured in code, docs, or a follow-up
  issue) or explicitly deferred with rationale in the PR description.
- No marketing adjectives, no hedging filler, no debug detritus, no
  hard-coded user-home paths, no secrets in the diff.
- Commit messages are Conventional Commits with imperative-mood subjects
  under 72 characters; commit bodies explain *why*.

## Pointers

- [`AGENTS.md`](../AGENTS.md) — the canonical project voice; every shared
  claim in this file mirrors a claim there.
- [`CLAUDE.md`](../CLAUDE.md) — the Claude Code mirror of the same shared
  disciplines.
- [`site/content/docs/reference/plans-discipline.mdx`](../site/content/docs/reference/plans-discipline.mdx) — the full
  Plans Discipline reference (lifecycle, frontmatter schema, archive
  protocol, gitignore snippet).
- [`site/content/docs/reference/authorship-header.mdx`](../site/content/docs/reference/authorship-header.mdx) — the full
  authorship-header reference (per-filetype variants, exception list,
  visibility policy, injector usage).
- [`site/content/docs/reference/ai-conventions.mdx`](../site/content/docs/reference/ai-conventions.mdx) — the multi-surface
  AI-conventions overview (which surfaces ship, the reconciliation rule,
  the override mechanism).
- [`src/apothem/schemas/authorship-header.txt`](../src/apothem/schemas/authorship-header.txt) —
  the byte-exact header fixture.
- [`src/apothem/schemas/header-exceptions.txt`](../src/apothem/schemas/header-exceptions.txt) —
  the exemption glob list.
- [`tests/fixtures/multi-surface-claims.yaml`](../tests/fixtures/multi-surface-claims.yaml) —
  the claim list this file is validated against by the
  `multi-surface-coherence` validator.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — the contributor's guide
  (commit conventions, branching model, local validation, PR review
  expectations).
