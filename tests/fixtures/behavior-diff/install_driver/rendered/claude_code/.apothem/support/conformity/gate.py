# SPDX-License-Identifier: MIT

"""Conformity-gate orchestrator: dispatches every grep against a Write/Edit input.

Why this orchestrator exists. The pre-emission gate's mechanical fraction
is a corpus of per-class greps; the orchestrator is the single dispatch
surface the harness invokes per `PreToolUse` Write/Edit hook. The
orchestrator reads the tool-input JSON from stdin, extracts the content
and target path, runs every grep's `check()` callable in sequence, and
aggregates findings into a single structured report. The gate is
advisory by default: it emits the consolidated report plus a per-finding
summary (so findings are never silent) and exits zero, letting the write
proceed. Strict mode is opt-in — with the ``--strict`` flag or a truthy
``APOTHEM_CONFORMITY_STRICT`` environment variable, a non-empty findings
list exits non-zero so the harness or CI blocks the action.

Performance budget. The hook's wall-clock ceiling is the 10s PreToolUse
limit per `rules/performance-discipline.md` §1, less the
PowerShell bootstrap stub's ~1500ms and the interpreter-locator's
~200ms; the cumulative grep budget is ~8300ms. Per-grep budget is the
``PER_GREP_BUDGET_SECONDS`` constant (~520ms), applied across the registered
per-Write greps (``len(GREP_MODULES)``) so the figure tracks the live registry
rather than a hardcoded count. The orchestrator times every grep and reports any
that approached the per-grep ceiling so future tuning can target the slow path.

Per-file vs per-staged-diff dispatch. Most greps run on the content
plus path. The production-ready-pr grep operates at change-set
granularity rather than per-file; in the per-Write dispatch path it
returns clean. The CLI-mode `--staged` flag invokes the substantive
staged-diff check.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import importlib.util
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final, Protocol, cast

# Plain-script bootstrap. Harness deployments invoke this file by absolute
# path (``${PYTHON_BIN} <ROOT>/.apothem/support/conformity/gate.py --hook``),
# which puts only this directory on ``sys.path``, so the ``apothem`` package is
# not importable and the first ``apothem.*`` import below would fail. The file
# runs from one of two layouts, told apart by its grandparent directory:
#
#   - Package layout: ``<parent>/apothem/conformity/gate.py`` (a repository
#     checkout's ``src/``, an installed package, a plugin tree). Prepend
#     ``<parent>`` and the vendored-dependency tree; the vendor entry is
#     prepended last so bundled dependency versions win the resolution race,
#     per the self-containment invariant in ``apothem/lib/plugin_bootstrap.py``.
#   - Harness support layout: ``<harness>/.apothem/support/conformity/gate.py``.
#     ``support/`` mirrors the package subtrees an install ships (``conformity/``,
#     ``hooks/``, ``schemas/``, ``templates/``) but is not named ``apothem``, so
#     no ``sys.path`` entry can expose it under that name. Register ``support/``
#     as the ``apothem`` package instead, so ``apothem.conformity.*`` resolves to
#     the sibling modules installed with this file (version-matched to it).
#
# This bootstrap MUST run before the first ``apothem.*`` import below — moving
# that import above this block reintroduces the ModuleNotFoundError the block
# exists to prevent. The standalone-validator launcher reuses it by running this
# file as a plain script before each validator.
if __package__ in (None, ""):
    _PACKAGE_DIR: Final[Path] = Path(__file__).resolve().parents[1]
    if _PACKAGE_DIR.name == "apothem" and (_PACKAGE_DIR / "__init__.py").is_file():
        for _entry in (str(_PACKAGE_DIR.parent), str(_PACKAGE_DIR / "_vendor")):
            if _entry not in sys.path:
                sys.path.insert(0, _entry)
    elif "apothem" not in sys.modules:
        import types

        _support_package = types.ModuleType(
            "apothem", "Harness support tree exposed as the apothem package."
        )
        _support_package.__path__ = [str(_PACKAGE_DIR)]
        sys.modules["apothem"] = _support_package

from apothem.conformity._grep_base import (
    EMPTY_SCOPE_KEY,
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_USAGE,
    INSPECTED_KEY,
    STDIN_FLAG,
    make_parser,
    read_path_arguments,
)

# Environment variable that overrides the default conformity-gate scopes.
# When set, the gate's --hook mode runs the matcher chain only on writes
# whose target path falls under this directory; out-of-scope writes
# short-circuit to a silent pass-through.
SCOPE_ENV_VAR: Final[str] = "APOTHEM_CONFORMITY_SCOPE"

# Hooks-wide kill switch, shared with hooks/dispatch.py. The engine install
# registers this gate's --hook mode beside the dispatcher-routed hooks, so a
# truthy value silences it too and an operator troubleshooting hooks turns
# every Apothem hook off with one variable.
HOOKS_DISABLE_ENV: Final[str] = "APOTHEM_HOOKS_DISABLE"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})


def _hooks_disabled() -> bool:
    """Return True when ``APOTHEM_HOOKS_DISABLE`` holds a truthy value."""
    return os.environ.get(HOOKS_DISABLE_ENV, "").strip().lower() in _TRUTHY


# Default scopes when APOTHEM_CONFORMITY_SCOPE is unset. Hook-capable
# user-scope harness roots are matcher-applicable territories; writes
# outside them are pass-through.
_DEFAULT_CLAUDE_SCOPE: Final[Path] = Path.home() / ".claude"


def _default_scopes() -> tuple[Path, ...]:
    """Return the default user-scope hook-capable harness roots."""
    codex_home = os.environ.get("CODEX_HOME")
    codex_scope = (
        Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    )
    return (_DEFAULT_CLAUDE_SCOPE, codex_scope)


def _resolve_scope() -> Path:
    """Return the first configured conformity-gate scope as an absolute Path.

    Kept for compatibility with tests and callers that inspect the legacy
    single-scope helper. Hook dispatch uses :func:`_resolve_scopes`.
    """
    return _resolve_scopes()[0]


def _resolve_scopes() -> tuple[Path, ...]:
    """Return the configured conformity-gate scopes as absolute Paths.

    Resolution order: ``APOTHEM_CONFORMITY_SCOPE`` env var > the default
    user-scope hook-capable harness roots. Returned paths are resolved
    (symlinks followed; relative components collapsed) so in-scope
    comparisons work against absolute canonical forms.
    """
    override = os.environ.get(SCOPE_ENV_VAR)
    if override:
        return (Path(override).expanduser().resolve(),)
    return tuple(scope.expanduser().resolve() for scope in _default_scopes())


def _path_in_scope(target: Path | None, scope: Path) -> bool:
    """Return True when *target* lives under *scope*.

    Resolves *target* to its absolute canonical form, then walks up its
    parent chain looking for *scope*. When *target* is None (no write
    target supplied — e.g., a CLI mode invocation), returns True so the
    matchers run as today; the short-circuit fires only on hook-mode
    invocations with a resolvable out-of-scope target.
    """
    if target is None:
        return True
    try:
        resolved = target.expanduser().resolve()
    except (OSError, RuntimeError):
        # Fail-closed-but-permissive: if path resolution fails, keep
        # matchers running so the gate does not silently drop writes
        # whose targets are simply unusual but in-scope.
        return True
    try:
        resolved.relative_to(scope)
    except ValueError:
        return False
    return True


def _path_in_any_scope(target: Path | None, scopes: tuple[Path, ...]) -> bool:
    """Return True when *target* lives under any configured scope."""
    return any(_path_in_scope(target, scope) for scope in scopes)


def scope_relative_path(target: Path) -> tuple[Path, Path] | None:
    """Return ``(scope_root, path-relative-to-scope)`` for *target*'s scope.

    Tries each configured conformity scope (``APOTHEM_CONFORMITY_SCOPE`` or the
    default hook-capable harness roots) in resolution order and returns the
    first that contains *target*, with *target* rendered relative to it. Returns
    ``None`` when *target* is under no configured scope. This is the shared seam
    the per-Write matchers use to evaluate a hook-scoped write (e.g.
    ``~/.claude/rules/x.md``) against the same notion of "in scope" the gate
    uses — so a matcher and the gate agree, and a write outside the apothem repo
    root is still checked relative to the harness root it landed under.
    """
    try:
        resolved = target.expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    for scope in _resolve_scopes():
        try:
            return scope, resolved.relative_to(scope)
        except ValueError:
            continue
    return None


# Harness runtime-state subtrees. Under each hook-capable harness root, these
# top-level subtrees hold the harness's OWN operator-facing state, NOT
# apothem-managed config:
#   - ``projects/<hash>/`` --- per-project state: project-scoped auto-memory
#     (``memory/MEMORY.md`` plus topic files), session transcripts, todo lists.
#   - ``memory/`` --- the global (cross-project) auto-memory tier.
# Both are owned by the operator and the harness; apothem never materializes or
# manages them (apothem's managed config lives in sibling subtrees: ``rules/``,
# ``skills/``, ``agents/``, ``commands/``, ``hooks/``, ``output-styles/``,
# ``statuslines/``, ``settings.json``). The hook exempts these subtrees so
# per-Write dispatch does not block the operator's memory writes --- a
# ``MEMORY.md`` index is provenance-less and frontmatter-less by the auto-memory
# convention and would otherwise fail-close on ``orphan-output-grep`` /
# ``frontmatter-grep``.
_HARNESS_STATE_SEGMENTS: Final[frozenset[str]] = frozenset({"projects", "memory"})


def _is_harness_state_path(target: Path | None, scopes: tuple[Path, ...]) -> bool:
    """Return True iff *target* sits under a scope's harness runtime-state subtree.

    The check is scope-coupled: it fires only when *target* resolves under a
    configured harness-config root AND the first path component below that root
    is one of ``_HARNESS_STATE_SEGMENTS`` (``projects`` / ``memory``). A
    coincidental ``projects/`` or ``memory/`` directory in an unrelated
    workspace is not exempted because that workspace is not a configured scope.
    Returns False for ``None`` targets and for paths that fail resolution.
    """
    if target is None:
        return False
    try:
        resolved = target.expanduser().resolve()
    except (OSError, RuntimeError):
        return False
    for scope in scopes:
        try:
            relative = resolved.relative_to(scope)
        except ValueError:
            continue
        if relative.parts and relative.parts[0] in _HARNESS_STATE_SEGMENTS:
            return True
    return False


class _CheckCallable(Protocol):
    """Shape of every grep module's `check()` callable."""

    def __call__(
        self,
        content: str,
        path: Path | None = None,
    ) -> Any:  # noqa: ANN401  # GrepResult instances are duck-typed across modules.
        """Scan *content* and return that module's result dataclass.

        Pre-conditions: ``content`` is the artifact body; ``path`` is its
        location, or ``None`` when the body arrived over stdin and no path
        context is available. Post-conditions: the return carries at least
        ``passed`` and ``findings``; its concrete type varies per module, which
        is why the annotation stays ``Any``.
        """
        ...


# Per-grep dispatch order. The order is intentional: the cheap structural
# scans (placeholder + arrow notation) run first; the more expensive
# regex sweeps and the entropy heuristic run later. The dispatch order
# does not affect the final verdict (every grep is run regardless).
GREP_MODULES: Final[tuple[str, ...]] = (
    "user_confirm_grep",
    "binding_reciprocity_grep",
    "option_annotation_grep",
    "completion_claim_grep",
    "hedging_grep",
    "brand_mark_grep",
    "diagram_staleness_grep",
    "unpinned_action_grep",
    "bare_except_grep",
    "magic_number_grep",
    "orphan_output_grep",
    "commented_out_code_grep",
    "secret_leak_grep",
    "production_ready_pr_grep",
    "file_header_grep",
    "copilot_instructions_presence_grep",
    "multi_surface_coherence_grep",
    "license_author_consistency_grep",
    "frontmatter_grep",
    "link_check",
    "always_on_budget_grep",
    "token_efficiency_grep",
    # `semver_stability_grep` is change-set-scoped (operates on the git diff
    # between staged + HEAD), not per-Write, so it is NOT in the per-Write
    # registry. Invoke at change-set boundary via
    # `python -m apothem.conformity.semver_stability_grep --staged`.
)

# Corpus-level standalone validators. These do NOT fit the per-Write
# `check(content, path)` signature — they walk the working tree, the
# git index, or a fixed surface set. They are invoked via subprocess
# in --all mode and exposed via --check <name> and --list. Each script
# accepts a root directory as its sole argument and exits 0 (PASS) or
# non-zero (FAIL).
STANDALONE_MODULES: Final[tuple[str, ...]] = (
    "naming-grep",
    "smoke-install-grep",
    "no-global-plans-grep",
    "plan-suite-structure-grep",
    "no-toplevel-docs-grep",
    "plans-discipline-language-grep",
    "plain-language-grep",
    "reference-token-grep",
    "freshness-token-grep",
    "agnosticism-grep",
    "agent-capability-grep",
    "frontmatter-value-grep",
    "static-version-grep",
    "dynamism-grep",
    "recommend-next-step-grep",
    "plan-next-step-consistency-grep",
    "redundancy-grep",
    "conventional-commit-grep",
    "gitattributes-presence-grep",
    "editorconfig-presence-grep",
    "permissions-minimum-scope-grep",
    "cross-platform-matrix-grep",
    "harden-runner-grep",
    "oidc-trusted-publishing-grep",
    "workflow-concurrency-grep",
    "determinism-grep",
    "agents-md-coverage-grep",
    "registry-capability-consistency-grep",
    "binding-reciprocity-corpus-grep",
    "binding-five-direction-grep",
)

# Per-grep wall-clock budget in seconds. Exceeding the budget surfaces
# as a watch item in the report but does not block the write — the hook
# has its own 10s ceiling and the orchestrator avoids hard-killing a
# grep mid-scan.
PER_GREP_BUDGET_SECONDS: Final[float] = 0.520

# Maximum per-matcher flagged-file sample carried in the ``--all-perwrite``
# payload. ``file_count`` is the full tally; ``files`` is a bounded sample and
# the report's ``files_truncated`` flag says whether the sample is partial.
_PERWRITE_FILE_SAMPLE_CAP: Final[int] = 10

# Where the grep modules live. The orchestrator resolves them relative
# to its own location so the hook works regardless of the operator's
# current working directory and of the layout the package is mounted in
# (repo checkout ``src/apothem/conformity/`` or installed
# ``<install-root>/apothem/conformity/`` — the modules and their
# ``schemas/`` sibling travel together in both shapes).
TOOLS_DIR: Final[Path] = Path(__file__).resolve().parent

# EXIT_PASS / EXIT_FAIL / EXIT_USAGE are imported from ``_grep_base`` (single
# source with every matcher). EXIT_FAIL (2) is the strict-mode findings-blocked
# code; a CLI-usage error carries the distinct EXIT_USAGE (3) so a CI consumer
# can tell "the gate blocked on findings" apart from "the gate was invoked
# wrong" (an unknown flag or validator name, a missing file or root).
CHECK_FLAG: Final[str] = "--check"
LIST_FLAG: Final[str] = "--list"
ALL_FLAG: Final[str] = "--all"
ALL_PERWRITE_FLAG: Final[str] = "--all-perwrite"
HOOK_FLAG: Final[str] = "--hook"
STRICT_FLAG: Final[str] = "--strict"
PROG: Final[str] = "conformity-gate"
STRICT_ENV: Final[str] = "APOTHEM_CONFORMITY_STRICT"
_STRICT_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})

# --- Corpus per-Write runner: blocking vs advisory classification -----------
#
# The ``--all-perwrite`` mode routes every git-tracked file through every
# per-Write matcher in ``GREP_MODULES`` (the corpus counterpart to the
# harness's per-write hook dispatch). Per the advisory-by-default enforcement
# posture ratified at ``rules/pre-emission-gate.md`` (the fifteen-bar gate
# anchor that owns this ``conformity/gate.py`` orchestrator), each matcher is
# classified into exactly one of two disjoint sets:
#
#   - BLOCKING (``_BLOCKING_PER_WRITE_GREPS``): deterministic, low-false-
#     positive matchers that are GREEN over the live tracked corpus today.
#     A finding from one of these under ``--strict`` fails the corpus run.
#     The posture's governing principle: a matcher is blocking ONLY once it
#     is green over the tracked corpus — never blocking-AND-failing.
#
#   - ADVISORY (``_ADVISORY_PER_WRITE_GREPS``): matchers whose findings are
#     reported (so the drift is never silent) but do NOT gate, because they
#     are high-false-positive against the shipped prose / code / config /
#     docs corpus today. Each carries a one-line note in ``_ADVISORY_RATIONALE``
#     naming the work that would let it gate, so the classification is visible
#     and testable. ``hedging`` stays advisory until the shipped rule and doc
#     prose is rewritten; the remaining advisory
#     members are matchers whose own ``check()`` fires structurally against
#     legitimate non-target content the corpus enumerates (lockfile entropy,
#     frontmatter-first Markdown, design-token literals, documented pattern
#     references), not against a genuine defect a fix could clear here.
#
# The two sets PARTITION ``GREP_MODULES`` — every per-Write matcher is in
# exactly one, verified by ``_assert_perwrite_partition`` at import time so a
# matcher can never be silently left out of (or in both of) the classification.

_BLOCKING_PER_WRITE_GREPS: Final[frozenset[str]] = frozenset(
    {
        "binding_reciprocity_grep",
        "option_annotation_grep",
        "completion_claim_grep",
        "unpinned_action_grep",
    }
)

# Advisory rationale: matcher name -> (reason, remediation). The reason names
# WHY the matcher is high-false-positive in corpus mode; the remediation names
# the work that, once done, lets the matcher join the blocking set. Both ship in
# the ``--all-perwrite`` report (``reason`` / ``remediation_owner``).
_ADVISORY_RATIONALE: Final[dict[str, tuple[str, str]]] = {
    "bare_except_grep": (
        "the bare `except:` sub-rule (always a real defect) is GREEN over the "
        "tree; the broad `except Exception:`-without-raise sub-heuristic fires "
        "on deliberate, `# noqa: BLE001`-marked fail-open isolation boundaries "
        "(dispatch / gate / statusline / hook) that ruff's BLE001 rule already "
        "governs and `ruff check` already gates in CI",
        "ruff BLE001 already gates the broad form in CI; teach the matcher the "
        "`# noqa: BLE001` intent marker",
    ),
    "user_confirm_grep": (
        "fires on prose / commands / matcher source that DOCUMENT the "
        "<USER-CONFIRM:id=...> placeholder syntax, not on unresolved "
        "placeholders",
        "skip placeholders quoted in code spans and in matcher source",
    ),
    "hedging_grep": (
        "hedging vocabulary trips a portion of the shipped rule / doc bodies "
        "until that prose is rewritten",
        "rewrite the hedged rule and doc prose",
    ),
    "brand_mark_grep": (
        "fires on harness brand slugs (Cursor, Codex, ...) in config / "
        "workflow / catalog files where the slug is a load-bearing catalog "
        "entry, not a privileging brand reference",
        "tell catalog entries apart from brand references in config and catalog files",
    ),
    "diagram_staleness_grep": (
        "date-comparison heuristic flags shipped docs diagrams whose verified "
        "date predates a sibling edit; staleness reconcile is doc-rewrite work",
        "re-verify the flagged docs diagrams and refresh their verified dates",
    ),
    "magic_number_grep": (
        "fires on CSS design-token values, version pins, and rebuild-script "
        "asset dimensions that are values in a data context, not logic literals",
        "exempt data contexts (design tokens, version pins, asset dimensions)",
    ),
    "orphan_output_grep": (
        "orphan-output is a multi-step-work-session concept; in corpus mode it "
        "fires on standalone config / data files that carry no provenance "
        "frontmatter by their own ratified convention",
        "scope the matcher to multi-step work outputs instead of every file",
    ),
    "commented_out_code_grep": (
        "fires on YAML / TOML comment blocks and shell here-doc bodies that "
        "resemble commented-out code but are deliberate inline documentation",
        "exempt documentation comments in YAML, TOML, and shell here-docs",
    ),
    "secret_leak_grep": (
        "entropy heuristic fires on package-lock.json integrity hashes and "
        "high-entropy doc tokens (harness slugs, base64-looking examples), and "
        "the literal-shape heuristic fires on test fixtures that DELIBERATELY "
        "embed fake credentials to exercise the detector under test; no genuine "
        "secret among the corpus findings",
        "exempt lockfile integrity hashes and the detector's own test fixtures",
    ),
    "production_ready_pr_grep": (
        "change-set-scoped matcher; returns clean per-file by design, so it "
        "carries no corpus verdict and is non-gating in per-file corpus mode",
        "n/a (change-set granularity, not per-file)",
    ),
    "file_header_grep": (
        "the per-Write insertion-at-index-0 logic does not model the "
        "frontmatter-first Markdown class (rules / agents / commands / docs / "
        "AGENTS.md) that is the dominant ratified head convention across the "
        "shipped tree; the genuine code-surface gaps are fixed in source",
        "model the frontmatter-first Markdown head convention in the matcher",
    ),
    "copilot_instructions_presence_grep": (
        "single-target surface matcher (.github/copilot-instructions.md); in "
        "corpus mode it returns clean for every non-target file, carrying no "
        "corpus verdict",
        "n/a (single-surface presence check)",
    ),
    "multi_surface_coherence_grep": (
        "cross-surface coherence matcher scoped to the AGENTS.md / CLAUDE.md / "
        "copilot triad; non-target files carry no corpus verdict",
        "n/a (cross-surface coherence check)",
    ),
    "license_author_consistency_grep": (
        "scoped to the LICENSE consistency surface; non-target files carry no "
        "corpus verdict",
        "n/a (single-surface consistency check)",
    ),
    "frontmatter_grep": (
        "class-inference heuristic fires on .mdx / .tsx components and docs content "
        "whose frontmatter contract differs from the rule / skill / agent "
        "schema it infers",
        "infer the frontmatter contract per artifact class, docs and site "
        "components included",
    ),
    "link_check": (
        "link reachability / resolution is inherently high-false-positive over "
        "the corpus (relative-link base ambiguity, external-host flakiness)",
        "resolve relative links against the right base; stop probing external "
        "hosts in corpus mode",
    ),
    "always_on_budget_grep": (
        "surfaces always-on rule bodies over the substantive-token ceiling; "
        "remediation is a rule-body decomposition, not a matcher change",
        "decompose an over-budget always-on rule into a path-filtered companion",
    ),
    "token_efficiency_grep": (
        "filler / qualifier prose heuristic in the same prose-debt class as "
        "hedging; high-false-positive against shipped rule / doc bodies",
        "rewrite the filler and qualifier prose in rule and doc bodies",
    ),
}

_ADVISORY_PER_WRITE_GREPS: Final[frozenset[str]] = frozenset(_ADVISORY_RATIONALE)


def _assert_perwrite_partition() -> None:
    """Verify BLOCKING and ADVISORY partition ``GREP_MODULES`` exactly.

    Raised at import time so a newly-registered per-Write matcher cannot be
    silently left unclassified (it would fall through corpus mode with no
    blocking / advisory verdict) or double-classified (blocking AND advisory).
    """
    classified = _BLOCKING_PER_WRITE_GREPS | _ADVISORY_PER_WRITE_GREPS
    overlap = _BLOCKING_PER_WRITE_GREPS & _ADVISORY_PER_WRITE_GREPS
    if overlap:
        raise RuntimeError(
            f"per-Write matcher(s) classified BOTH blocking and advisory: "
            f"{sorted(overlap)}"
        )
    registry = set(GREP_MODULES)
    missing = registry - classified
    extra = classified - registry
    if missing:
        raise RuntimeError(
            f"per-Write matcher(s) unclassified for corpus mode: {sorted(missing)}"
        )
    if extra:
        raise RuntimeError(
            f"corpus classification names matcher(s) absent from GREP_MODULES: "
            f"{sorted(extra)}"
        )


_assert_perwrite_partition()

# Per-suffix applicability for matchers whose RULE is suffix-scoped but whose
# own ``check()`` does not gate by file type. Each named matcher inspects only
# files whose suffix is in its set; a file of any other type is skipped for
# that matcher (so a Markdown file is never bare-except-scanned, an arbitrary
# file is never workflow-action-scanned). Matchers absent from this map self-
# gate inside their own ``check()`` (e.g. magic-number / commented-out-code /
# file-header by variant family) or are content-type-agnostic prose matchers.
_PER_SUFFIX_APPLICABILITY: Final[dict[str, frozenset[str]]] = {
    # M13.3 error handling is a Python rule; `except:` is Python syntax.
    "bare_except_grep": frozenset({".py", ".pyi"}),
    # GitHub Actions pinning applies to workflow YAML only.
    "unpinned_action_grep": frozenset({".yml", ".yaml"}),
}

# File suffixes whose bytes are opaque to the text matchers; the corpus runner
# skips them entirely (it cannot decode them as UTF-8 text). Mirrors the binary
# extension exemptions at schemas/header-exceptions.txt.
_CORPUS_BINARY_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".webp",
        ".svg",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".7z",
        ".rar",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".pyc",
        ".pyo",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".mp3",
        ".mp4",
        ".webm",
        ".mov",
        ".avi",
    }
)


@dataclass(frozen=True)
class GrepInvocation:
    """One grep's result plus its wall-clock timing.

    ``error`` is non-None only when the matcher's load or ``check()`` raised;
    such an invocation is recorded ``passed=True`` (fail-open isolation) so one
    matcher's internal bug never fail-closes the operator's write, while the
    error text is preserved in the report for diagnosis rather than swallowed.
    """

    grep: str
    passed: bool
    findings: list[dict[str, object]]
    elapsed_seconds: float
    over_budget: bool
    error: str | None = None


@dataclass(frozen=True)
class OrchestratorReport:
    """Aggregate result of one conformity-gate run.

    Carries the overall pass verdict, the scanned path (``None`` in
    corpus mode), the grep / pass / fail counts, and the per-grep
    :class:`GrepInvocation` records.
    """

    passed: bool
    path: str | None
    grep_count: int
    pass_count: int
    fail_count: int
    invocations: list[GrepInvocation] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize the report as indented JSON under the
        ``conformity-gate`` orchestrator envelope."""
        payload = {
            "orchestrator": "conformity-gate",
            "passed": self.passed,
            "path": self.path,
            "grep_count": self.grep_count,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "invocations": [asdict(i) for i in self.invocations],
        }
        return json.dumps(payload, indent=2)


@functools.cache
def _load_check(module_name: str) -> _CheckCallable:
    """Load `module_name.check` via importlib (memoized per module name).

    Memoization is load-bearing for the corpus and per-file dispatch cost:
    ``run_orchestrator`` runs every matcher for a single write, and
    ``_run_all_perwrite`` runs every matcher against every tracked file, so an
    un-memoized loader re-executes each matcher module once per (file, matcher)
    pair. ``functools.cache`` keys on ``module_name`` so each matcher module is
    imported and its ``check`` callable resolved exactly once per process; the
    key is a plain hashable string and the loaded module is immutable state, so
    the cache is safe to share across every dispatch.

    Why the sys.modules registration matters: Python's dataclasses decorator
    inspects `sys.modules.get(cls.__module__)` at class-creation time to
    resolve forward-referenced KW_ONLY sentinels. Without registering the
    module under its qualified name before `exec_module()`, the lookup
    returns None and the decorator raises AttributeError on Python 3.14+.
    """
    module_path = TOOLS_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load grep module at {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    check = getattr(module, "check", None)
    if not callable(check):
        raise RuntimeError(f"grep module {module_name} exposes no check() callable")
    return check  # type: ignore[no-any-return]


def _findings_as_dicts(result: object) -> list[dict[str, object]]:
    """Extract the findings list from a GrepResult-shaped object."""
    findings = getattr(result, "findings", []) or []
    return [
        asdict(f) if hasattr(f, "__dataclass_fields__") else dict(f) for f in findings
    ]


def _is_plan_suite_path(path: Path | None) -> bool:
    """Return True iff path is under the canonical project-local plans subtree.

    The sole canonical project-local plans location is ``.apothem/plans/`` (the
    shared Apothem working directory's plans child); a legacy ``.plans/`` tree
    is no longer canonical — operators upgrade it via ``apothem
    migrate-workspace``.

    Plan-suite artifacts are gitignored ephemera per the ``.apothem/plans/**``
    class enumerated at ``schemas/header-exceptions.txt`` (the schemas directory
    shipped beside this package in both the repo-checkout and installed
    layouts) and exempt from the
    codebase quality bar (M13 code-craft, M15 production-ready). The
    orchestrator short-circuits on plan-suite paths so the per-Write hook
    does not block plan-suite emissions whose Markdown enumerations (dates,
    version identifiers, phase identifiers, kebab-case directory paths)
    fire structural false positives on matchers designed for codebase
    content.

    Per-Write narrow-routing (G1) --- DISCLOSED-DEFERRED. A narrower posture
    would route plans writes through a small per-Write matcher subset
    instead of a blanket synthetic PASS. It is deferred because the only
    per-Write matcher whose rule governs plans-suite structure
    (``orphan_output_grep``) fires "provenance absent" on legitimate
    ``_inputs/`` scratch files (e.g. a ``prose.txt`` or a frontmatter-less
    working note) --- exactly the volatile, session-local scratch tier the
    closed-vocabulary rule declares exempt from the codebase quality bar.
    Routing per-Write writes through it would flood pre-existing findings on
    conformant scratch and invert the advisory posture. The structural
    invariants (suite-locality, closed vocabularies, numeric-prefix
    discipline, phase coherence) are instead enforced at the CORRECT
    granularity by the directory-walking ``plan-suite-structure-grep``
    standalone validator, which runs over the whole tree in ``--all`` repo
    sweeps (CI + pre-commit). A directory-walker is the right shape for
    suite-structure invariants; the per-Write content matcher is not. When a
    per-Write plans matcher whose rule genuinely governs scratch-tier
    content lands, this short-circuit can be narrowed reversibly.
    """
    if path is None:
        return False
    parts = path.parts
    # The sole canonical project-local plans home is ``.apothem/plans`` (the
    # shared Apothem working directory's plans child). Match the two-segment
    # adjacency, never a lone ``.apothem`` part — ``.apothem`` also holds
    # operator memory/learning/contexts data, which is NOT plan-suite content.
    return any(
        parts[i] == ".apothem" and parts[i + 1] == "plans"
        for i in range(len(parts) - 1)
    )


def run_orchestrator(
    content: str,
    path: Path | None,
    only: str | None = None,
) -> OrchestratorReport:
    """Run every grep; aggregate the results into a single report.

    When ``only`` names a single grep module (e.g., ``"file-header-grep"``
    or its short form ``"file-header"``), the orchestrator runs only that
    module. The short form drops the trailing ``-grep`` suffix.

    Plan-suite paths short-circuit to a synthetic PASS per
    ``_is_plan_suite_path`` --- see that helper's docstring for the rationale.
    The short-circuit applies regardless of ``only`` so per-grep CLI
    invocations on plan-suite paths also pass cleanly.
    """
    if _is_plan_suite_path(path):
        return OrchestratorReport(
            passed=True,
            path=str(path),
            grep_count=0,
            pass_count=0,
            fail_count=0,
            invocations=[],
        )
    if only is not None:
        candidates = (only, f"{only}-grep")
        modules = tuple(m for m in GREP_MODULES if m in candidates)
        if not modules:
            raise ValueError(f"unknown grep: {only!r}")
    else:
        modules = GREP_MODULES
    invocations: list[GrepInvocation] = []
    for module_name in modules:
        start = time.perf_counter()
        error: str | None = None
        result: object = None
        try:
            check = _load_check(module_name)
            result = check(content, path)
        except Exception as exc:  # noqa: BLE001, RUF100 - fail-open isolation boundary: one matcher's internal error (load failure or check() raise) must never fail-close the operator's write; the error is recorded on the invocation and surfaced, not swallowed silently
            error = f"{type(exc).__name__}: {exc}"
        elapsed = round(time.perf_counter() - start, 4)
        if error is not None:
            invocations.append(
                GrepInvocation(
                    grep=module_name,
                    passed=True,
                    findings=[],
                    elapsed_seconds=elapsed,
                    over_budget=False,
                    error=error,
                )
            )
        else:
            invocations.append(
                GrepInvocation(
                    grep=module_name,
                    passed=bool(getattr(result, "passed", False)),
                    findings=_findings_as_dicts(result),
                    elapsed_seconds=elapsed,
                    over_budget=elapsed > PER_GREP_BUDGET_SECONDS,
                )
            )
    pass_count = sum(1 for i in invocations if i.passed)
    fail_count = len(invocations) - pass_count
    return OrchestratorReport(
        passed=fail_count == 0,
        path=str(path) if path is not None else None,
        grep_count=len(invocations),
        pass_count=pass_count,
        fail_count=fail_count,
        invocations=invocations,
    )


_POSITION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "line",
        "lineno",
        "line_number",
        "start_line",
        "end_line",
        "column",
        "col",
        "pos",
        "position",
        "range",
        "occurrences",
        "context",
    }
)


def _read_tool_input_from_stdin() -> tuple[str, Path | None, str | None]:
    """Parse the harness tool-input JSON; extract post / path / pre."""
    raw = sys.stdin.read()
    if not raw.strip():
        return "", None, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw, None, None
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return raw, None, None
    file_path_raw = tool_input.get("file_path")
    path = (
        Path(file_path_raw)
        if isinstance(file_path_raw, str) and file_path_raw
        else None
    )
    if "new_string" in tool_input and "old_string" in tool_input and path is not None:
        try:
            existing = path.read_text(encoding="utf-8")
            new_str = tool_input.get("new_string") or ""
            old_str = tool_input.get("old_string") or ""
            replace_all = bool(tool_input.get("replace_all"))
            if old_str and old_str not in existing:
                # ``str.replace`` silently returns ``existing`` unchanged when
                # ``old_string`` is absent, so the reconstructed post-content
                # equals the pre-content and the diff report is vacuously clean.
                # Note the no-op on stderr so a stale / mismatched Edit payload
                # is diagnosable rather than silently passing as a clean write.
                sys.stderr.write(
                    "conformity-gate: Edit-payload reconstruction is a no-op — "
                    f"old_string not found in {path}; the differential report "
                    "reflects the unchanged file, not the intended edit\n"
                )
            if replace_all:
                content = existing.replace(old_str, new_str)
            else:
                content = existing.replace(old_str, new_str, 1)
            post = content if isinstance(content, str) else ""
            return post, path, existing
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            pass
    content = tool_input.get("content") or tool_input.get("new_string") or ""
    return content if isinstance(content, str) else "", path, None


def _finding_signature(finding: dict[str, object]) -> str:
    """Canonicalise a finding for pre / post equality, ignoring position."""
    canonical = {k: v for k, v in finding.items() if k not in _POSITION_KEYS}
    return json.dumps(canonical, sort_keys=True, default=str)


def _diff_invocations(
    pre: list[GrepInvocation], post: list[GrepInvocation]
) -> list[GrepInvocation]:
    """Return post invocations with pre-existing findings suppressed."""
    pre_by_matcher: dict[str, list[str]] = {}
    for inv in pre:
        pre_by_matcher.setdefault(inv.grep, []).extend(
            _finding_signature(f) for f in inv.findings
        )
    diffed = []
    for inv in post:
        bag = list(pre_by_matcher.get(inv.grep, ()))
        retained = []
        for finding in inv.findings:
            sig = _finding_signature(finding)
            if sig in bag:
                bag.remove(sig)
                continue
            retained.append(finding)
        diffed.append(
            GrepInvocation(
                grep=inv.grep,
                passed=not retained,
                findings=retained,
                elapsed_seconds=inv.elapsed_seconds,
                over_budget=inv.over_budget,
                error=inv.error,
            )
        )
    return diffed


def _orchestrator_diff_report(
    pre_content: str,
    post_content: str,
    path: Path | None,
    only: str | None,
) -> OrchestratorReport:
    """Run pre / post orchestrator passes; emit a differential report."""
    pre_report = run_orchestrator(pre_content, path, only=only)
    post_report = run_orchestrator(post_content, path, only=only)
    diffed = _diff_invocations(
        list(pre_report.invocations), list(post_report.invocations)
    )
    pass_count = sum(1 for inv in diffed if inv.passed)
    fail_count = len(diffed) - pass_count
    return OrchestratorReport(
        passed=fail_count == 0,
        path=post_report.path,
        grep_count=len(diffed),
        pass_count=pass_count,
        fail_count=fail_count,
        invocations=diffed,
    )


def _gate_exit(passed: bool, *, strict: bool) -> int:
    """Map a gate verdict to an exit code under the advisory-by-default posture.

    A clean run always exits ``EXIT_PASS``. A run with findings exits
    ``EXIT_PASS`` (advisory — the findings are reported, the action proceeds)
    unless strict mode is enabled, in which case it exits ``EXIT_FAIL``.
    """
    if passed:
        return EXIT_PASS
    return EXIT_FAIL if strict else EXIT_PASS


def advisory_findings_present(payload: dict[str, object]) -> bool:
    """Return the corpus / standalone payload's ``advisory_findings_present`` flag.

    Both ``--all`` (standalone validators) and ``--all-perwrite`` (per-Write
    corpus) emit this top-level boolean: True iff an advisory validator / matcher
    reported a finding. The flag is the load-bearing handle a consumer reads to
    surface advisory drift WITHOUT consulting the gating verdict; it is kept
    separate from ``passed`` precisely because advisory drift is non-gating.
    """
    return bool(payload.get("advisory_findings_present", False))


def _strict_exit_with_advisory(
    *,
    blocking_passed: bool,
    advisory_present: bool,
    strict: bool,
) -> int:
    """Map a corpus / standalone verdict to an exit code, advisory flag in hand.

    The advisory-by-default posture ratified at ``rules/pre-emission-gate.md``
    fixes the strict split: under ``--strict`` the BLOCKING verdict gates (a
    blocking finding exits non-zero), and ADVISORY drift is surfaced but
    **never gates** — a leaked reference-token / stale-AGENTS advisory does NOT
    fail the strict step. This helper makes ``advisory_present`` load-bearing by
    threading it through the strict decision explicitly: the gating exit code is
    derived from ``blocking_passed`` alone, while ``advisory_present`` is
    surfaced on stderr (so the drift is never silent) and intentionally does not
    alter the exit code. The choice is pinned by a test so promotion of any
    advisory member to gating is a deliberate, reviewed classification change,
    never an accidental flip of the strict step's behavior.
    """
    if strict and advisory_present:
        sys.stderr.write(
            "conformity-gate: advisory finding(s) present (non-gating per the "
            "advisory-by-default posture); surfaced for review, exit code "
            "unaffected\n"
        )
    return _gate_exit(blocking_passed, strict=strict)


def _resolve_validator(name: str) -> tuple[str, bool]:
    """Resolve a short or full validator name to its canonical form.

    Returns ``(canonical_name, is_standalone)`` or raises ``ValueError``
    when the name is unknown. The short form drops the trailing
    ``_grep`` suffix (e.g., ``file_header`` → ``file_header_grep``).
    Accepts both hyphenated and underscored forms from CLI input.
    """
    normalized = name.replace("-", "_")
    candidates = (normalized, f"{normalized}_grep")
    # Normalize each registry entry to the underscored form before the
    # membership test: GREP_MODULES entries are already underscored, but
    # STANDALONE_MODULES entries are stored hyphenated (CLI ergonomics) and
    # would never match the underscored *candidates* otherwise. The returned
    # canonical preserves each registry's stored form.
    for canonical in GREP_MODULES:
        if canonical.replace("-", "_") in candidates:
            return canonical, False
    for canonical in STANDALONE_MODULES:
        if canonical.replace("-", "_") in candidates:
            return canonical, True
    raise ValueError(f"unknown grep: {name!r}")


def _list_validators() -> str:
    """Return the JSON enumeration of every registered validator."""
    payload = {
        "orchestrator": "conformity-gate",
        "per_write_greps": list(GREP_MODULES),
        "standalone_validators": list(STANDALONE_MODULES),
        "total": len(GREP_MODULES) + len(STANDALONE_MODULES),
    }
    return json.dumps(payload, indent=2)


# Launcher for one standalone-validator subprocess. It first runs this gate
# file as a plain script, so the layout-aware bootstrap at the top of the file
# makes the ``apothem`` package importable the same way it does for the gate
# itself, then runs the validator module as ``__main__`` with the remaining
# arguments. A child process therefore resolves its imports without relying on
# the parent's ``PYTHONPATH`` or on an installed package.
_STANDALONE_LAUNCHER: Final[str] = (
    "import runpy, sys\n"
    "gate_path, module = sys.argv[1], sys.argv[2]\n"
    "sys.argv = [module, *sys.argv[3:]]\n"
    "runpy.run_path(gate_path, run_name='apothem_conformity_bootstrap')\n"
    "runpy.run_module('apothem.conformity.' + module, run_name='__main__',"
    " alter_sys=True)\n"
)


def _run_standalone(name: str, root: Path) -> tuple[bool, str]:
    """Invoke a standalone validator via subprocess; return (passed, output).

    The ``STANDALONE_MODULES`` names are hyphenated for CLI ergonomics
    (``naming-grep``), but the on-disk module filenames are underscored
    (``naming_grep.py``). Normalize the name to the underscored form
    before resolving the script path so ``--all`` and ``--check`` both
    locate the script regardless of which form the caller supplied. The
    validator runs through :data:`_STANDALONE_LAUNCHER` against *root*,
    which the caller has already resolved to an absolute directory.
    """
    module = name.replace("-", "_")
    script = TOOLS_DIR / f"{module}.py"
    if not script.exists():
        return False, f"{name}: script absent at {script}"
    try:
        completed = subprocess.run(  # noqa: S603 — trusted invocation: sys.executable + a constant launcher + this file's path + a validated STANDALONE_MODULES name
            [
                sys.executable,
                "-c",
                _STANDALONE_LAUNCHER,
                str(Path(__file__).resolve()),
                module,
                str(root),
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
        )
    except OSError as exc:
        return False, f"{name}: invocation failed: {exc}"
    output = completed.stdout or completed.stderr or ""
    return completed.returncode == EXIT_PASS, output


def _advisory_verdict(output: str) -> dict[str, object] | None:
    """Return an advisory validator's inner verdict from its JSON output.

    An advisory validator (one whose JSON declares ``advisory: true``) exits 0
    even when it has findings, so its subprocess exit code — the gate's
    per-validator ``passed`` field — stays green while its JSON reports
    ``passed: false``. This parses that JSON so the inner verdict can be
    propagated into the gate report; a consumer reading the per-validator
    result then sees the drift without parsing the embedded ``output`` string.

    Returns ``{"passed": bool, "findings": list}`` when the output is JSON
    declaring ``advisory: true``; otherwise None (the validator is not
    advisory, or its output is not parseable JSON).
    """
    try:
        payload = json.loads(output)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or not payload.get("advisory"):
        return None
    findings = payload.get("findings")
    return {
        "passed": bool(payload.get("passed", True)),
        "findings": findings if isinstance(findings, list) else [],
    }


def _inspection_fields(output: str) -> dict[str, object]:
    """Return a validator report's ``inspected`` / empty-scope fields, if any.

    Every standalone validator stamps ``inspected`` (how many targets it
    examined) on its JSON report, plus ``empty_scope_expected`` when it
    examined none. Lifting them into the ``--all`` result entry lets a consumer
    see a vacuous run without parsing each embedded ``output`` string.
    """
    try:
        payload = json.loads(output)
    except (json.JSONDecodeError, ValueError, TypeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        key: payload[key] for key in (INSPECTED_KEY, EMPTY_SCOPE_KEY) if key in payload
    }


def _run_all(root: Path) -> tuple[bool, str]:
    """Run every standalone validator; aggregate exit verdicts.

    Per-Write greps are NOT invoked in --all mode because they require
    file-content input from the harness's tool-input JSON. The harness
    itself runs them per-Write via the --hook dispatch path; --all is
    the corpus-level counterpart for CI / Makefile invocations.

    Advisory validators exit 0 even when they report findings, so the overall
    gate stays green; their inner verdict is surfaced per-validator as
    ``advisory`` / ``advisory_passed`` / ``findings`` and aggregated into the
    top-level ``advisory_findings_present`` flag so the drift is visible
    without parsing each validator's embedded ``output``.
    """
    results: list[dict[str, object]] = []
    overall_passed = True
    advisory_findings_present = False
    for name in STANDALONE_MODULES:
        passed, output = _run_standalone(name, root)
        if not passed:
            overall_passed = False
        entry: dict[str, object] = {
            "validator": name,
            "passed": passed,
            "output": output.strip(),
        }
        entry.update(_inspection_fields(output))
        verdict = _advisory_verdict(output)
        if verdict is not None:
            entry["advisory"] = True
            entry["advisory_passed"] = verdict["passed"]
            entry["findings"] = verdict["findings"]
            if not verdict["passed"]:
                advisory_findings_present = True
        results.append(entry)
    payload = {
        "orchestrator": "conformity-gate",
        "mode": "all",
        "root": str(root),
        "passed": overall_passed,
        "advisory_findings_present": advisory_findings_present,
        "validator_count": len(STANDALONE_MODULES),
        "results": results,
    }
    return overall_passed, json.dumps(payload, indent=2)


def _corpus_tracked_files(root: Path) -> list[Path]:
    """Return the git-tracked files under *root* as resolved absolute Paths.

    Uses ``git ls-files`` so the corpus is exactly the tracked working tree —
    ignored artifacts (``dist/``, caches, ``.plans/`` ephemera) are excluded by
    construction. The invocation is read-only. When git is unavailable or
    *root* is not a work tree, returns an empty list (the caller treats an
    empty corpus as a clean pass — there is nothing tracked to scan).
    """
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z"],  # noqa: S607 — read-only invocation; argv list (never shell); `git` resolved from PATH is the standard cross-platform invocation, mirroring the repo's other git subprocess call sites
            cwd=str(root),
            capture_output=True,
            check=False,
            encoding="utf-8",
        )
    except (OSError, ValueError):
        return []
    if completed.returncode != EXIT_PASS:
        return []
    rels = [entry for entry in completed.stdout.split("\0") if entry]
    return [(root / rel).resolve() for rel in rels]


def _is_corpus_fixture_path(path: Path) -> bool:
    """Return True for deliberately-malformed conformity-test fixture files.

    The ``tests/conformity/<matcher>/`` and ``tests/fixtures/`` trees carry
    ``fail.*`` / ``pass.*`` and other reference fixtures whose content is
    intentionally non-conformant (a planted violation a matcher's own unit test
    asserts on). Scanning them in corpus mode would surface those planted
    violations as corpus findings. They are exempt by the same principle the
    ``.plans/`` short-circuit applies: fixture data is not shipped codebase
    content held to the quality bar.
    """
    parts = path.parts
    if "tests" not in parts:
        return False
    tail = parts[parts.index("tests") + 1 :]
    return bool(tail) and tail[0] in {"conformity", "fixtures"}


def _matcher_applies_to(module_name: str, path: Path) -> bool:
    """Return True when *module_name* should inspect *path* in corpus mode.

    Honors the per-suffix applicability map for matchers whose rule is suffix-
    scoped but whose own ``check()`` does not gate by file type (so a Markdown
    file is never bare-except-scanned). Matchers absent from the map self-gate
    inside ``check()`` and are always invoked (they return clean for files
    their rule does not govern).
    """
    suffixes = _PER_SUFFIX_APPLICABILITY.get(module_name)
    if suffixes is None:
        return True
    return path.suffix.lower() in suffixes


def _run_all_perwrite(root: Path) -> tuple[bool, str]:
    """Run every per-Write matcher over the git-tracked corpus under *root*.

    The corpus counterpart to the harness's per-write hook dispatch: each
    tracked file is routed through every ``GREP_MODULES`` matcher with per-
    suffix applicability (``_matcher_applies_to``) and the same ``.plans/`` /
    fixture exemptions the per-write path honors. Findings aggregate per
    matcher and split into a blocking tally and an advisory tally per the
    ``_BLOCKING_PER_WRITE_GREPS`` / ``_ADVISORY_PER_WRITE_GREPS`` partition.

    Returns ``(blocking_clean, payload)`` where ``blocking_clean`` is True iff
    zero blocking matchers flagged a finding. Advisory findings are reported
    (so drift is never silent) but never affect ``blocking_clean``. A matcher
    result carrying a ``note`` (a matcher's "scope not resolvable" skip) is not a
    finding. The caller maps ``blocking_clean`` to an exit code under the
    advisory-by-default posture (``--strict`` makes a non-clean blocking run
    exit non-zero).
    """
    files = _corpus_tracked_files(root)
    # matcher -> {"finding_count": int, "file_count": int, "files": [rel, ...]}
    blocking: dict[str, dict[str, object]] = {}
    advisory: dict[str, dict[str, object]] = {}
    files_scanned = 0
    for abs_path in files:
        if abs_path.suffix.lower() in _CORPUS_BINARY_SUFFIXES:
            continue
        if _is_plan_suite_path(abs_path) or _is_corpus_fixture_path(abs_path):
            continue
        if "_vendor" in abs_path.parts or "node_modules" in abs_path.parts:
            # Vendored / third-party trees carry upstream conventions, not the
            # apothem quality bar — exempt per schemas/header-exceptions.txt
            # (`**/_vendor/**`, `**/node_modules/**`).
            continue
        try:
            content = abs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Undecodable-as-text tracked file (an unlisted binary suffix);
            # there is nothing for the text matchers to scan.
            continue
        files_scanned += 1
        try:
            rel = str(abs_path.relative_to(root))
        except ValueError:
            rel = str(abs_path)
        for module_name in GREP_MODULES:
            if not _matcher_applies_to(module_name, abs_path):
                continue
            try:
                result = _load_check(module_name)(content, abs_path)
            except Exception:  # noqa: S112, BLE001, RUF100 — fail-open isolation: one matcher's internal error (load failure or check() raise) must never fail-close the corpus run; the matcher contributes no finding for this file and the run proceeds, mirroring run_orchestrator's per-matcher isolation boundary (BLE001 is the intent marker; RUF100 self-suppresses because ruff's BLE family is not active)
                continue
            if getattr(result, "note", None) is not None:
                # A matcher's scope-not-resolvable skip — not a finding.
                continue
            findings = getattr(result, "findings", None) or []
            if not findings:
                continue
            bucket = blocking if module_name in _BLOCKING_PER_WRITE_GREPS else advisory
            entry = bucket.setdefault(
                module_name,
                {"finding_count": 0, "file_count": 0, "files": []},
            )
            entry["finding_count"] = cast(int, entry["finding_count"]) + len(findings)
            entry["file_count"] = cast(int, entry["file_count"]) + 1
            sample = entry["files"]
            if isinstance(sample, list) and len(sample) < _PERWRITE_FILE_SAMPLE_CAP:
                sample.append(rel)
    blocking_clean = not blocking
    blocking_results = [
        {
            "matcher": name,
            "finding_count": data["finding_count"],
            "file_count": data["file_count"],
            "files": data["files"],
            # ``files`` is a bounded sample (``_PERWRITE_FILE_SAMPLE_CAP``); the
            # flag tells a consumer the sample is partial so it does not read the
            # truncated list as the complete flagged-file set.
            "files_truncated": cast(int, data["file_count"])
            > _PERWRITE_FILE_SAMPLE_CAP,
        }
        for name, data in sorted(blocking.items())
    ]
    advisory_results = [
        {
            "matcher": name,
            "finding_count": advisory[name]["finding_count"] if name in advisory else 0,
            "file_count": advisory[name]["file_count"] if name in advisory else 0,
            "files": advisory[name]["files"] if name in advisory else [],
            "files_truncated": (
                cast(int, advisory[name]["file_count"]) > _PERWRITE_FILE_SAMPLE_CAP
                if name in advisory
                else False
            ),
            "reason": _ADVISORY_RATIONALE[name][0],
            "remediation_owner": _ADVISORY_RATIONALE[name][1],
        }
        for name in sorted(_ADVISORY_PER_WRITE_GREPS)
        if name in advisory
    ]
    payload = {
        "orchestrator": "conformity-gate",
        "mode": "all-perwrite",
        "root": str(root),
        "passed": blocking_clean,
        "files_scanned": files_scanned,
        "blocking_matcher_count": len(_BLOCKING_PER_WRITE_GREPS),
        "advisory_matcher_count": len(_ADVISORY_PER_WRITE_GREPS),
        "blocking_findings_present": not blocking_clean,
        "advisory_findings_present": bool(advisory),
        "blocking": blocking_results,
        "advisory": advisory_results,
    }
    return blocking_clean, json.dumps(payload, indent=2)


def _silent_pass(path: Path | None) -> int:
    """Emit a silent pass-through report to stdout; return EXIT_PASS.

    Shared by the hook-mode short-circuits (out-of-scope target,
    per-project harness runtime-state target) so the matcher chain is
    skipped without blocking the write.
    """
    report = OrchestratorReport(
        passed=True,
        path=str(path) if path else None,
        grep_count=0,
        pass_count=0,
        fail_count=0,
    )
    print(report.to_json())
    return EXIT_PASS


def _findings_summary(report: OrchestratorReport, *, strict: bool) -> str:
    """Build the human-readable findings summary for the hook's stderr surface.

    The harness shows a ``PreToolUse`` hook's stderr to the operator; the JSON
    report on stdout is machine-facing. This summary surfaces the findings so
    they are never silent. In advisory mode (the default) the write proceeds
    and the summary points the operator at the fix plus the ``--strict`` opt-in;
    in strict mode the summary names the block reason. One line per finding;
    the matcher name plus its issue and detail are surfaced so it is actionable.
    """
    target = report.path or "<stdin>"
    if strict:
        header = (
            f"conformity-gate (strict) flagged {report.fail_count} matcher(s) "
            f"on {target} and exits non-zero to fail the CI / pre-commit step. "
            f"The shipped PreToolUse hook runs advisory and does not pass "
            f"--strict, so a runtime write proceeds; strict gating bites at "
            f"merge time, not at the tool call."
        )
    else:
        header = (
            f"conformity-gate (advisory) flagged {report.fail_count} matcher(s) "
            f"on {target}; the write proceeds — review and address the findings, "
            f"or run with --strict (or APOTHEM_CONFORMITY_STRICT=1) to block."
        )
    lines = [header]
    for inv in report.invocations:
        if inv.passed:
            continue
        for finding in inv.findings:
            label = (
                finding.get("issue")
                or finding.get("value")
                or finding.get("form")
                or "finding"
            )
            detail = finding.get("detail") or finding.get("rule") or ""
            entry = f"  - [{inv.grep}] {label}"
            if detail:
                entry += f": {detail}"
            lines.append(entry)
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    """Return the gate's argument parser (usage errors exit ``EXIT_USAGE``)."""
    parser = make_parser(PROG, __doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        LIST_FLAG,
        dest="list",
        action="store_true",
        help="print every registered validator as JSON and exit",
    )
    modes.add_argument(
        ALL_FLAG,
        dest="all",
        action="store_true",
        help="run every standalone validator over TARGET, a root directory "
        "(default: the current directory)",
    )
    modes.add_argument(
        ALL_PERWRITE_FLAG,
        dest="all_perwrite",
        action="store_true",
        help="run every per-write matcher over the tracked files under TARGET",
    )
    modes.add_argument(
        HOOK_FLAG,
        dest="hook",
        action="store_true",
        help="read a harness tool-input payload on stdin (the PreToolUse form)",
    )
    parser.add_argument(
        CHECK_FLAG,
        dest="check",
        metavar="NAME",
        default=None,
        help="run one validator: a per-write matcher over a file or stdin, or a "
        "standalone validator over a root directory",
    )
    parser.add_argument(
        STRICT_FLAG,
        dest="strict",
        action="store_true",
        help=f"exit {EXIT_FAIL} on a blocking finding (also: {STRICT_ENV}=1)",
    )
    parser.add_argument(
        STDIN_FLAG,
        dest="stdin",
        action="store_true",
        help="read the content to check from stdin",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="file to check, or the root directory for --all, --all-perwrite, "
        "or a standalone --check",
    )
    return parser


def _resolve_root(parser: argparse.ArgumentParser, target: str | None) -> Path:
    """Return *target* (default: the current directory) as an absolute root.

    A root that is not an existing directory is a usage error: a typo'd path
    in a CI step or a pre-commit hook must not read as a pass. Resolving here
    means ``.`` and the absolute form inspect the same tree.
    """
    root = Path(target) if target is not None else Path.cwd()
    if not root.is_dir():
        parser.error(f"root is not an existing directory: {root}")
    return root.resolve()


def _strict_enabled(flag: bool) -> bool:
    """Return True when ``--strict`` or a truthy ``APOTHEM_CONFORMITY_STRICT`` is set.

    The gate is advisory by default: findings are reported but never block,
    abort, or force a non-zero exit. Strict mode is opt-in — the operator
    enables it with the ``--strict`` flag or a truthy ``APOTHEM_CONFORMITY_STRICT``
    environment variable (e.g., a CI job that wants findings to fail the build).
    """
    env_enabled = os.environ.get(STRICT_ENV, "").strip().lower() in _STRICT_TRUTHY
    return flag or env_enabled


def main(argv: list[str] | None = None) -> int:
    """Dispatch one gate invocation and return its process exit code.

    Pre-conditions: ``argv`` is a full argument vector including the program
    name (``None`` reads ``sys.argv``). ``--strict`` may appear anywhere;
    ``APOTHEM_CONFORMITY_STRICT`` sets the same posture from the environment.

    Post-conditions: returns :data:`EXIT_PASS` when no blocking finding was
    raised, or when findings exist but strict mode is off — the advisory
    default reports without failing a build. Returns the findings-block code
    under ``--strict``, and the usage-error code :data:`EXIT_USAGE` for an
    unknown flag or validator name, a conflicting flag pair, a file that does
    not exist, or a root that is not an existing directory — kept distinct so
    a caller can tell a misspelled selector or path from a real finding.
    ``--help`` prints usage and returns 0.
    """
    if argv is None:
        argv = sys.argv
    parser = _build_parser()
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    strict = _strict_enabled(bool(args.strict))
    try:
        return _dispatch(parser, args, strict=strict)
    except SystemExit as exc:
        # ``parser.error`` exits EXIT_USAGE after printing its one-line message.
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE


def _dispatch(
    parser: argparse.ArgumentParser, args: argparse.Namespace, *, strict: bool
) -> int:
    """Run the mode the parsed arguments select; return the exit code."""
    corpus_mode = args.list or args.all or args.all_perwrite
    if args.check is not None and corpus_mode:
        parser.error(
            f"{CHECK_FLAG} cannot be combined with {LIST_FLAG}, "
            f"{ALL_FLAG}, or {ALL_PERWRITE_FLAG}"
        )
    if args.stdin and (corpus_mode or args.hook):
        parser.error(f"{STDIN_FLAG} applies only to a file check")
    if args.hook and args.target is not None:
        parser.error(f"{HOOK_FLAG} reads its payload from stdin; drop the path")
    if args.list:
        if args.target is not None:
            parser.error(f"{LIST_FLAG} takes no path")
        print(_list_validators())
        return EXIT_PASS
    if args.all_perwrite:
        passed, payload = _run_all_perwrite(_resolve_root(parser, args.target))
        print(payload)
        return _strict_exit_with_advisory(
            blocking_passed=passed,
            advisory_present=advisory_findings_present(json.loads(payload)),
            strict=strict,
        )
    if args.all:
        passed, payload = _run_all(_resolve_root(parser, args.target))
        print(payload)
        return _strict_exit_with_advisory(
            blocking_passed=passed,
            advisory_present=advisory_findings_present(json.loads(payload)),
            strict=strict,
        )
    only: str | None = None
    # --check <name> may name a standalone; route via subprocess when so.
    if args.check is not None:
        try:
            canonical, is_standalone = _resolve_validator(args.check)
        except ValueError as exc:
            # Unknown validator name is a CLI-usage error, not a findings block:
            # EXIT_USAGE (3) keeps it distinct from EXIT_FAIL (2, strict block).
            sys.stderr.write(f"{exc}\n")
            return EXIT_USAGE
        if is_standalone:
            if args.hook or args.stdin:
                parser.error(f"{canonical} is a standalone validator; pass a root")
            root = _resolve_root(parser, args.target)
            passed, output = _run_standalone(canonical, root)
            print(output)
            return _gate_exit(passed, strict=strict)
        only = canonical
    pre_content: str | None = None
    if args.hook and _hooks_disabled():
        return EXIT_PASS
    if args.hook:
        # Harness-dispatched hook mode: parse tool-input JSON from stdin.
        content, path, pre_content = _read_tool_input_from_stdin()
        # No resolvable target path: an empty or malformed payload (no
        # `tool_input.file_path`) carries no write to gate. Fail open rather
        # than run matchers against a path-less body — a hook invocation we
        # cannot attribute to a file is not a write the gate should block.
        if path is None:
            return _silent_pass(None)
        scopes = _resolve_scopes()
        # Scope-aware short-circuit: when the write target lives outside the
        # configured conformity scope, return a silent pass-through report
        # so the matchers do not block writes against unrelated workspaces.
        if not _path_in_any_scope(path, scopes):
            return _silent_pass(path)
        # Harness runtime-state short-circuit: the harness's own ``projects/``
        # (per-project state incl. project memory) and ``memory/`` (global
        # memory) subtrees are operator/harness-owned state, not apothem-managed
        # config. Skip the matcher chain so the operator's memory writes ---
        # provenance-less and frontmatter-less by the auto-memory convention ---
        # are not fail-closed.
        if _is_harness_state_path(path, scopes):
            return _silent_pass(path)
    else:
        args.path = args.target
        content, path = read_path_arguments(parser, args)
    try:
        if pre_content is not None:
            report = _orchestrator_diff_report(pre_content, content, path, only)
        else:
            report = run_orchestrator(content, path, only=only)
    except ValueError as exc:
        # An unresolvable grep name is a CLI-usage error: EXIT_USAGE (3), not the
        # strict findings-block code EXIT_FAIL (2).
        sys.stderr.write(f"{exc}\n")
        return EXIT_USAGE
    print(report.to_json())
    if not report.passed:
        # Surface the findings on stderr so they are never silent. The harness
        # shows a PreToolUse hook's stderr to the operator; in advisory mode the
        # write proceeds, in strict mode the non-zero exit blocks it.
        sys.stderr.write(_findings_summary(report, strict=strict) + "\n")
    return _gate_exit(report.passed, strict=strict)


def _force_utf8_streams() -> None:
    """Pin stdout/stderr to UTF-8 for the deployed-hook / CLI entry.

    The gate emits a machine-facing JSON report on stdout and a human-facing
    findings summary on stderr; the summary carries em-dashes and other
    non-ASCII punctuation. On Windows a pipe-attached stream defaults to the
    console code page (cp1252), so an em-dash leaves the process as byte 0x97
    rather than its UTF-8 encoding — a UTF-8-reading consumer (the harness that
    surfaces the hook's stderr to the operator, or a test that captures it) then
    fails to decode it. Every *file* the gate touches is already opened
    ``encoding="utf-8"``; this closes the one remaining gap, the process's own
    standard streams. Scoped to the ``__main__`` entry so an in-process
    ``main()`` call (the package-invocation tests) leaves the interpreter's
    streams — and any pytest capture wrapper standing in for them — untouched.
    Guarded and idempotent: a stream without ``reconfigure`` is skipped, and a
    detached stream is best-effort only.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(ValueError, OSError):
            reconfigure(encoding="utf-8")


if __name__ == "__main__":
    _force_utf8_streams()
    sys.exit(main(sys.argv))
