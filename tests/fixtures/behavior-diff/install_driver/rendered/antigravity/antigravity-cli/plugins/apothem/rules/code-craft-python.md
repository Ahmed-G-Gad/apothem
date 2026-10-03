---
trigger: glob
description: "Per-language code-craft for Python — strict SOLID compliance, modern type hinting (3.10+ syntax, no Any), Google-style docstrings, specific exception handling, pytest discipline, security guardrails (no hardcoded secrets, no shell injection, no unsafe deserialization), and architectural anti-pattern interception. Path-filtered to Python source files and configuration manifests."
globs: "**/*.py, **/pyproject.toml, **/setup.py, **/setup.cfg, **/requirements*.txt, **/Pipfile, **/tox.ini, **/pytest.ini, **/conftest.py, **/.flake8, **/mypy.ini, **/ruff.toml, **/.ruff.toml, **/uv.toml, **/uv.lock, **/.python-version, **/pyrightconfig.json"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Code Craft — Python

## What this rule enforces

This rule binds **M13 — Code Craft Conventions** at the **Python per-language tier**. Every Python artifact the agent produces — script, hook, helper, library, test, configuration generator, migration script, deployment manifest, snippet — MUST meet a Senior-Architect floor: strict SOLID compliance, modern type hinting (Python 3.10+ syntax with conditional fallbacks per `python_requires`), Google-style docstrings, specific-exception handling, pytest-only test discipline, security-conscious code (no hardcoded secrets, no shell injection, no unsafe deserialization), and proactive anti-pattern interception. Correctness and readability supersede premature optimization. Output is clean, resilient, scalable, maintainable, and idiomatically Pythonic.

## Pre-conditions

Applies whenever a Python artifact matching the `pathFilter` glob list — Python source, lockfiles, lint / format / type-check / test configurations, `python_requires` manifests, virtualenv pinning files — is authored, modified, or reviewed. The §6 seriousness scaling sets the FLOOR per level: any Python file touch activates at least the EXPLORING row even when the surrounding session is EXPLORING globally — never lower. Ecosystem-internal Python under `tools/`, `hooks/`, and `tests/` honors this rule alongside host-project Python.

## Required behavior

### 1. Strict SOLID Compliance

Non-negotiable in every non-trivial Python module:

- **SRP.** Every class, function, and module has exactly one reason to change. If a class name requires "and" to describe its purpose, it violates SRP — split it.
- **OCP.** Open for extension via composition, `Protocol`, and strategy patterns — closed for modification. Use registries, plugin patterns, and dispatch tables over growing `if/elif` chains.
- **LSP.** Every subclass perfectly substitutable for its parent — no weakened postconditions, no strengthened preconditions, no unexpected exceptions. If overriding tempts you to change the contract, use composition instead.
- **ISP.** `Protocol` classes with narrow interfaces over monolithic ABCs. A `Readable` protocol with `read()` beats a `FileHandler` ABC with `read()`, `write()`, `delete()`, `rename()`.
- **DIP.** High-level modules never import low-level modules — both depend on `Protocol` / `ABC` abstractions, with concrete implementations injected at composition root (`main()` or a DI container) and never constructed inside the consumer. Cross-layer injection discipline (which language-agnostic patterns to apply where) lives in `rules/clean-architecture-layers.md` §2.3 — this rule covers Python materialization only (`Protocol` / `ABC` choice, composition-root wiring style, `from __future__ import annotations` for forward references in interface modules).

### 2. Implementation & Style

#### 2.1 Version Detection

Before generating Python code, determine the project's minimum supported version from, in priority order: `python_requires` in `pyproject.toml` / `setup.cfg`, `.python-version`, `tox.ini` envlist, CI matrix. If undetermined, assume 3.10. Below 3.10: use `Optional[X]` not `X | None`, `Union[A, B]` not `A | B`, and omit `match`/`case`. Below 3.11: omit `Self`, and use `asyncio.gather` not `TaskGroup`. The (3.10+) / (3.11+) annotations below are conditional — emit modern syntax only when the detected target supports it.

#### 2.2 Formatting & Naming (M13.2)

- **PEP 8** baseline. Assume **`ruff`** for linting and formatting (preferred) or `black` (88 chars) + `isort`: (1) stdlib, (2) third-party, (3) local. Absolute imports only.
- `snake_case` functions / variables / modules, `PascalCase` classes / type aliases, `UPPER_SNAKE_CASE` constants, `_leading_underscore` internal / private.
- No single-char names except `i / j / k` in loops, `x` in lambdas, `_` for discarded. Names reveal intent: `calculate_portfolio_risk()` not `process_data()`.

#### 2.3 Type Hinting

Mandatory, strict, modern on ALL signatures, class attributes, and module-level variables:

- Modern syntax (3.10+): `list[int]`, `dict[str, T]`, `X | None` — never `List`, `Dict`, `Optional` from `typing`.
- **Ban `Any`** — use `Protocol`, `TypeVar`, `Generic`, or `@overload` instead. Narrow exceptions: third-party boundary types with incomplete stubs, JSON deserialization results pre-validation, and `**kwargs` forwarding to external APIs. Each use requires a justifying comment (`# Any: <reason>`).
- Use `TypeAlias` for complex types, `Literal` for constrained strings, `Final` for constants, `ClassVar` for class-level, `Self` (3.11+) for builder returns.
- `Protocol` over `ABC` for structural subtyping. Return type annotations mandatory including `-> None`.

#### 2.4 Documentation (M13.1, M13.11)

- **Google Style docstrings** (`Args:`, `Returns:`, `Raises:`) for all public entities. Private: docstring when logic is non-obvious.
- Inline comments explain **"why"**, never "what." No commented-out code (source control is the canonical archive). Module docstrings describe purpose and public API.

#### 2.5 Error & Resource Management (M13.3)

- Catch **specific exceptions** — never bare `except:` or generic `except Exception:` (unless re-raising at outermost boundary).
- `try / except / else / finally` used logically. Custom exception hierarchies rooted in project-level base. Exceptions carry context in message and attributes.
- Never raise exceptions as a signaling mechanism between layers (Python's EAFP idiom for guard checks is acceptable). Use `contextlib.suppress()` over empty `except` blocks.
- **Always context managers (`with`)** for I/O and resources. `@contextmanager` or `__enter__` / `__exit__` for custom lifecycle. `ExitStack` for dynamic resource counts. Never rely on GC for cleanup.

#### 2.6 Modern Patterns

- **`dataclasses` / `attrs`** for data-holding classes — never manual `__init__` / `__repr__` / `__eq__`. Use `field(default_factory=...)` for mutable defaults.
- **Pydantic** for external data validation. **`Enum`** for fixed constant sets — never magic strings / ints (M13.10).
- **`pathlib.Path`** over `os.path`. **f-strings** only. **`functools.cache` / `lru_cache`** for expensive pure functions.
- **`itertools` + generators** for lazy evaluation. **`__slots__`** for memory-dense classes. **`match` / `case`** (3.10+) for complex dispatch.
- **`asyncio`** for I/O-bound concurrency (M13.9). Never block the event loop with sync I/O. Use `TaskGroup` (3.11+) for structured concurrency. `async with` / `async for` for async resources and iterators.
- **`logging.getLogger(__name__)`** per module (M13.5). Structured logging via `structlog` for production. Never `print()` for operational output.

### 3. Testing Directives (M13.6)

- **`pytest` exclusively** — never `unittest.TestCase`. Test files mirror source: `src/domain/user.py` → `tests/domain/test_user.py`.
- **Arrange-Act-Assert** in every test, separated by blank lines. One behavior per test. Names describe behavior: `test_calculate_risk_raises_on_insufficient_data`.
- Cover **happy paths, edge cases** (boundary, empty, None, Unicode), and **failure modes** (invalid input, missing deps, timeouts). Every bug fix ships a regression test in the same change-set.
- **Fixtures** scoped to the narrowest sufficient scope. **`parametrize`** when input varies but the assertion pattern is constant. **`pytest.raises(match=...)`** for exception testing.
- **`unittest.mock.patch`** at the import site, not the definition. **`tmp_path`** for filesystem. **`monkeypatch`** for env vars. **Factory functions** for complex test data.
- Test behavior, never implementation details. Never mock what you do not own — wrap it in an adapter and mock the adapter. Never `sleep()` — mock the clock.

### 4. Security Directives (M13.8)

#### 4.1 Secrets & Configuration

- **Zero hardcoded secrets.** Keys, passwords, tokens from env vars or secret managers. `os.environ["KEY"]` (hard fail), never `get("KEY", "default")` for secrets.
- `.env` in `.gitignore`. Always verify before commit.

#### 4.2 Input Validation & Injection Prevention

- **Validate all external data** at system boundaries. **SQL**: parameterized queries only. **Commands**: never `shell=True` with untrusted input — use `subprocess.run(["cmd", arg])`.
- **Paths**: `pathlib.Path.resolve()` + verify within bounds. **Deserialization**: never `pickle` / `yaml.load()` for untrusted data — use `json` / `yaml.safe_load()` / Pydantic.
- **Templates**: auto-escaping (Jinja2 `autoescape=True`). **Regex**: avoid catastrophic backtracking; timeout user-supplied patterns.

#### 4.3 Dependency & Runtime Safety

- **Pin deps** in production (`==`). Ranges only in library `pyproject.toml`. **Audit** regularly (`pip-audit`, `safety`). Prefer **`uv`** for environment and dependency management.
- Never log secrets / PII. Structured logging with sanitized messages. Minimal privilege — never root unless required.

### 5. Architectural Guardrails

#### 5.1 Quality Audit

Audit for missing abstractions, leaky abstractions, god objects, feature envy (methods using another class's data more than their own), primitive obsession (raw `str` / `int` / `dict` where domain types add safety), inappropriate intimacy — triggered when reading, reviewing, or modifying a class / module of 150+ lines, or when a symbol recurs across 3+ files. Refactor immediately when detected; do not defer.

#### 5.2 Refactoring & Output

- **Concrete, scoped refactorings** — never vague. Atomic: one structural change per refactoring. Preserve all tests. Update all affected type hints, docstrings, imports.
- **Output**: concise working solution first → brief architectural rationale → surgical changes matching surrounding codebase conventions.

#### 5.3 Anti-Pattern Interception

Intercept during design: `isinstance` chains → `Protocol` / strategy. Mutable defaults → `field(default_factory=...)`. Global state → injected dependency. Circular imports → redesign boundaries. `import *` → explicit. String constants → `Enum`. `os.path` → `pathlib`. `print()` → `logging`. Sync I/O in async → flag.

### 6. Seriousness Scaling

| Level | Enforcement |
| ----- | ----------- |
| EXPLORING | PEP 8 + type hints + specific exceptions. SOLID awareness only |
| PERSONAL_USE | Full style. SOLID on public API. Public docstrings. AAA tests. No hardcoded secrets |
| SHARED | All sections enforced. Design violations are findings. Full test coverage. Security audit |
| PUBLIC_LAUNCH | Full + `mypy --strict`. 100% public API docs. Dependency audit. Security as quality gate |

### 7. Anti-Patterns

- **DON'T** use bare `except:` or `except Exception:` (unless re-raising at the outermost boundary) — **BECAUSE** it swallows errors and masks bugs.
- **DON'T** declare mutable defaults (`def f(items=[])`) — **BECAUSE** the default is shared across calls.
- **DON'T** use `Any` type hints — **BECAUSE** it disables type checking where you need it most.
- **DON'T** subclass built-ins (`dict`, `list`) — **BECAUSE** C methods bypass overrides. Use `UserDict` / `UserList`.
- **DON'T** write monolithic test functions with multiple Act-Assert pairs — **BECAUSE** the first failure masks the rest.
- **DON'T** suppress with `# type: ignore` without an error code + justifying comment — **BECAUSE** blanket suppression hides real errors.
- **DON'T** inherit concrete classes for reuse — **BECAUSE** brittle hierarchies. Use composition + `Protocol`.

## Disclosure surface

Every Python artifact emission, refit, or anti-pattern interception is recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[Discovery — source: pyproject.toml | setup.cfg | .python-version | tox.ini; value: <python_requires>; honored]` for every version-detection outcome that shapes type-hint syntax.
- `[Discovery — source: ruff.toml | .ruff.toml | pyproject.toml [tool.ruff]; value: <ruleset>; honored]` for honored lint-config discoveries.
- `[Refinement — improvement: maintainability; intercepted: <anti-pattern>; refactor: <description>]` for proactive anti-pattern interceptions during design.
- `[Default — applied: <auto-decision>; class: pure-formatting-normalization]` for ruff / black formatter normalizations on existing files where the host has a ratified style.

## Failure tells

`def f(items=[])` (mutable default — shared across calls). `except:` / `except Exception: pass` (silent swallow — M13.3 violation). `Any` type hint without `# Any: <reason>` justifying comment (typecheck disabled where it matters most). `from typing import Optional, Union` in a project with `python_requires = ">=3.10"` (legacy syntax where modern is available). `subprocess.run(cmd, shell=True)` with untrusted input (shell injection — M13.8). `pickle.loads(untrusted_bytes)` (deserialization attack surface). `yaml.load(untrusted)` without `Loader=yaml.SafeLoader` (RCE attack surface). `print()` for operational output (M13.5 — should be `logging.getLogger(__name__).info(...)`). Tests written as `unittest.TestCase` subclasses in a project with `pytest` configured (test-framework drift — M13.6). `# TODO: fix this` without a tracking issue (open marker per `rules/definitiveness.md` M8). `os.path.join(a, b)` in a 3.10+ codebase (legacy API — should be `pathlib.Path(a) / b`). Magic numbers in business logic without named constants (M13.10). Public function with no docstring (M13.11). A test using `time.sleep(3)` to wait for a side effect (timing dependency instead of mocking time).

## Bindings (§0.j five-direction)

- **Drives →** ● Every Python artifact's quality floor across every host project (SOLID enforcement, type-hint discipline, docstring requirement, pytest convention, security guardrails). ● Every `tools/*.py` and `hooks/*.py` and `tests/*.py` touch under the path-filter. ● Every Python-language manifestation of the Senior Software Architect role declared at `rules/cognitive-identity.md` §1. ◐ The Python-language materialization of clean architecture layer discipline (the §1 DIP discussion cross-references `rules/clean-architecture-layers.md` §2.3).
- **Satisfies →** ● the fifteen-mandate registry row **M13 — Code Craft** at the Python per-language tier. ● CM-28 (Python Senior Architect — rule-delegated mandate; this rule is the canonical specification CM-28 delegates to). ● the rules registry row "Code Craft — Python".
- **Established by ↑** ● the fifteen-mandate registry (ratifies M13). ● CM-28. ● `rules/cognitive-identity.md` (Python is the primary language declared at §2). ● PEP 8, PEP 484, PEP 604, PEP 612, PEP 695 (the upstream Python language standards this rule projects).
- **Gated by ←** ● The path-filter (17 glob patterns covering `*.py`, `pyproject.toml`, `setup.cfg`, `requirements*.txt`, `Pipfile`, `tox.ini`, `pytest.ini`, `conftest.py`, lint configs) — this rule activates only on Python-language artifact touches. ● `rules/cognitive-identity.md` Senior Software Architect role declaration. ● the trivial-vs-non-trivial threshold (trivial-scope Python edits run an abbreviated check covering M13.7 lint / format only).
- **Cross-bound with ↔** ↔ `rules/code-craft-conventions.md` (universal-delegation stub yields to this rule when the artifact's path matches; the universal floor M13.1–M13.11 is materialized here in Python idioms). ↔ `rules/code-craft-shell.md` + `rules/code-craft-markdown.md` (sibling per-language code-craft rules; consistent body shape across the trio). ↔ `rules/clean-architecture-layers.md` (Python materializes the layer discipline through `Protocol` / `ABC` choice + composition-root patterns; §1 DIP cross-references that rule's §2.3). ↔ `rules/cognitive-identity.md` (the Senior Software Architect role's Python-language manifestation). ↔ `rules/clean-room-generation.md` (Python code emission passes the Writing Protocol §2 + Code Generation §4 before this rule's path-filtered guardrails apply). ↔ `rules/operational-mandates.md` §CM-28 (the inline registry entry that delegates here). ↔ `rules/performance-discipline.md` §1.1 (the per-class performance budgets apply to Python artifacts under this rule's path-filter). ↔ `rules/refactoring-discipline.md` (the per-language quality bar a refactor's deficiency-elevation targets). ↔ `rules/host-discovery-manifests.md` (↔ reciprocal of the peer's Cross-bound citation). ↔ `rules/pre-emission-gate.md` (↔ reciprocal of the peer's Cross-bound citation). ↔ `rules/pre-emission-gate-bars.md` (this rule is among the M-rules named in the gate's "Failure → action" column; the bar-level catalog cross-binds each). ↔ `rules/production-ready-prs.md` (↔ reciprocal of the peer's Cross-bound citation). ↔ `rules/surgical-manipulation.md` (scoped, atomic refactoring is the per-language form of surgical mutation). ↔ `rules/ten-dimension-check.md` (per-dimension materialization for code). ↔ `rules/ten-dimension-check-dimensions.md` (↔ reciprocal of the peer's Cross-bound citation).
