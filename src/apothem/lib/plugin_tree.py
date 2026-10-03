# SPDX-License-Identifier: MIT

"""Plugin source-tree assembler and manifest generator.

This module materializes the canonical ``.claude-plugin`` distribution unit:
a self-contained bundle of the apothem engine plus its catalog (skills,
agents, commands, rules, hooks) that runs directly from the assembled tree —
the engine and its vendored dependencies import in place, and no package
installation occurs at any point.

:func:`assemble_plugin_tree` copies the ``apothem`` package verbatim into
``lib/apothem`` and writes a thin ``apothem_lib`` shim re-exporting its
public submodules; the engine is never renamed or rewritten.

The layout contract produced is::

    <plugin_root>/.claude-plugin/plugin.json
    <plugin_root>/lib/apothem/            (verbatim engine copy)
    <plugin_root>/lib/apothem_lib.py      (re-export shim)
    <plugin_root>/lib/apothem/_vendor/    (vendored deps, or empty .keep)
    <plugin_root>/skills|agents|commands|hooks|rules|output-styles/  (catalog copies)
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Final

import jsonschema

#: Plugin identifier. The plugin *is* apothem (verbatim engine reuse).
PLUGIN_NAME: Final[str] = "apothem"

#: Capability-led description embedded in the generated manifest. Names only
#: what the plugin itself delivers to Claude Code — slash-commands, agents,
#: skills, mechanical hooks, and behavioral rules referenced on-demand (the
#: SessionStart bootstrap points at the bundled rules; they are not auto-loaded
#: as always-on context plugin-alone). It deliberately omits always-on-rules
#: sync and MCP-server sync: those are engine capabilities, not plugin features.
PLUGIN_DESCRIPTION: Final[str] = (
    "Host-agnostic AI-harness configuration catalog: review and audit "
    "slash-commands, research and quality agents, reusable skills, mechanical "
    "conformity hooks, and behavioral rules referenced on-demand — bundled "
    "with the self-contained apothem engine."
)

#: Manifest metadata embedded in every generated plugin manifest.
PLUGIN_AUTHOR: Final[dict[str, str]] = {
    "name": "Ahmed G. Gad",
    "email": "me@ahmedgad.com",
    "url": "https://github.com/ahmed-g-gad",
}
PLUGIN_HOMEPAGE: Final[str] = "https://apothem.ahmedgad.com"
PLUGIN_REPOSITORY: Final[str] = "https://github.com/ahmed-g-gad/apothem"

#: Name shown in Claude Code's UI in place of the kebab-case ``name``.
PLUGIN_DISPLAY_NAME: Final[str] = "Apothem"

#: Directory-listing links. Anthropic's plugin directory reads these from
#: ``plugin.json``; Claude Code ignores them at load time. Each must be an
#: ``https://`` URL (manifest reference, "Directory listing fields").
#: The support link is the issue tracker SUPPORT.md routes defects and
#: questions to.
#:
#: TODO(clarify): ``privacyPolicyUrl`` and ``termsOfServiceUrl`` stay unset
#: until the operator publishes those pages; their URLs cannot be derived from
#: the repository. ``icon`` needs an image file inside the assembled tree,
#: which the assembler does not copy yet.
PLUGIN_LISTING_URLS: Final[dict[str, str]] = {
    "documentationUrl": "https://apothem.ahmedgad.com/docs",
    "supportUrl": "https://github.com/ahmed-g-gad/apothem/issues",
}
PLUGIN_LICENSE: Final[str] = "MIT"
PLUGIN_KEYWORDS: Final[tuple[str, ...]] = (
    "configuration",
    "profiles",
    "skills",
    "agents",
    "commands",
)

#: Documentation files that live beside catalog members but are never members.
_CATALOG_DOC_FILES: Final[frozenset[str]] = frozenset({"README.md", "AGENTS.md"})

#: Directory names that are pruned from the engine copy (never distributed).
_COPY_IGNORE: Final[tuple[str, ...]] = (
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)

#: Catalog directory names copied from the engine source into the plugin root.
#: ``output-styles/`` is the plugin's default output-style folder: with no
#: ``outputStyles`` manifest key, Claude Code scans it, so the styles are
#: selectable plugin-alone (https://code.claude.com/docs/en/plugins-reference,
#: "Output styles | output-styles/", retrieved 2026-10-03).
_CATALOG_DIRS: Final[tuple[str, ...]] = (
    "skills",
    "agents",
    "commands",
    "rules",
    "output-styles",
)

#: Source-relative location of the hook message catalog.
_HOOK_MESSAGES_REL: Final[Path] = Path("hooks") / "messages"

#: Plugin-root-relative engine prefix for the assembled tree. The engine is
#: copied verbatim to ``lib/apothem`` by :func:`assemble_plugin_tree`, so the
#: bootstrap stubs, the dispatcher, and the message catalog all resolve under
#: this prefix when the plugin is installed alone from the assembled bundle.
_ASSEMBLED_ENGINE_ROOT_REL: Final[str] = "lib/apothem"

#: The hook-event block, mirrored from the engine's claude_code
#: ``settings.json`` template. Each entry is a dispatch-routable event the
#: bash bootstrap stub (``hooks/lib/bootstrap.sh``) can drive: the stub
#: self-locates a CPython interpreter and execs ``hooks/dispatch.py`` with the
#: event name and, where the event emits a Markdown context, the message file's
#: full path. Conformity-gate entries from ``settings.json``
#: (``gate.py --hook``) are intentionally NOT mirrored here: the bootstrap stub
#: drives only the dispatcher, and the gate's user-scope default applies under
#: a harness root (``~/.claude`` / ``~/.codex``), not a plugin-alone project
#: write — wiring it plugin-alone would require an engine install. The per-event
#: timeouts and matchers track the ``settings.json`` block so the plugin-alone
#: and engine-install postures stay coherent. ``PreCompact`` and ``PostCompact``
#: are not registered on Claude Code surfaces: Claude Code discards both events'
#: ``systemMessage`` and accepts no ``additionalContext`` from them, so the
#: post-compaction recovery context travels on ``SessionStart`` with
#: ``source: compact`` instead. Shell guards match ``Bash|PowerShell`` so the
#: PowerShell tool, where enabled, is covered too.
#:
#: Each tuple is ``(event_name, matcher, timeout_seconds, message_basename)``;
#: ``message_basename`` is ``None`` for events the dispatcher handles without a
#: Markdown context (``SessionStart`` runs the session-start bootstrap directly).
_PLUGIN_HOOK_ENTRIES: Final[tuple[tuple[str, str, int, str | None], ...]] = (
    ("SessionStart", "*", 30, None),
    ("PreToolUse", "Write", 10, "pretooluse-write"),
    ("PreToolUse", "Write", 10, "pretooluse-write-header-guard"),
    ("PreToolUse", "Write", 10, "pretooluse-write-plan-guard"),
    ("PreToolUse", "Write", 10, "pretooluse-dependency-guard"),
    ("PreToolUse", "Write", 10, "pretooluse-eval-guard"),
    ("PreToolUse", "Edit", 10, "pretooluse-edit"),
    ("PreToolUse", "Edit", 10, "pretooluse-edit-header-guard"),
    ("PreToolUse", "Edit", 10, "pretooluse-write-plan-guard"),
    ("PreToolUse", "Edit", 10, "pretooluse-dependency-guard"),
    ("PreToolUse", "Edit", 10, "pretooluse-eval-guard"),
    ("PreToolUse", "NotebookEdit", 10, "pretooluse-notebookedit"),
    ("PreToolUse", "NotebookEdit", 10, "pretooluse-write-plan-guard"),
    ("PreToolUse", "Bash|PowerShell", 10, "pretooluse-bash"),
    ("PreToolUse", "Bash|PowerShell", 10, "pretooluse-bash-plan-guard"),
    ("PreToolUse", "Bash|PowerShell", 10, "pretooluse-eval-guard"),
    ("PreToolUse", "AskUserQuestion", 10, "pretooluse-askuserquestion-recommended"),
    ("PostToolUse", "*", 10, "posttooluse-proactive-compaction"),
    ("Stop", "*", 60, "stop"),
)

#: The thin alias shim re-exporting the engine's public submodules.
_SHIM_BODY: Final[str] = '''# SPDX-License-Identifier: MIT

"""Thin alias shim re-exporting the bundled apothem engine's public API.

Importing ``apothem_lib`` makes the engine's public submodules reachable
under one flat namespace (``apothem_lib.profile``, ``apothem_lib.adapters``,
...) without requiring callers to know the bundled package layout.
"""

from __future__ import annotations

from apothem import __version__
from apothem import harnesses as adapters
from apothem.lib import profile, propagation, reporter

__all__ = [
    "__version__",
    "adapters",
    "profile",
    "propagation",
    "reporter",
]
'''


class PluginAssemblyError(RuntimeError):
    """Raised when the plugin source tree cannot be assembled.

    The message names the offending path so the caller can diagnose a
    malformed source (e.g. a missing catalog directory). The assembler
    never silently skips a malformed input.
    """


def _version_from_pyproject() -> str | None:
    """Read ``[project].version`` from the repo's ``pyproject.toml`` when present.

    The repo's own manifest must track the authoritative in-tree version
    rather than the version of whatever copy is installed in site-packages
    (an editable install can be stale). Walks upward from this module to the
    nearest ``pyproject.toml``.

    Returns:
        The declared version, or ``None`` when no ``pyproject.toml`` is found
        or it declares no project version.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "pyproject.toml"
        if not candidate.is_file():
            continue
        text = candidate.read_text(encoding="utf-8")
        match = re.search(
            r"^\s*version\s*=\s*[\"']([^\"']+)[\"']", text, flags=re.MULTILINE
        )
        return match.group(1) if match else None
    return None


def _resolve_version(version: str | None) -> str:
    """Resolve the manifest version from the authoritative source.

    Precedence: an explicit argument, then the repo's ``pyproject.toml``,
    then the installed ``apothem.__version__`` as a last resort.

    Args:
        version: Explicit version, or ``None`` to resolve automatically.

    Returns:
        A ``MAJOR.MINOR.PATCH`` SemVer string.
    """
    if version is not None:
        return version
    declared = _version_from_pyproject()
    if declared is not None:
        return declared
    from apothem import __version__

    return __version__


def _enumerate_members(catalog_root: Path) -> dict[str, list[str]]:
    """Enumerate catalog members under ``catalog_root``.

    Skills are directories carrying a ``SKILL.md`` entry point (id = dirname).
    Agents, commands, and rules are flat ``*.md`` files (id = stem). Hooks are
    the hook message ``*.md`` files (id = stem). ``README.md`` and
    ``AGENTS.md`` index files are excluded — they are documentation, not
    catalog members.

    Args:
        catalog_root: The apothem source package directory.

    Returns:
        A mapping of member kind to a sorted list of member ids.

    Raises:
        PluginAssemblyError: When a required catalog directory is absent.
    """

    def _require_dir(rel: Path) -> Path:
        path = catalog_root / rel
        if not path.is_dir():
            raise PluginAssemblyError(f"required catalog directory missing: {path}")
        return path

    skills_dir = _require_dir(Path("skills"))
    skills = sorted(
        child.name
        for child in skills_dir.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    )

    def _markdown_stems(rel: Path) -> list[str]:
        directory = _require_dir(rel)
        return sorted(
            md.stem
            for md in directory.glob("*.md")
            if md.name not in _CATALOG_DOC_FILES
        )

    return {
        "skills": skills,
        "agents": _markdown_stems(Path("agents")),
        "commands": _markdown_stems(Path("commands")),
        "rules": _markdown_stems(Path("rules")),
        "hooks": _markdown_stems(_HOOK_MESSAGES_REL),
    }


def build_plugin_manifest(
    catalog_root: Path,
    *,
    version: str | None = None,
    catalog_prefix: str = "./",
    address_default_command_dir: bool = False,
) -> dict[str, object]:
    """Build a Claude Code plugin manifest dict from the apothem catalog.

    Enumerates every catalog member under ``catalog_root`` and assembles a
    manifest conforming to ``plugin.schema.json``. Commands and agents are
    declared as explicit file paths so the documentation files beside them
    are never registered as components; skills are declared as the skills
    directory (each immediate child carries a ``SKILL.md`` entry point).
    Rules and hook message contexts are engine cohorts consumed by the
    apothem materializers, not plugin components, so they carry no manifest
    field. Output styles carry none either: the assembled tree ships them in
    the default ``output-styles/`` folder Claude Code scans when the manifest
    sets no ``outputStyles`` key. Component arrays are sorted for determinism:
    the same catalog always yields the same manifest.

    Args:
        catalog_root: The apothem source package directory (the dir holding
            ``skills/``, ``agents/``, ``commands/``, ``rules/``, ``hooks/``).
        version: Explicit SemVer string, or ``None`` to resolve from
            ``pyproject.toml`` / ``apothem.__version__``.
        catalog_prefix: Plugin-root-relative prefix of the catalog
            directories, beginning with ``./`` — ``./`` when the catalog
            sits at the plugin root (the assembled tree), or
            ``./src/apothem/`` when the repository root is the plugin root.
        address_default_command_dir: When ``True``, prepend the plugin-root
            default ``./commands/`` directory to the ``commands`` array. The
            repository root is simultaneously this Claude Code plugin's root
            and the Gemini / Qwen extension root, so a bare ``./commands/``
            (holding the extensions' TOML passthrough command, not a Claude
            ``*.md`` command) sits at the plugin root. Claude Code v2.1.140+
            flags that default folder as "ignored" unless the manifest
            addresses it explicitly; listing it — the folder holds no
            ``*.md``, so no Claude command loads from it — suppresses the
            note while the explicit nested ``commands`` paths stay
            authoritative. Set ``True`` only when ``catalog_prefix`` is
            nested (the repository-root manifest); the assembled tree's
            commands already point into its own ``./commands/`` and need no
            extra entry.

    Returns:
        A manifest dict validating against ``plugin.schema.json``.

    Raises:
        PluginAssemblyError: When a required catalog directory is absent.
        jsonschema.ValidationError: When the assembled manifest does not
            conform to the plugin schema.
    """
    members = _enumerate_members(catalog_root)
    command_paths = sorted(
        f"{catalog_prefix}commands/{stem}.md" for stem in members["commands"]
    )
    if address_default_command_dir:
        command_paths = ["./commands/", *command_paths]
    engine_root_rel = _engine_root_rel_for(catalog_prefix)
    manifest: dict[str, object] = {
        "name": PLUGIN_NAME,
        "displayName": PLUGIN_DISPLAY_NAME,
        "version": _resolve_version(version),
        "description": PLUGIN_DESCRIPTION,
        "author": dict(PLUGIN_AUTHOR),
        "homepage": PLUGIN_HOMEPAGE,
        "repository": PLUGIN_REPOSITORY,
        "license": PLUGIN_LICENSE,
        "keywords": list(PLUGIN_KEYWORDS),
        **PLUGIN_LISTING_URLS,
        "commands": command_paths,
        "agents": sorted(
            f"{catalog_prefix}agents/{stem}.md" for stem in members["agents"]
        ),
        "skills": [f"{catalog_prefix}skills/"],
        "hooks": f"./{engine_root_rel}/hooks/hooks.json",
    }
    _validate_manifest(manifest)
    return manifest


def _engine_root_rel_for(catalog_prefix: str) -> str:
    """Map a catalog prefix to its plugin-root-relative engine prefix.

    The catalog directories and the engine sit at distinct locations in the
    two supported layouts:

    * Assembled tree (``catalog_prefix == "./"``): the catalog is at the
      plugin root, but the verbatim engine copy lives under ``lib/apothem``.
    * Repository-root manifest (``catalog_prefix == "./src/apothem/"``): the
      catalog and the engine share the ``src/apothem`` prefix.

    Args:
        catalog_prefix: The plugin-root-relative catalog prefix.

    Returns:
        The plugin-root-relative engine prefix (no leading ``./``, no
        trailing slash).
    """
    if catalog_prefix == "./":
        return _ASSEMBLED_ENGINE_ROOT_REL
    return catalog_prefix.strip("./")


def _bootstrap_command(engine_root_rel: str, suffix: str) -> str:
    """Render the ``command`` string for one plugin hook entry.

    The command runs the bash bootstrap stub under the plugin install
    directory (``${CLAUDE_PLUGIN_ROOT}``, which Claude Code substitutes and
    exports) through an explicit ``bash`` invocation. Invoking the interpreter
    by name, rather than executing the stub path, keeps the hook independent of
    the file's executable bit: a git checkout or a marketplace copy preserves
    the tracked mode, and a stub tracked without ``+x`` would otherwise exit 126
    on every call. The stub self-locates a CPython >= 3.10 interpreter and execs
    ``hooks/dispatch.py``; no engine install or install-time ``${PYTHON_BIN}``
    substitution is required.

    Args:
        engine_root_rel: Plugin-root-relative engine prefix
            (``lib/apothem`` for the assembled tree, ``src/apothem`` for the
            repository-root manifest).
        suffix: The argument string appended after the stub path: the event
            name plus, where present, the quoted message-file path.

    Returns:
        The ``command`` string for one ``hooks.json`` command entry.
    """
    stub = f"${{CLAUDE_PLUGIN_ROOT}}/{engine_root_rel}/hooks/lib/bootstrap.sh"
    return f'bash "{stub}" {suffix}'


def _entry_command_block(
    engine_root_rel: str, event: str, timeout: int, message: str | None
) -> list[dict[str, object]]:
    """Return the single command hook for one plugin hook entry.

    Each dispatch-routable entry is registered exactly once, in shell form with
    Claude Code's default hook shell (``sh`` on macOS and Linux, Git Bash on
    Windows). A paired ``shell: powershell`` registration is deliberately not
    emitted: Claude Code offers no per-platform condition on a hook, so a pair
    runs twice wherever both shells exist and reports a hook error on every call
    wherever one is missing. Windows hosts without Git for Windows use the
    engine install (``apothem install --harness claude-code``), whose hooks run
    in exec form against an install-resolved interpreter and need no shell.

    Args:
        engine_root_rel: Plugin-root-relative engine prefix.
        event: The hook event name (e.g. ``PreToolUse``).
        timeout: Per-entry timeout in seconds, mirrored from the engine's
            ``settings.json`` block.
        message: The message-file basename (without ``.md``), or ``None`` for
            events the dispatcher handles without a Markdown context.

    Returns:
        A one-element list holding the command-hook dict.
    """
    if message is None:
        suffix = event
    else:
        msg_rel = f"{engine_root_rel}/hooks/messages/{message}.md"
        suffix = f'{event} "${{CLAUDE_PLUGIN_ROOT}}/{msg_rel}"'
    return [
        {
            "type": "command",
            "command": _bootstrap_command(engine_root_rel, suffix),
            "timeout": timeout,
        }
    ]


def build_plugin_hooks_json(engine_root_rel: str) -> dict[str, object]:
    """Build a Claude Code ``hooks.json`` mirroring the engine hook block.

    Produces the plugin-alone hook configuration: a ``hooks`` map keyed by
    event name, each event carrying matcher-grouped command blocks. Every
    command drives the bash bootstrap stub under ``${CLAUDE_PLUGIN_ROOT}``
    (one entry per dispatch-routable hook), so the conformity nudges, the
    session bootstrap (which also carries the post-compaction recovery context
    on ``source: compact``) and the stop handler fire when the plugin is
    installed alone — without an apothem
    engine install or the install-time ``${PYTHON_BIN}`` / ``${HARNESS_ROOT}``
    substitution the engine ``settings.json`` relies on.

    The event set, matchers, and per-event timeouts mirror the engine's
    claude_code ``settings.json`` block, minus the ``gate.py --hook``
    conformity entries (the bootstrap stub drives only the dispatcher, and the
    gate's scope default targets a harness root, not a plugin-alone project
    write — see ``_PLUGIN_HOOK_ENTRIES``).

    Args:
        engine_root_rel: Plugin-root-relative engine prefix —
            ``lib/apothem`` for the assembled tree (``catalog_prefix="./"``),
            or ``src/apothem`` for the repository-root manifest
            (``catalog_prefix="./src/apothem/"``).

    Returns:
        A ``hooks.json`` dict carrying the ``hooks`` event map.
    """
    # Accumulate one command-list per (event, matcher) so consecutive entries
    # sharing a matcher (e.g. the three Write guards) collapse into a single
    # matcher group with an ordered command list — mirroring the engine
    # ``settings.json`` grouping. ``dict`` preserves first-seen order, so the
    # emitted event and matcher ordering is deterministic across runs.
    accumulators: dict[tuple[str, str], list[dict[str, object]]] = {}
    for event, matcher, timeout, message in _PLUGIN_HOOK_ENTRIES:
        commands = accumulators.setdefault((event, matcher), [])
        commands.extend(_entry_command_block(engine_root_rel, event, timeout, message))
    events: dict[str, list[dict[str, object]]] = {}
    for (event, matcher), commands in accumulators.items():
        events.setdefault(event, []).append({"matcher": matcher, "hooks": commands})
    return {"hooks": events}


def _plugin_schema_path() -> Path:
    """Return the path to the bundled ``plugin.schema.json`` fixture."""
    return Path(__file__).resolve().parent.parent / "schemas" / "plugin.schema.json"


def _validate_manifest(manifest: dict[str, object]) -> None:
    """Validate a manifest against ``plugin.schema.json``.

    Args:
        manifest: The manifest dict to validate.

    Raises:
        jsonschema.ValidationError: When the manifest does not conform.
    """
    schema = json.loads(_plugin_schema_path().read_text(encoding="utf-8"))
    jsonschema.validate(instance=manifest, schema=schema)


def _translate_catalog_skills(skills_dir: Path) -> None:
    """Rewrite each catalog ``SKILL.md`` in Claude Code's frontmatter spelling.

    Uses the same translation as the claude_code install's ``native_skills``
    mode (imported lazily: ``lib`` does not depend on the harness package at
    import time). Files are rewritten with ``\\n`` newlines so the committed
    tree stays byte-identical across platforms.
    """
    from apothem.harnesses._shared.install_driver_converters import (
        claude_code_skill_text,
    )

    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        translated = claude_code_skill_text(text)
        if translated != text:
            skill_md.write_text(translated, encoding="utf-8", newline="\n")


def assemble_plugin_tree(src_root: Path, dest_root: Path) -> Path:
    """Materialize the canonical plugin source tree at ``dest_root``.

    Copies the apothem engine verbatim into ``lib/apothem``,
    writes the ``apothem_lib`` re-export shim, ensures the ``_vendor``
    directory exists, copies the catalog directories, and writes the
    generated ``plugin.json``. The operation is idempotent: re-running
    overwrites the engine copy, shim, and catalog cleanly.

    Args:
        src_root: The apothem source package directory.
        dest_root: The plugin root to populate.

    Returns:
        ``dest_root``.

    Raises:
        PluginAssemblyError: When ``src_root`` is not a directory or a
            required catalog directory is absent.
    """
    if not src_root.is_dir():
        raise PluginAssemblyError(f"source package directory missing: {src_root}")

    # Build the manifest first so a malformed source fails before any write.
    manifest = build_plugin_manifest(src_root)

    dest_root.mkdir(parents=True, exist_ok=True)

    # 1. Engine copy: lib/apothem (verbatim, pruned of caches).
    lib_dir = dest_root / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    engine_dest = lib_dir / "apothem"
    if engine_dest.exists():
        shutil.rmtree(engine_dest)
    shutil.copytree(
        src_root,
        engine_dest,
        ignore=shutil.ignore_patterns(*_COPY_IGNORE),
    )

    # 2. Vendored deps: copy src _vendor if present, else create empty .keep.
    vendor_dest = engine_dest / "_vendor"
    src_vendor = src_root / "_vendor"
    if src_vendor.is_dir():
        if vendor_dest.exists():
            shutil.rmtree(vendor_dest)
        shutil.copytree(
            src_vendor,
            vendor_dest,
            ignore=shutil.ignore_patterns(*_COPY_IGNORE),
        )
    else:
        vendor_dest.mkdir(parents=True, exist_ok=True)
        (vendor_dest / ".keep").write_text("", encoding="utf-8")

    # 3. Alias shim: lib/apothem_lib.py.
    #    newline="\n" on every generated file: the assembled tree is committed
    #    and held to this generator by a drift gate, so the output has to be
    #    byte-identical across platforms. Without it Python translates "\n" to
    #    os.linesep, git normalizes the committed bytes to LF, and a Windows
    #    re-assembly then reports drift against a clone the author cannot
    #    reproduce. Copied files are unaffected — they carry source bytes.
    (lib_dir / "apothem_lib.py").write_text(_SHIM_BODY, encoding="utf-8", newline="\n")

    # 4. Catalog dirs: skills/agents/commands/rules/output-styles copied to plugin root.
    #    The catalog directories become harness DISCOVERY directories at the
    #    plugin root, where every top-level entry is interpreted as a component.
    #    ``build_plugin_manifest`` already omits the directory READMEs from the
    #    manifest arrays, but Claude Code also scans the default component
    #    folders directly, so a copied ``README.md`` is still loaded — and
    #    reported as a frontmatter-less component. Prune the same doc set the
    #    manifest omits, at the catalog root only: a README nested inside a
    #    skill directory is that skill's own reference material, not a stray.
    for name in _CATALOG_DIRS:
        src_dir = src_root / name
        if not src_dir.is_dir():
            raise PluginAssemblyError(f"required catalog directory missing: {src_dir}")
        dest_dir = dest_root / name
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(
            src_dir,
            dest_dir,
            ignore=shutil.ignore_patterns(*_COPY_IGNORE),
        )
        for doc_name in _CATALOG_DOC_FILES:
            (dest_dir / doc_name).unlink(missing_ok=True)

    # 4b. Skill frontmatter: rename source keys to the spelling Claude Code
    #     reads (userInvocable -> user-invocable), as the claude_code install
    #     does. Only the plugin-root catalog changes; the lib/apothem engine
    #     copy keeps the source form.
    _translate_catalog_skills(dest_root / "skills")

    # 5. Hook message catalog: hooks/messages copied to plugin-root hooks/.
    hooks_src = src_root / _HOOK_MESSAGES_REL
    if not hooks_src.is_dir():
        raise PluginAssemblyError(f"required catalog directory missing: {hooks_src}")
    hooks_dest = dest_root / "hooks"
    if hooks_dest.exists():
        shutil.rmtree(hooks_dest)
    shutil.copytree(
        hooks_src,
        hooks_dest,
        ignore=shutil.ignore_patterns(*_COPY_IGNORE),
    )

    # 6. Plugin hooks.json: written beside the verbatim engine copy so the
    #    bootstrap stubs, dispatcher, and message catalog all resolve under the
    #    same ``lib/apothem`` prefix the manifest's ``hooks`` field points at.
    #    The engine copy (step 1) already materialized ``lib/apothem/hooks/``,
    #    so the directory exists.
    hooks_json = build_plugin_hooks_json(_ASSEMBLED_ENGINE_ROOT_REL)
    engine_hooks_dir = engine_dest / "hooks"
    (engine_hooks_dir / "hooks.json").write_text(
        json.dumps(hooks_json, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # 7. Manifest: .claude-plugin/plugin.json.
    plugin_meta_dir = dest_root / ".claude-plugin"
    plugin_meta_dir.mkdir(parents=True, exist_ok=True)
    (plugin_meta_dir / "plugin.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return dest_root
