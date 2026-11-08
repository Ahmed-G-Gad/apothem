# SPDX-License-Identifier: MIT

"""Collect the per-commit metrics artifact the CI ``metrics`` job uploads.

Why this exists. The baseline numbers that decide whether a change helped or
hurt (coverage of the conformity gate and the audit tooling, the always-on
context each harness carries, CLI start-up, hook latency) were measured once by
hand. This script measures them on every CI run and writes one JSON document,
so a regression shows up as a changed number instead of going unnoticed.

Output (``--out``, default stdout), ``schema_version: 1``:

* ``coverage`` — line + branch coverage percent per package (``engine``,
  ``conformity``, ``audit``) from a ``coverage json`` report of a run measured
  over ``src/apothem`` (``--coverage-json``); ``coverage_lines`` gives the
  statement-only figure beside it. ``coverage_floors`` holds each
  package's floor: the engine's is ``[tool.coverage.report] fail_under`` and
  the others come from ``[tool.coverage.package-floors]`` in ``pyproject.toml``.
  ``--check-floors`` exits 1 when a measured package is below its floor.
* ``always_on_bytes`` / ``always_on_files`` — for each of the registered
  harnesses: ``profile init`` and ``install --harness <h> --project <p>`` into
  a scratch ``HOME`` and project, then the bytes on disk (frontmatter included)
  of the instruction files that harness loads in full at launch. Which files
  count is a per-harness rule taken from the vendor's documented launch
  surfaces; ``rules.always_on_bytes`` carries the rule text for every harness.
  Skill, agent and command listings (description text only) are not counted.
* ``cli_coldstart_ms`` — median wall time of ``python -m apothem --version``
  over ``--runs`` runs; ``cli_coldstart_detail_ms`` adds ``--help``.
* ``hook_e2e_ms`` / ``hook_injected_chars`` — per registered event and matcher,
  from ``src/apothem/benchmarks/bench_hooks.py --json``: the median total time
  of the chain on a real payload and the context characters it injects.
* ``nulls`` — every value that is ``null`` names its reason here
  (``"<key>.<sub-key>": "<reason>"``), so a missing number is never silent.

Exit codes: 0 written; 1 a coverage floor was missed (with ``--check-floors``);
2 usage error.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
PYPROJECT = REPO_ROOT / "pyproject.toml"
BENCH_HOOKS = SRC / "apothem" / "benchmarks" / "bench_hooks.py"
SCHEMA_VERSION = 1
DEFAULT_RUNS = 10
HOOK_RUNS = 5
INSTALL_TIMEOUT_S = 300

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from apothem.lib.harness_registry import SUPPORTED_HARNESS_IDS  # noqa: E402

# ---------------------------------------------------------------------------
# Coverage per package
# ---------------------------------------------------------------------------


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        # The dual-code ignore keeps both type-check contexts clean: mypy's
        # 3.10 target has no tomllib stub; 3.11+ needs no ignore at all.
        import tomllib  # type: ignore[import-not-found, unused-ignore]
    except ModuleNotFoundError as exc:  # Python 3.10: no stdlib TOML reader
        raise SystemExit(
            f"collect_metrics: reading {path.name} needs Python 3.11+ (tomllib)"
        ) from exc
    with path.open("rb") as handle:
        data: dict[str, Any] = tomllib.load(handle)
    return data


def coverage_config(
    pyproject: Path,
) -> tuple[dict[str, tuple[str, ...]], dict[str, float]]:
    """Return ``(packages, floors)`` from the coverage tables in ``pyproject``.

    ``engine`` is the ``[tool.coverage.run] source`` set with the
    ``[tool.coverage.report] fail_under`` floor; every entry of
    ``[tool.coverage.package-floors]`` adds a package with its own path and
    floor.
    """
    coverage = _load_toml(pyproject)["tool"]["coverage"]
    packages: dict[str, tuple[str, ...]] = {
        "engine": tuple(str(path) for path in coverage["run"]["source"])
    }
    floors: dict[str, float] = {"engine": float(coverage["report"]["fail_under"])}
    for name, entry in coverage.get("package-floors", {}).items():
        packages[name] = (str(entry["path"]),)
        floors[name] = float(entry["fail_under"])
    return packages, floors


def _normalized(path: str) -> str:
    return path.replace("\\", "/")


def coverage_by_package(
    report: Mapping[str, Any],
    packages: Mapping[str, tuple[str, ...]],
    *,
    branches: bool = True,
) -> dict[str, float | None]:
    """Return coverage percent per package from a coverage JSON report.

    With ``branches`` (the default) this is coverage.py's own percentage, the
    unit the floors use: (covered lines + covered branches) / (statements +
    branches). ``branches=False`` gives statement coverage alone. A file
    belongs to a package when its path contains one of the package's directory
    prefixes; a package with no measured file is ``None``.
    """
    totals = {name: [0, 0] for name in packages}
    for path, entry in report.get("files", {}).items():
        normalized = "/" + _normalized(path)
        summary = entry["summary"]
        hit = summary["covered_lines"]
        total = summary["num_statements"]
        if branches:
            hit += summary.get("covered_branches", 0)
            total += summary.get("num_branches", 0)
        for name, prefixes in packages.items():
            if any(f"/{prefix.strip('/')}/" in normalized for prefix in prefixes):
                totals[name][0] += hit
                totals[name][1] += total
    return {
        name: (round(100 * hit / total, 2) if total else None)
        for name, (hit, total) in totals.items()
    }


def floor_violations(
    measured: Mapping[str, float | None], floors: Mapping[str, float]
) -> list[str]:
    """Return one line per package below its floor (or not measured)."""
    violations = []
    for name, floor in floors.items():
        value = measured.get(name)
        if value is None:
            violations.append(f"{name} not measured (floor {floor:g})")
        elif value < floor:
            violations.append(f"{name} {value:g} < floor {floor:g}")
    return violations


# ---------------------------------------------------------------------------
# Always-on launch surfaces
# ---------------------------------------------------------------------------

_FRONTMATTER_LINE = re.compile(r"^([A-Za-z][\w-]*)\s*:\s*(.*?)\s*$")


def _frontmatter(text: str) -> dict[str, str]:
    """Return the first YAML frontmatter block's top-level ``key: value`` pairs.

    A leading HTML comment line (an SPDX header or a managed-block sentinel)
    may precede the block. Values are unquoted; nested values read as ``""``.
    """
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines[:12]) if line.strip() == "---"), None
    )
    if start is None:
        return {}
    fields: dict[str, str] = {}
    for line in lines[start + 1 :]:
        if line.strip() == "---":
            return fields
        match = _FRONTMATTER_LINE.match(line)
        if match:
            fields[match.group(1)] = match.group(2).strip("\"'")
    return {}


Predicate = Callable[[str], bool]


def _key_is(key: str, *values: str, missing: bool = False) -> Predicate:
    """Frontmatter predicate: ``key`` equals one of ``values`` (or is absent)."""

    def check(text: str) -> bool:
        fields = _frontmatter(text)
        if key not in fields:
            return missing
        return fields[key].lower() in values

    return check


def _no_key(key: str) -> Predicate:
    return lambda text: key not in _frontmatter(text)


def _has_text(text: str) -> bool:
    """Predicate: the file holds more than whitespace (blank files load nothing)."""
    return bool(text.strip())


def _codebuddy_rule(text: str) -> bool:
    """Predicate: a CodeBuddy rule that loads at launch.

    ``enabled: false`` turns a rule off, and ``alwaysApply`` defaults to true;
    a rule with ``alwaysApply: false`` loads only for matching paths.
    """
    fields = _frontmatter(text)
    if fields.get("enabled", "").lower() == "false":
        return False
    return fields.get("alwaysApply", "true").lower() == "true"


@dataclass(frozen=True)
class Surface:
    """A launch-time instruction surface: glob under ``home`` or ``project``."""

    root: str
    pattern: str
    predicate: Predicate | None = None


def _home(pattern: str, predicate: Predicate | None = None) -> Surface:
    return Surface("home", pattern, predicate)


def _project(pattern: str, predicate: Predicate | None = None) -> Surface:
    return Surface("project", pattern, predicate)


#: OpenClaw's bootstrap files in prompt order (workspace-bootstrap-policy.ts).
_OPEN_CLAW_ORDER = (
    "AGENTS.md",
    "SOUL.md",
    "IDENTITY.md",
    "USER.md",
    "BOOTSTRAP.md",
    "MEMORY.md",
)
_OPEN_CLAW_FILE_CHARS = 20_000
_OPEN_CLAW_USER_CHARS = 4_000
_OPEN_CLAW_TOTAL_CHARS = 60_000
#: OpenClaw stops adding files once fewer characters than this remain.
_OPEN_CLAW_MIN_REMAINING = 64

#: Antigravity truncates each instruction file at this many bytes. It applies
#: the cap after @ includes expand; the collector does not expand includes
#: (Apothem's files hold none). Antigravity's 20,000-token budget across the
#: global and always_on rules, past which the largest become on-demand
#: pointers, is not modeled.
_ANTIGRAVITY_FILE_MAX_BYTES = 24_000

_ZED_ORDER = (
    ".rules",
    ".cursorrules",
    ".windsurfrules",
    ".clinerules",
    ".github/copilot-instructions.md",
    "AGENT.md",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
)

# harness -> (rule text, surfaces). Sources: each harness's vendor docs as
# recorded in the harness currency pass (antigravity.google, code.claude.com,
# codebuddy.ai, learn.chatgpt.com/codex, cursor.com, gemini-cli docs,
# docs.github.com, hermes-agent docs, kimi-code docs, kiro.dev,
# docs.openclaw.ai, opencode.ai, qwen-code docs, docs.trae.ai, docs.devin.ai,
# zed.dev, docs.z.ai).
LAUNCH_SURFACES: dict[str, tuple[str, tuple[Surface, ...]]] = {
    "antigravity": (
        "~/.gemini/{GEMINI,AGENTS}.md, ~/.gemini/config/{GEMINI,AGENTS}.md, "
        "~/.gemini/config/rules/*.md with trigger: always_on, and in the project "
        "{GEMINI,AGENTS}.md, .agents/{GEMINI,AGENTS}.md and .agents/rules/*.md "
        "with trigger: always_on, plus ~/.gemini/config/plugins/<name>/rules/*.md "
        "with trigger: always_on; each file counted up to 24,000 bytes. "
        "@ includes are not expanded, and the 20,000-token budget across "
        "always-on rules is not modeled.",
        (
            _home(".gemini/GEMINI.md"),
            _home(".gemini/AGENTS.md"),
            _home(".gemini/config/GEMINI.md"),
            _home(".gemini/config/AGENTS.md"),
            _home(".gemini/config/rules/*.md", _key_is("trigger", "always_on")),
            _home(
                ".gemini/config/plugins/*/rules/*.md",
                _key_is("trigger", "always_on"),
            ),
            _project("GEMINI.md"),
            _project("AGENTS.md"),
            _project(".agents/GEMINI.md"),
            _project(".agents/AGENTS.md"),
            _project(".agents/rules/*.md", _key_is("trigger", "always_on")),
        ),
    ),
    "claude-code": (
        "~/.claude/CLAUDE.md and ~/.claude/rules/**/*.md without paths: "
        "frontmatter, plus the project CLAUDE.md, .claude/CLAUDE.md, "
        "CLAUDE.local.md and .claude/rules/**/*.md without paths:, and the "
        "project AGENTS.md and .claude/AGENTS.md only when none of the three "
        "project CLAUDE files exists.",
        (
            _home(".claude/CLAUDE.md"),
            _home(".claude/rules/**/*.md", _no_key("paths")),
            _project("CLAUDE.md"),
            _project(".claude/CLAUDE.md"),
            _project("CLAUDE.local.md"),
            _project(".claude/rules/**/*.md", _no_key("paths")),
        ),
    ),
    "codebuddy": (
        ".codebuddy/rules/**/*.md (project and ~) unless enabled: false or "
        "alwaysApply: false (the default is always), ~/.codebuddy/CODEBUDDY.md, "
        "the project CODEBUDDY.local.md, and the first of the project "
        "CODEBUDDY.md and .codebuddy/CODEBUDDY.md, else the project AGENTS.md.",
        (
            _project(".codebuddy/rules/**/*.md", _codebuddy_rule),
            _home(".codebuddy/rules/**/*.md", _codebuddy_rule),
            _home(".codebuddy/CODEBUDDY.md"),
            _project("CODEBUDDY.local.md"),
        ),
    ),
    "codex": (
        "The first non-empty of ~/.codex/AGENTS.override.md and ~/.codex/AGENTS.md, "
        "plus the first of AGENTS.override.md, AGENTS.md and the "
        "project_doc_fallback_filenames names that exists in the project (an "
        "empty one loads nothing), counted up to project_doc_max_bytes (32 KiB "
        "by default).",
        (),
    ),
    "cursor": (
        ".cursor/rules/**/*.mdc with alwaysApply: true, and the project AGENTS.md.",
        (
            _project(".cursor/rules/**/*.mdc", _key_is("alwaysApply", "true")),
            _project("AGENTS.md"),
        ),
    ),
    "gemini-cli": (
        "~/.gemini/GEMINI.md and the project GEMINI.md.",
        (_home(".gemini/GEMINI.md"), _project("GEMINI.md")),
    ),
    "github-copilot": (
        ".github/copilot-instructions.md and the project AGENTS.md. Path-scoped "
        ".github/instructions files are not counted.",
        (_project(".github/copilot-instructions.md"), _project("AGENTS.md")),
    ),
    "hermes": (
        "~/.hermes/SOUL.md when it holds text, plus the first of these kinds "
        "in the project with a non-empty file (Hermes loads one): .hermes.md "
        "or HERMES.md (the first of "
        "the two that exists is the only candidate), AGENTS.override.md or "
        "AGENTS.md, CLAUDE.md, then .cursorrules with every .cursor/rules/*.mdc. "
        "The Apothem support tree and apothem/rules/ are not launch surfaces.",
        (_home(".hermes/SOUL.md", _has_text),),
    ),
    "kimi-code": (
        "~/.kimi-code/AGENTS.md, the first non-empty of ~/.agents/AGENTS.md and "
        "~/.agents/agents.md, and the project .kimi-code/AGENTS.md and "
        "AGENTS.md; blank files load nothing. Kimi also reads AGENTS.md in "
        "each folder from the git root down; the scratch project has no .git, "
        "so only its root is read.",
        (
            _home(".kimi-code/AGENTS.md", _has_text),
            _project(".kimi-code/AGENTS.md", _has_text),
            _project("AGENTS.md", _has_text),
        ),
    ),
    "kiro": (
        ".kiro/steering/**/*.md (project and ~) with inclusion: always or no "
        "inclusion key (the default is always), and the project AGENTS.md.",
        (
            _project(
                ".kiro/steering/**/*.md", _key_is("inclusion", "always", missing=True)
            ),
            _home(
                ".kiro/steering/**/*.md", _key_is("inclusion", "always", missing=True)
            ),
            _project("AGENTS.md"),
        ),
    ),
    "open-claw": (
        "The non-blank workspace bootstrap files in ~/.openclaw/workspace/, in "
        "prompt order: " + ", ".join(_OPEN_CLAW_ORDER) + "; each up to 20,000 "
        "characters (USER.md 4,000), 60,000 in all. The count is approximate: "
        "OpenClaw's own trimming, head-and-tail truncation, missing-file "
        "markers and per-session filtering are not modeled. apothem/rules/ is "
        "not a launch surface.",
        (),
    ),
    "opencode": (
        "~/.config/opencode/AGENTS.md, the project AGENTS.md, and every file the "
        "instructions globs in ~/.config/opencode/opencode.json match (~ "
        "expanded; relative globs resolve against the project).",
        (_home(".config/opencode/AGENTS.md"), _project("AGENTS.md")),
    ),
    "qwen-code": (
        "The context file(s) named by ~/.qwen/settings.json context.fileName "
        "(default QWEN.md) in ~/.qwen/ and in the project.",
        (),
    ),
    "trae": (
        ".trae/rules/**/*.md with alwaysApply: true (Trae reads alwaysApply, "
        "description and globs), and ~/.trae/user_rules/*.md.",
        (
            _project(".trae/rules/**/*.md", _key_is("alwaysApply", "true")),
            _home(".trae/user_rules/*.md"),
        ),
    ),
    "windsurf": (
        ".devin/rules/**/*.md and .windsurf/rules/**/*.md with trigger: "
        "always_on, ~/.codeium/windsurf/memories/global_rules.md, and the "
        "project AGENTS.md.",
        (
            _project(".devin/rules/**/*.md", _key_is("trigger", "always_on")),
            _project(".windsurf/rules/**/*.md", _key_is("trigger", "always_on")),
            _home(".codeium/windsurf/memories/global_rules.md"),
            _project("AGENTS.md"),
        ),
    ),
    "zed": (
        "The first of " + ", ".join(_ZED_ORDER) + " in the project (Zed reads "
        "one), plus ~/.config/zed/AGENTS.md.",
        (_home(".config/zed/AGENTS.md"),),
    ),
    "glm": (
        "None: GLM is a model backend (a provider config); it loads no "
        "instruction files.",
        (),
    ),
}


def _surface_files(surface: Surface, home: Path, project: Path) -> list[Path]:
    base = home if surface.root == "home" else project
    matches = sorted(base.glob(surface.pattern))
    found = []
    for path in matches:
        if not path.is_file():
            continue
        if surface.predicate is not None and not surface.predicate(
            path.read_text(encoding="utf-8", errors="replace")
        ):
            continue
        found.append(path)
    return found


def _opencode_instruction_files(home: Path, project: Path) -> list[Path]:
    config = home / ".config" / "opencode" / "opencode.json"
    if not config.is_file():
        return []
    try:
        instructions = json.loads(config.read_text(encoding="utf-8")).get(
            "instructions", []
        )
    except json.JSONDecodeError:
        return []
    files: list[Path] = []
    for pattern in instructions:
        text = str(pattern)
        if text.startswith("~/"):
            text = str(home / text[2:])
        elif not Path(text).is_absolute():
            text = str(project / text)
        # glob.glob, not Path.glob: the configured patterns are absolute once
        # `~` is expanded, and Path.glob takes relative patterns only.
        matches = sorted(glob.glob(text, recursive=True))  # noqa: PTH207
        files.extend(Path(match) for match in matches)
    return [path for path in files if path.is_file()]


def _qwen_context_files(home: Path, project: Path) -> list[Path]:
    names: list[str] = ["QWEN.md"]
    settings = home / ".qwen" / "settings.json"
    if settings.is_file():
        try:
            configured = (
                json.loads(settings.read_text(encoding="utf-8"))
                .get("context", {})
                .get("fileName")
            )
        except (json.JSONDecodeError, AttributeError):
            configured = None
        if isinstance(configured, str):
            names = [configured]
        elif isinstance(configured, list) and configured:
            names = [str(name) for name in configured]
    candidates = [home / ".qwen" / name for name in names] + [
        project / name for name in names
    ]
    return [path for path in candidates if path.is_file()]


def _zed_files(project: Path) -> list[Path]:
    for name in _ZED_ORDER:
        path = project / name
        if path.is_file():
            return [path]
    return []


def _non_empty(path: Path) -> bool:
    try:
        return path.is_file() and bool(path.read_text(encoding="utf-8").strip())
    except (OSError, UnicodeDecodeError):
        return False


def _first_non_empty(paths: Iterable[Path]) -> list[Path]:
    return next(([path] for path in paths if _non_empty(path)), [])


def _hermes_files(project: Path) -> list[Path]:
    # Hermes loads one kind of project context, the first with a non-empty file.
    # The first of .hermes.md and HERMES.md that exists is the only candidate of
    # its kind, so an empty .hermes.md hides a HERMES.md beside it. The scratch
    # project has no git root, so each kind is read from the project folder.
    hermes_md = next(
        (project / n for n in (".hermes.md", "HERMES.md") if (project / n).is_file()),
        None,
    )
    cursor_rules = [
        project / ".cursorrules",
        *sorted((project / ".cursor" / "rules").glob("*.mdc")),
    ]
    kinds = (
        _first_non_empty([hermes_md] if hermes_md is not None else []),
        _first_non_empty(
            project / name for name in ("AGENTS.override.md", "AGENTS.md", "agents.md")
        ),
        _first_non_empty(project / name for name in ("CLAUDE.md", "claude.md")),
        [path for path in cursor_rules if _non_empty(path)],
    )
    return next((files for files in kinds if files), [])


def _claude_code_agents_files(project: Path) -> list[Path]:
    # Claude Code reads AGENTS.md only when no CLAUDE file is in the working
    # folder or above it. The collector checks only the project root: the
    # scratch project has no parent that holds one. ~/.claude/CLAUDE.md and
    # the rules do not count.
    # TODO(clarify): whether an empty CLAUDE.md blocks the fallback; it is
    # treated as present.
    if any(
        (project / name).is_file()
        for name in ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md")
    ):
        return []
    return [
        project / name
        for name in ("AGENTS.md", ".claude/AGENTS.md")
        if (project / name).is_file()
    ]


def _codebuddy_memory_files(project: Path) -> list[Path]:
    # The docs call ./CODEBUDDY.md and ./.codebuddy/CODEBUDDY.md equivalent and
    # read AGENTS.md only without a CODEBUDDY.md. The collector checks only
    # the project root: the scratch project has no parent that holds one.
    # TODO(clarify): CodeBuddy documents neither which of the two loads when
    # both exist nor whether a lone .codebuddy/CODEBUDDY.md blocks AGENTS.md;
    # the first that exists is counted, and either one blocks AGENTS.md.
    for name in ("CODEBUDDY.md", ".codebuddy/CODEBUDDY.md", "AGENTS.md"):
        if (project / name).is_file():
            return [project / name]
    return []


def _kimi_cross_tool_files(home: Path) -> list[Path]:
    # MoonshotAI/kimi-code packages/agent-core-v2/src/agent/profile/context.ts:
    # AGENTS_MD_PLAIN_NAMES lists AGENTS.md then agents.md, the first match
    # wins, and a file whose trimmed text is empty is skipped.
    return _first_non_empty(home / ".agents" / n for n in ("AGENTS.md", "agents.md"))


def _open_claw_bytes(home: Path) -> tuple[int, int]:
    # OpenClaw caps characters, not bytes: count the bytes of the characters it
    # keeps. Each file gets at most its cap or what is left of the total, and
    # the walk stops when fewer than 64 characters are left. A missing file
    # becomes a one-line marker, which is not a file and is not counted.
    workspace = home / ".openclaw" / "workspace"
    remaining = _OPEN_CLAW_TOTAL_CHARS
    size = files = 0
    for name in _OPEN_CLAW_ORDER:
        if remaining < _OPEN_CLAW_MIN_REMAINING:
            break
        path = workspace / name
        if not _non_empty(path):
            continue
        text = path.read_text(encoding="utf-8")
        cap = _OPEN_CLAW_USER_CHARS if name == "USER.md" else _OPEN_CLAW_FILE_CHARS
        kept = text[: min(cap, remaining)]
        size += len(kept.encode("utf-8"))
        remaining -= len(kept)
        files += 1
    return size, files


_CODEX_PROJECT_DOC_MAX_BYTES = 32 * 1024


def _codex_project_doc_settings(home: Path) -> tuple[list[str], int]:
    names: list[str] = []
    max_bytes = _CODEX_PROJECT_DOC_MAX_BYTES
    config = home / ".codex" / "config.toml"
    if config.is_file():
        try:
            data = _load_toml(config)
        except ValueError:  # tomllib.TOMLDecodeError
            data = {}
        except SystemExit as exc:
            # Python 3.10 has no tomllib. collect() records a RuntimeError as a
            # null for this harness instead of ending the whole run.
            raise RuntimeError(str(exc)) from exc
        fallbacks = data.get("project_doc_fallback_filenames")
        if isinstance(fallbacks, list):
            # Codex ignores an entry that is not a plain file name.
            names = [
                name
                for name in fallbacks
                if isinstance(name, str)
                and name not in ("", ".", "..")
                and Path(name).name == name
            ]
        limit = data.get("project_doc_max_bytes")
        if isinstance(limit, int) and not isinstance(limit, bool) and limit >= 0:
            max_bytes = limit
    return names, max_bytes


def _codex_bytes(home: Path, project: Path) -> tuple[int, int]:
    # The global file is the first non-empty of the two. In each project folder
    # Codex takes the first candidate that exists and loads nothing from an
    # empty one, and project files share the project_doc_max_bytes budget. The
    # scratch project has no .git, so its folder is the whole chain.
    files = _first_non_empty(
        home / ".codex" / name for name in ("AGENTS.override.md", "AGENTS.md")
    )
    size = sum(path.stat().st_size for path in files)
    fallbacks, budget = _codex_project_doc_settings(home)
    for name in dict.fromkeys(("AGENTS.override.md", "AGENTS.md", *fallbacks)):
        path = project / name
        if path.is_file():
            if budget > 0 and _non_empty(path):
                size += min(path.stat().st_size, budget)
                files.append(path)
            break
    return size, len(files)


def measure_surfaces(harness: str, home: Path, project: Path) -> tuple[int, int]:
    """Return ``(bytes, files)`` loaded at launch for ``harness`` in a tree."""
    if harness == "codex":
        return _codex_bytes(home, project)
    if harness == "open-claw":
        return _open_claw_bytes(home)
    _rule, surfaces = LAUNCH_SURFACES[harness]
    files: list[Path] = []
    for surface in surfaces:
        files.extend(_surface_files(surface, home, project))
    if harness == "opencode":
        files.extend(_opencode_instruction_files(home, project))
    elif harness == "qwen-code":
        files.extend(_qwen_context_files(home, project))
    elif harness == "zed":
        files.extend(_zed_files(project))
    elif harness == "hermes":
        files.extend(_hermes_files(project))
    elif harness == "claude-code":
        files.extend(_claude_code_agents_files(project))
    elif harness == "codebuddy":
        files.extend(_codebuddy_memory_files(project))
    elif harness == "kimi-code":
        files.extend(_kimi_cross_tool_files(home))
    unique = sorted({path.resolve() for path in files})
    sizes = [path.stat().st_size for path in unique]
    if harness == "antigravity":
        sizes = [min(size, _ANTIGRAVITY_FILE_MAX_BYTES) for size in sizes]
    return sum(sizes), len(unique)


def _isolated_env(root: Path) -> dict[str, str]:
    home = root / "home"
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"CODEX_HOME", "XDG_CONFIG_HOME", "PYTHONPATH"}
    }
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            # Pinned under the scratch HOME so the install lands where the
            # claude-code surfaces look, whether or not the adapter honours it.
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            "TMPDIR": str(root / "tmp"),
            "PYTHONPATH": str(SRC),
        }
    )
    return env


def _apothem(
    args: list[str], env: dict[str, str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed argv: this interpreter running the checkout's own CLI
        [sys.executable, "-m", "apothem", *args],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_S,
        check=False,
    )


def install_and_measure(harness: str) -> tuple[int, int]:
    """Install ``harness`` into a scratch HOME + project; return (bytes, files).

    Raises ``RuntimeError`` naming the failing step when the install fails.
    """
    with tempfile.TemporaryDirectory(prefix=f"apothem-metrics-{harness}-") as scratch:
        root = Path(scratch)
        home, project = root / "home", root / "project"
        for directory in (home, project, root / "tmp"):
            directory.mkdir()
        env = _isolated_env(root)
        for args in (
            ["profile", "init", "-q"],
            ["install", "--harness", harness, "--project", str(project), "-q"],
        ):
            completed = _apothem(args, env, project)
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout).strip().splitlines()
                raise RuntimeError(
                    f"`apothem {' '.join(args[:3])}` exited {completed.returncode}: "
                    f"{detail[-1] if detail else 'no output'}"
                )
        return measure_surfaces(harness, home, project)


# ---------------------------------------------------------------------------
# CLI cold start and hook latency
# ---------------------------------------------------------------------------


def cli_coldstart_ms(args: list[str], runs: int) -> float:
    """Median wall time in ms of ``python -m apothem <args>`` from the checkout."""
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    env["PYTHONPATH"] = str(SRC)
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        completed = subprocess.run(  # noqa: S603 — fixed argv: this interpreter running the checkout's own CLI
            [sys.executable, "-m", "apothem", *args],
            env=env,
            capture_output=True,
            check=False,
        )
        samples.append(time.perf_counter() - start)
        if completed.returncode != 0:
            raise RuntimeError(
                f"`apothem {' '.join(args)}` exited {completed.returncode}"
            )
    return round(statistics.median(samples) * 1000, 1)


def hook_metrics(
    report: Mapping[str, Any], nulls: dict[str, str]
) -> tuple[dict[str, float | None], dict[str, int | None]]:
    """Map a ``bench_hooks --json`` report to latency and injection values.

    A chain that did not produce a measurement is ``None`` with its reason
    recorded in ``nulls`` under ``hook_e2e_ms.<event[:matcher]>``.
    """
    latency: dict[str, float | None] = {}
    injected: dict[str, int | None] = {}
    for label, chain in report.get("chains", {}).items():
        latency[label] = chain.get("median_sum_ms")
        injected[label] = chain.get("injected_chars")
        if latency[label] is None:
            nulls[f"hook_e2e_ms.{label}"] = str(
                chain.get("detail", chain.get("status"))
            )
    return latency, injected


def run_hook_benchmark(runs: int) -> dict[str, Any]:
    """Run ``bench_hooks.py --json`` and return its report."""
    completed = subprocess.run(  # noqa: S603 — fixed argv: the repository's own benchmark driver
        [sys.executable, str(BENCH_HOOKS), "--json", f"--runs={runs}"],
        env={**os.environ, "PYTHONPATH": str(SRC)},
        capture_output=True,
        text=True,
        check=False,
    )
    if not completed.stdout.strip():
        raise RuntimeError(f"bench_hooks printed no report: {completed.stderr.strip()}")
    report: dict[str, Any] = json.loads(completed.stdout)
    return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 — git from PATH, read-only query
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return completed.stdout.strip() or None


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    """Measure everything requested; return ``(metrics, floor violations)``."""
    nulls: dict[str, str] = {}
    packages, floors = coverage_config(PYPROJECT)

    coverage: dict[str, float | None] = dict.fromkeys(packages)
    coverage_lines: dict[str, float | None] = dict.fromkeys(packages)
    if args.coverage_json:
        report = json.loads(Path(args.coverage_json).read_text(encoding="utf-8"))
        coverage = coverage_by_package(report, packages)
        coverage_lines = coverage_by_package(report, packages, branches=False)
        for name, value in coverage.items():
            if value is None:
                nulls[f"coverage.{name}"] = "no file of the package was measured"
    else:
        for name in packages:
            nulls[f"coverage.{name}"] = "no --coverage-json report supplied"
    violations = floor_violations(coverage, floors) if args.check_floors else []

    selected = args.harness or list(SUPPORTED_HARNESS_IDS)
    always_on_bytes: dict[str, int | None] = {}
    always_on_files: dict[str, int | None] = {}
    for harness in SUPPORTED_HARNESS_IDS:
        if harness not in selected:
            always_on_bytes[harness] = always_on_files[harness] = None
            nulls[f"always_on_bytes.{harness}"] = "not selected (--harness)"
            continue
        try:
            always_on_bytes[harness], always_on_files[harness] = install_and_measure(
                harness
            )
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            always_on_bytes[harness] = always_on_files[harness] = None
            nulls[f"always_on_bytes.{harness}"] = str(exc)

    coldstart: float | None = None
    coldstart_detail: dict[str, float | None] = {}
    if args.skip_coldstart:
        nulls["cli_coldstart_ms"] = "skipped (--skip-coldstart)"
    else:
        for flag in ("--version", "--help"):
            try:
                coldstart_detail[flag] = cli_coldstart_ms([flag], args.runs)
            except RuntimeError as exc:
                coldstart_detail[flag] = None
                nulls[f"cli_coldstart_detail_ms.{flag}"] = str(exc)
        coldstart = coldstart_detail.get("--version")
        if coldstart is None:
            nulls["cli_coldstart_ms"] = nulls.get(
                "cli_coldstart_detail_ms.--version", "not measured"
            )

    hook_latency: dict[str, float | None] = {}
    hook_injected: dict[str, int | None] = {}
    if args.skip_hooks:
        nulls["hook_e2e_ms"] = "skipped (--skip-hooks)"
    else:
        try:
            hook_latency, hook_injected = hook_metrics(
                run_hook_benchmark(args.hook_runs), nulls
            )
        except (RuntimeError, json.JSONDecodeError) as exc:
            nulls["hook_e2e_ms"] = str(exc)

    metrics = {
        "schema_version": SCHEMA_VERSION,
        "commit": _git_commit(),
        "python": sys.version.split()[0],
        "coverage": coverage,
        "coverage_floors": floors,
        "coverage_lines": coverage_lines,
        "always_on_bytes": always_on_bytes,
        "always_on_files": always_on_files,
        "cli_coldstart_ms": coldstart,
        "cli_coldstart_detail_ms": coldstart_detail,
        "hook_e2e_ms": hook_latency,
        "hook_injected_chars": hook_injected,
        "nulls": nulls,
        "rules": {
            "always_on_bytes": {
                harness: rule for harness, (rule, _surfaces) in LAUNCH_SURFACES.items()
            },
            "coverage": (
                "line + branch percent per package (coverage.py's unit); floors "
                "from pyproject.toml; coverage_lines is statements only"
            ),
            "cli_coldstart_ms": "median of `python -m apothem --version` (PYTHONPATH=src)",
            "hook_e2e_ms": "bench_hooks.py median_sum_ms per registered event and matcher",
        },
    }
    return metrics, violations


def main(argv: list[str] | None = None) -> int:
    """Collect the metrics artifact; return the exit code (see module docstring)."""
    parser = argparse.ArgumentParser(
        prog="collect_metrics", description=__doc__.splitlines()[0]
    )
    parser.add_argument(
        "--coverage-json", help="coverage.py JSON report of a run over src/apothem."
    )
    parser.add_argument(
        "--check-floors",
        action="store_true",
        help="Exit 1 when a package's coverage is below its floor.",
    )
    parser.add_argument(
        "--harness",
        action="append",
        choices=list(SUPPORTED_HARNESS_IDS),
        help="Measure always-on bytes for this harness only (repeatable); default all.",
    )
    parser.add_argument(
        "--runs", type=int, default=DEFAULT_RUNS, help="Cold-start runs."
    )
    parser.add_argument(
        "--hook-runs", type=int, default=HOOK_RUNS, help="Runs per hook chain."
    )
    parser.add_argument("--skip-coldstart", action="store_true")
    parser.add_argument("--skip-hooks", action="store_true")
    parser.add_argument("--out", help="Write the JSON here instead of stdout.")
    args = parser.parse_args(argv)
    if args.runs < 1 or args.hook_runs < 1:
        parser.error("--runs and --hook-runs must be at least 1")

    metrics, violations = collect(args)
    text = json.dumps(metrics, indent=2, sort_keys=False) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    for line in violations:
        print(f"collect_metrics: coverage floor missed: {line}", file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
