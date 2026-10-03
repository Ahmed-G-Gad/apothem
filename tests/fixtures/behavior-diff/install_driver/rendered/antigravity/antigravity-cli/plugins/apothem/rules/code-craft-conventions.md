---
trigger: glob
description: "Universal code-craft delegation stub for languages without a dedicated per-language rule. Discovers the host's ratified formatter / linter / type-checker / test framework / per-language idioms and honors them per M1; surfaces silence as inquiry per M5; defers to a per-language sibling rule (code-craft-python, code-craft-shell, code-craft-markdown) when one matches the artifact's path."
globs: "**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Universal Code-Craft Delegation — Discover, Honor, Defer

## What this rule enforces

This rule binds **M13 — Code Craft Conventions** at the **universal-delegation** tier: it applies where a code artifact's language has no dedicated `rules/code-craft-<language>.md`. The discipline is **delegation**. The host's ratified code-craft conventions — formatter, linter, type-checker, test framework, build configuration, per-language idioms — MUST be **discovered** from the host's source-of-truth (manifest files, config files, sibling source files of the same language) per `rules/host-discovery.md` and **honored uniformly**. Where the host is silent on a convention the agent must adopt to act, the silence surfaces as an inquiry per `rules/authority-inquiry.md` with a recommended option per `rules/option-annotation.md`.

This stub does not duplicate the canonical M13 sub-element list (M13.1 why-not-what commenting · M13.2 naming · M13.3 error handling · M13.4 function & module design · M13.5 logging · M13.6 testing · M13.7 formatter / linter / type-checker · M13.8 security-conscious code · M13.9 concurrency · M13.10 magic number discipline · M13.11 documentation surface). Per-language siblings carry the language-specific materialization; this stub carries the **delegation contract** routing every code-craft decision through host discovery and per-language sibling-rule precedence.

## Pre-conditions

Applies whenever a code artifact is authored, modified, or reviewed AND its language matches no per-language sibling rule's `pathFilter`. The current per-language siblings at `rules/`:

| Sibling rule | Path-filter scope | When this stub yields |
|---|---|---|
| `code-craft-python.md` | `**/*.py`, `**/pyproject.toml`, `**/setup.cfg`, `**/requirements*.txt`, `**/Pipfile`, `**/tox.ini`, `**/pytest.ini`, `**/conftest.py`, `**/*.python-version`, `**/mypy.ini`, `**/ruff.toml`, `**/.ruff.toml`, `**/uv.toml`, `**/uv.lock`, `**/pyrightconfig.json` | Python artifacts |
| `code-craft-shell.md` | `**/*.sh`, `**/*.bash`, `**/*.ps1` | Shell artifacts (POSIX bash + PowerShell) |
| `code-craft-markdown.md` | `**/*.md`, `**/*.markdown` | Markdown / prose artifacts |

When a sibling's `pathFilter` matches the artifact path, the sibling applies and this stub yields. When no sibling matches (e.g., TypeScript, Go, Rust, Java, C++, Ruby), this stub is the active code-craft authority.

## Required behavior

### 1. Host Discovery — The Per-Language Walk

Before authoring code in any language without a dedicated sibling rule, the agent MUST walk the host's ratified source-of-truth files for that language:

| Language | Discovery surfaces |
|---|---|
| **TypeScript / JavaScript** | `package.json`, `tsconfig.json`, `.eslintrc*`, `.prettierrc*`, `pnpm-lock.yaml` / `yarn.lock` / `package-lock.json`, sibling `*.ts` / `*.js` files |
| **Rust** | `Cargo.toml`, `Cargo.lock`, `rustfmt.toml`, `clippy.toml`, sibling `*.rs` files |
| **Go** | `go.mod`, `go.sum`, `.golangci.yml`, sibling `*.go` files |
| **Java / Kotlin** | `pom.xml`, `build.gradle{,.kts}`, `checkstyle.xml`, `spotbugs-exclude.xml`, sibling `*.java` / `*.kt` files |
| **C / C++** | `CMakeLists.txt`, `.clang-format`, `.clang-tidy`, sibling `*.c` / `*.cpp` / `*.h` files |
| **Ruby** | `Gemfile`, `Gemfile.lock`, `.rubocop.yml`, sibling `*.rb` files |
| **Other languages** | Walk the language's package manager manifest, the language's lint / format configuration, and at least three sibling source files |

The agent MUST record every discovered convention with provenance (source file path, value, discovery date) per `rules/host-discovery.md` §4. The discovery output is the per-language ratified convention set the artifact MUST honor.

### 2. Honor Discoveries — The Sibling Convergence

The artifact MUST be **indistinguishable from one a long-tenured contributor would have written in that language**. When editing existing files, the agent MUST preserve the surrounding idioms even where it would idiomatically choose otherwise. The host's own `lint` / `format` / `test` / `type-check` commands MUST pass the artifact unmodified.

Sibling-source convergence: when the host has no explicit lint / format config but does have sibling source files of the same language, those files' observable idioms (indentation, quote style, naming, import ordering, error-handling pattern) are the ratified convention by majority observation. A new file diverging from the sibling convention is non-conformant per M14 systemic participation (`rules/systemic-participation.md`).

### 3. Surface Silence — Inquiry-Routed Choices

Where the host is silent on a code-craft convention the agent must adopt to proceed (a brand-new project with no formatter; a new language entering a polyglot host with no precedent), the agent MUST surface the choice as an inquiry per `rules/authority-inquiry.md` with the recommended option annotated per `rules/option-annotation.md`. The recommended option's rationale cites at least one concrete-driver class — community-default tooling, vendor-recommended idioms, or a host-discovered analog from a related language already in the project.

### 4. Per-Language Sibling Precedence

When the artifact path matches a per-language sibling's `pathFilter`, that sibling's specific guardrails take precedence over this stub's general delegation. The sibling carries the language-specific materialization of M13.1–M13.11; this stub neither duplicates nor contradicts it.

When a host carries a language with no per-language sibling AND that language recurs across multiple work sessions, the recurrence signals that a new sibling may be warranted per `rules/persistent-conventions-vigilance.md` §4 Ecosystem Gap Detection. The trigger is recurrence count plus convention-citation density; the gap-closure action is authoring a new `code-craft-<language>.md` sibling.

### 5. Code-Craft Sub-Element Coverage — Universal Floor

Even at the universal-delegation tier, the M13 sub-element catalog is the floor every emitted artifact MUST meet. Host-discovered conventions populate the per-language specifics; the universal floor remains:

- **M13.1 Why-not-what commenting.** Comments state intent / rationale / reference / invariant — never paraphrase what the code lexically does. No commented-out code; source control is the canonical archive.
- **M13.2 Naming.** Identifiers reveal intent. Booleans read as predicates. Single-letter names only in conventional roles.
- **M13.3 Error handling.** Caught exceptions are typed and handled or re-raised with context. No silent failure.
- **M13.4 Function & module design.** Pure-function bias where reasonable; explicit dependency injection over implicit state; one responsibility per function.
- **M13.5 Logging.** Levels are deliberate (DEBUG / INFO / WARNING / ERROR / CRITICAL); no secrets ever logged.
- **M13.6 Testing.** Behavior-descriptive test names; AAA shape (Arrange / Act / Assert); no test depends on test ordering.
- **M13.7 Formatter / linter / type-checker.** The host's ratified tools are honored; the artifact passes them clean.
- **M13.8 Security-conscious code.** No hardcoded secrets; no shell execution on unvalidated input; no SQL injection; no eval / exec on untrusted input.
- **M13.9 Concurrency.** Where applicable: no shared mutable state without documented synchronization; race conditions named when they exist.
- **M13.10 Magic number discipline.** Numeric literals appearing in logic become named constants with intent.
- **M13.11 Documentation surface.** Public functions / classes / modules carry docstrings stating preconditions, postconditions, invariants, exceptions raised.

The per-language sibling refines each sub-element with language-specific idioms; this stub enforces the floor when no sibling applies.

## Disclosure surface

Every host-discovery outcome and every silence-routed inquiry is recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[Discovery — source: <manifest-path>; language: <name>; convention: <formatter | linter | type-checker | test-framework | idiom>; value: <discovered-value>; honored]` for every honored discovery.
- `[Inquiry — id: <inquiry-id>; category: preference; outcome: <user-choice | fallback-to-recommended>]` for every silence-routed convention choice.
- `[Default — applied: <auto-decision>; class: pure-formatting-normalization]` for the carve-out cases (host has ratified style, artifact diverges, normalization applied per `rules/authority-inquiry-categories.md` §2).
- `[Refinement — improvement: maintainability; per-language gap detected: <language>; recurrence: <count>; tracking: <gap-closure inquiry-or-task>]` when the recurrence count surfaces a new per-language-sibling-rule candidate.

## Failure tells

A TypeScript file in a project standardized on `prettier` + `eslint` that uses a different formatter or quote style than every sibling file (sibling-convergence violation). A Rust file with `unsafe` blocks lacking a `// SAFETY: <invariant>` comment in a project where every other `unsafe` block carries one (idiom drift). A Go file using `panic` as control flow in a project where every other Go file uses error returns (M13.3 error-handling drift). A Ruby file silently introducing a new RuboCop violation in a project with `.rubocop.yml` ratified (M13.7 formatter / linter drift). A new language introduced into a polyglot project without a code-craft sibling rule and without the recurrence-tracking surface (the rule's gap-detection signal is suppressed). A new language file authored without the host-discovery walk (the agent invented conventions where the host has them). A change-set that touches a per-language sibling-rule-covered path AND a stub-covered path, where the stub-covered language drifts while the sibling-covered language remains conformant (asymmetric attention to the per-language sibling vs. the stub's general delegation).

## Bindings (§0.j five-direction)

- **Drives →** ● Every code artifact authoring session in a language without a dedicated per-language sibling rule (every TypeScript, Go, Rust, Java, C++, Ruby, Kotlin, Swift, etc. artifact). ● Per-language host-discovery walks for every code-touched language. ● The recurrence-tracking surface that signals new per-language-sibling-rule candidates. ◐ The sibling-convergence enforcement at `rules/systemic-participation.md` (M14).
- **Satisfies →** ● the fifteen-mandate registry row **M13 — Code Craft** (universal-delegation tier; per-language tier is the per-language sibling rules).
- **Established by ↑** ● the fifteen-mandate registry (ratifies M13). ● The user-scope ecosystem's mandate to carry a universal code-craft floor for every language regardless of per-language sibling presence.
- **Gated by ←** ● the trivial-vs-non-trivial threshold (trivial-scope code edits run an abbreviated check covering M13.1 why-not-what + M13.7 formatter / linter only). ● `CLAUDE.md` always-loaded preamble. ● Per-language sibling rule pathFilter precedence (this stub yields when a sibling matches).
- **Cross-bound with ↔** ↔ `rules/code-craft-python.md` (Python sibling — takes precedence on Python paths). ↔ `rules/code-craft-shell.md` (Shell sibling — takes precedence on shell paths). ↔ `rules/code-craft-markdown.md` (Markdown sibling — takes precedence on Markdown paths). ↔ `rules/host-discovery.md` (M1 — per-language discovery is the M1 walk for code-craft conventions). ↔ `rules/authority-inquiry.md` (M5 — silence-routed choices). ↔ `rules/option-annotation.md` (M7 — recommended-option annotation on inquired conventions). ↔ `rules/systemic-participation.md` (M14 — sibling convergence is the M14 silo-prevention surface for code). ↔ `rules/persistent-conventions-vigilance.md` (CM-22 §4 — recurrence-driven gap detection signals new per-language-sibling-rule candidates). ↔ `rules/systemic-participation-relations.md` (universal-delegation stub's sibling-convergence enforcement at §2 binds here for code-language artifacts). ↔ `rules/ten-dimension-check-dimensions.md` (per-language code-craft rules apply dimensions 4, 7, 8, 10 with language-specific failure tells).
