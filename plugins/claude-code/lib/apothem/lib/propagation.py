# SPDX-License-Identifier: MIT

"""Propagation-manifest loader for harness adapters.

The manifest at ``src/apothem/lib/propagation-manifest.yaml`` declares
per-harness install rules — ordered ``(source, target, mode)`` tuples,
exclude globs, stale-sweep entries, and per-directory filename filters.
This module loads the manifest and exposes typed accessors so adapter
modules consume the manifest declaratively instead of hardcoding the
rules as Python constants.

Status: manifest-driven. The canonical claude-code adapter at
``src/apothem/harnesses/claude_code/install.py`` consumes its
propagation rules from this loader via ``load_manifest`` — the manifest
IS the contract; the adapter holds no hardcoded install-layout
constants. The regression test at
``tests/unit/test_propagation_manifest.py`` verifies the manifest and
the adapter agree on the install layout.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import as_file, files
from pathlib import Path
from string import Template
from typing import Final

import yaml

# The five preserve-first ownership classes. Class assignment is by
# authorship origin and durability — who authored the bytes at the target
# path, and what the propagation driver may do to them:
#
# - apothem-owned   — bytes Apothem authors and exclusively manages.
# - operator-owned  — bytes the operator owns; Apothem merges, never
#                     silently overwrites (backup + diff + authorization).
# - vendor-reserved — bytes the harness vendor manages; never a write target.
# - generated       — Apothem's reproducible derived output; regenerate freely.
# - immutable       — append-only records; in-place rewrite is refused.
OWNERSHIP_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "apothem-owned",
        "operator-owned",
        "vendor-reserved",
        "generated",
        "immutable",
    }
)

_DEFAULT_OWNERSHIP_CLASS: Final[str] = "apothem-owned"


@dataclass(frozen=True)
class InstallEntry:
    """One propagation operation declared in the manifest."""

    source: str
    target: str
    mode: str  # write_text, tree mode, or harness-specific conversion mode
    ownership_class: str = _DEFAULT_OWNERSHIP_CLASS


@dataclass(frozen=True)
class HarnessRules:
    """Per-harness propagation rules loaded from the manifest."""

    install: list[InstallEntry]
    exclude: list[str]
    stale_sweep: list[str]
    per_directory_filters: dict[str, list[str]] = field(default_factory=dict)


_MANIFEST_FILENAME: Final[str] = "propagation-manifest.yaml"


def load_manifest() -> dict[str, HarnessRules]:
    """Load the propagation manifest and return per-harness rules.

    The parse is memoized per process and keyed by the manifest's path and
    modification time, so a batch command (install-all / update-all) that
    resolves rules once per harness parses the manifest only once. A
    manifest edited in place (different mtime) invalidates the cache on the
    next call.

    Returns:
        Mapping from harness name (e.g. ``"claude_code"``) to its
        ``HarnessRules`` record. Harnesses absent from the manifest are
        omitted from the returned mapping.

    Raises:
        FileNotFoundError: When the manifest file is missing from the
            package resources.
        ValueError: When the manifest is malformed (missing top-level
            ``harnesses`` key, unparseable YAML, or per-harness entries
            failing the schema).
    """
    # Resolve via importlib.resources and stay inside the as_file context
    # while reading: for a zipfile distribution the extracted file exists
    # only within the with-block (a path returned after the exit would
    # dangle). On-disk installs keep the (path, mtime) memoization; a zip
    # extraction gets a fresh temp path each call and simply re-parses.
    traversable = files("apothem.lib") / _MANIFEST_FILENAME
    with as_file(traversable) as concrete:
        path = Path(concrete)
        if not path.is_file():
            raise FileNotFoundError(f"propagation manifest not found at {path}")
        return _load_manifest_cached(str(path), path.stat().st_mtime_ns)


@lru_cache(maxsize=1)
def _load_manifest_cached(path_str: str, mtime_ns: int) -> dict[str, HarnessRules]:
    """Read and parse the manifest at ``path_str``; memoized by (path, mtime).

    Reading and YAML-parsing happen here so the bytes are read exactly once
    per (path, mtime). ``lru_cache`` does not memoize exceptions, so a
    malformed manifest re-parses (and re-raises ``ValueError``) on every call.
    """
    text = Path(path_str).read_text(encoding="utf-8")
    return _parse_manifest_text(text)


def _parse_manifest_text(text: str) -> dict[str, HarnessRules]:
    """Parse the manifest YAML text into per-harness rules (schema-validated)."""
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict) or "harnesses" not in raw:
        raise ValueError(
            "propagation manifest is missing the top-level 'harnesses' key"
        )
    harnesses_raw = raw["harnesses"] or {}
    if not isinstance(harnesses_raw, dict):
        raise ValueError("'harnesses' must be a mapping of harness-name to rules")

    rules: dict[str, HarnessRules] = {}
    for name, body in harnesses_raw.items():
        if body is None:
            continue
        if not isinstance(body, dict):
            raise ValueError(f"harness '{name}' entry must be a mapping")
        install_raw = body.get("install") or []
        install: list[InstallEntry] = []
        for entry in install_raw:
            if not isinstance(entry, dict):
                raise ValueError(f"harness '{name}' install entry must be a mapping")
            # Surface a missing required key as the documented ValueError with
            # the harness name attached, not a bare KeyError.
            missing = [key for key in ("source", "target") if key not in entry]
            if missing:
                raise ValueError(
                    f"harness '{name}' install entry is missing required "
                    f"key(s): {', '.join(missing)}"
                )
            ownership_class = str(
                entry.get("ownership_class", _DEFAULT_OWNERSHIP_CLASS)
            )
            if ownership_class not in OWNERSHIP_CLASSES:
                raise ValueError(
                    f"harness '{name}' install entry declares unknown "
                    f"ownership_class '{ownership_class}'"
                )
            install.append(
                InstallEntry(
                    source=str(entry["source"]),
                    target=str(entry["target"]),
                    mode=str(entry.get("mode", "replace_tree")),
                    ownership_class=ownership_class,
                )
            )
        rules[name] = HarnessRules(
            install=install,
            exclude=list(body.get("exclude") or []),
            stale_sweep=list(body.get("stale-sweep") or []),
            per_directory_filters={
                k: list(v or [])
                for k, v in (body.get("per-directory-filters") or {}).items()
            },
        )
    return rules


def resolve_target(
    template: str,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
) -> Path:
    """Substitute ``${HARNESS_ROOT}`` and ``${PROJECT_ROOT}`` into a path.

    Shared substitution helper consumed by every adapter that resolves
    manifest target paths into concrete filesystem locations. Supports
    two placeholders:

    - ``${HARNESS_ROOT}`` — the harness's user-scope configuration root
      (e.g., ``~/.claude`` for the Claude Code harness, ``~/.gemini`` for
      antigravity / gemini_cli).
    - ``${PROJECT_ROOT}`` — the operator-supplied project root, required
      by project-scope harnesses (e.g., ``<project>/.cursor/rules/`` for
      the cursor harness; analogous targets for github_copilot and
      gemini_cli project-scope entries).

    Either placeholder may be absent from the template — substitution is
    a no-op for the absent placeholder. When a template references a
    placeholder whose corresponding root argument is ``None``, the
    substitution leaves the literal placeholder in place; the caller is
    responsible for surfacing the missing-root condition as an operator
    inquiry before the resulting path is written to.
    """
    mapping: dict[str, str] = {}
    if harness_root is not None:
        mapping["HARNESS_ROOT"] = str(harness_root)
    if project_root is not None:
        mapping["PROJECT_ROOT"] = str(project_root)
    resolved = Template(template).safe_substitute(mapping)
    # A documented placeholder whose root argument is None deliberately
    # survives substitution (the caller surfaces the missing root); any
    # other residual ${...} token is a manifest typo and must not become
    # a literal path segment.
    permitted = {
        name for name in ("HARNESS_ROOT", "PROJECT_ROOT") if name not in mapping
    }
    unknown = set(re.findall(r"\$\{([^}]+)\}", resolved)) - permitted
    if unknown:
        raise ValueError(
            "unknown placeholder(s) in propagation target template "
            f"{template!r}: {', '.join(sorted(unknown))}"
        )
    return Path(resolved)


__all__ = [
    "OWNERSHIP_CLASSES",
    "HarnessRules",
    "InstallEntry",
    "load_manifest",
    "resolve_target",
]
