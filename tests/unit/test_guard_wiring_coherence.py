# SPDX-License-Identifier: MIT

"""Coherence guard: every shipped PreToolUse guard message must be wired.

The tool-matcher -> guard-message mapping is hand-duplicated across five
config sources with no single source of truth:

1. ``plugin_tree._PLUGIN_HOOK_ENTRIES`` -> generates the committed
   ``src/apothem/hooks/hooks.json`` (the engine catalog the plugin-alone and
   the gemini_cli / opencode / hermes / open_claw / antigravity engine-copy
   harnesses all inherit). The committed file is bound to the generator by
   ``test_plugin_tree.test_committed_repo_hooks_json_matches_generator``.
2. ``harnesses/claude_code/templates/settings.json`` -> claude_code's installed
   config.
3. ``harnesses/codex/templates/hooks.json`` -> codex.
4. ``harnesses/qwen_code/materializer._qwen_hooks`` -> qwen_code.

That hand-duplication is what let ``pretooluse-eval-guard`` and
``pretooluse-dependency-guard`` ship under ``hooks/messages/`` (and be
documented as active in the hooks README + the docs site) while being wired in
*none* of the five sources — so the advertised advisories fired nowhere. These
tests bind the four independent sources to the committed ``hooks.json`` so a
future guard cannot drift in shipped-but-unwired the same way.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from apothem.harnesses.qwen_code.materializer import _qwen_hooks

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src" / "apothem"
_MESSAGES_DIR = _SRC / "hooks" / "messages"
_HOOKS_JSON = _SRC / "hooks" / "hooks.json"
_SETTINGS_JSON = _SRC / "harnesses" / "claude_code" / "templates" / "settings.json"
_CODEX_HOOKS = _SRC / "harnesses" / "codex" / "templates" / "hooks.json"

#: Message files under ``hooks/messages/`` that are intentionally NOT wired as a
#: standalone ``hooks.json`` entry. ``pretooluse-conformity`` is a sub-context
#: the Write / Edit guards reference in their own bodies; the mechanical check
#: ships as the ``gate.py --hook`` entry in ``settings.json``, never as its own
#: dispatch-routed Markdown context. Adding a guard here documents a deliberate
#: decision not to fire it; absence here means it must be wired.
_UNWIRED_BY_DESIGN = frozenset({"pretooluse-conformity"})

#: A guard message basename embedded anywhere in a hook command / args entry.
_MESSAGE_RE = re.compile(r"pretooluse-[a-z0-9-]+")


def _entry_message(entry: dict[str, object]) -> str | None:
    """Return the ``pretooluse-*`` guard basename a hook entry dispatches, or None.

    Handles both config shapes: the command-string form (``hooks.json`` /
    codex / qwen, where the basename is a token of ``command``) and the
    args-array form (``settings.json``, where the dispatcher message is the
    final ``args`` element). The ``gate.py --hook`` conformity entries carry no
    ``pretooluse-*`` token and resolve to None, so they are skipped.
    """
    command = entry.get("command")
    args = entry.get("args")
    text = command if isinstance(command, str) else ""
    if isinstance(args, list):
        text = f"{text} {' '.join(str(a) for a in args)}"
    match = _MESSAGE_RE.search(text)
    return match.group(0) if match else None


def _pretooluse_guard_sets(hooks_config: dict[str, object]) -> dict[str, set[str]]:
    """Map each PreToolUse matcher to the set of guard basenames it dispatches."""
    events = hooks_config["hooks"]
    assert isinstance(events, dict)
    result: dict[str, set[str]] = {}
    for group in events.get("PreToolUse", []):
        assert isinstance(group, dict)
        inner = group["hooks"]
        assert isinstance(inner, list)
        names = {_entry_message(h) for h in inner if isinstance(h, dict)}
        result[str(group["matcher"])] = {n for n in names if n}
    return result


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_shipped_guard_message_is_wired() -> None:
    """Every ``pretooluse-*`` guard message file is wired in the committed
    ``hooks.json`` (or explicitly allow-listed as unwired-by-design).

    This is the exact regression that shipped ``pretooluse-eval-guard`` and
    ``pretooluse-dependency-guard`` dead: a guard message existed and was
    documented active, but no matcher dispatched it.
    """
    shipped = {p.stem for p in _MESSAGES_DIR.glob("pretooluse-*.md")}
    wired: set[str] = set()
    for names in _pretooluse_guard_sets(_load(_HOOKS_JSON)).values():
        wired |= names
    missing = shipped - wired - _UNWIRED_BY_DESIGN
    assert not missing, (
        f"guard message(s) ship under hooks/messages/ but are dispatched by no "
        f"hooks.json PreToolUse matcher: {sorted(missing)}. Wire them in "
        f"plugin_tree._PLUGIN_HOOK_ENTRIES (then regenerate hooks.json) and the "
        f"per-harness configs, or add them to _UNWIRED_BY_DESIGN with a reason."
    )


def test_settings_json_guard_set_matches_committed_hooks_json() -> None:
    """claude_code's installed settings.json carries the same PreToolUse guard
    set, per matcher, as the committed engine hooks.json (the gate.py entries
    carry no guard token and are ignored)."""
    hooks = _pretooluse_guard_sets(_load(_HOOKS_JSON))
    settings = _pretooluse_guard_sets(_load(_SETTINGS_JSON))
    assert settings == hooks, (
        "claude_code settings.json PreToolUse guard wiring drifted from the "
        f"committed hooks.json.\n  settings.json: {settings}\n  hooks.json:    {hooks}"
    )


def test_codex_guard_set_matches_committed_hooks_json() -> None:
    """codex folds Write + Edit into one ``Edit|Write|apply_patch`` matcher using
    the ``pretooluse-write`` messages; its write and Bash guard sets must equal
    the engine hooks.json Write and Bash sets."""
    hooks = _pretooluse_guard_sets(_load(_HOOKS_JSON))
    codex = _pretooluse_guard_sets(_load(_CODEX_HOOKS))
    assert codex["Edit|Write|apply_patch"] == hooks["Write"], (
        f"codex write-matcher guards drifted from hooks.json Write.\n"
        f"  codex: {codex['Edit|Write|apply_patch']}\n  hooks.json: {hooks['Write']}"
    )
    assert codex["Bash"] == hooks["Bash|PowerShell"], (
        f"codex Bash guards drifted from hooks.json Bash|PowerShell.\n"
        f"  codex: {codex['Bash']}\n  hooks.json: {hooks['Bash|PowerShell']}"
    )


def test_qwen_guard_set_matches_committed_hooks_json() -> None:
    """qwen folds WriteFile + Edit into one ``WriteFile|Edit`` matcher; its write
    and Bash guard sets must equal the engine hooks.json Write and Bash sets."""
    hooks = _pretooluse_guard_sets(_load(_HOOKS_JSON))
    # The guard sets are independent of the resolved interpreter, so any
    # python_bin placeholder exercises the same matcher structure.
    qwen = _pretooluse_guard_sets({"hooks": _qwen_hooks("python3")})
    assert qwen["WriteFile|Edit"] == hooks["Write"], (
        f"qwen write-matcher guards drifted from hooks.json Write.\n"
        f"  qwen: {qwen['WriteFile|Edit']}\n  hooks.json: {hooks['Write']}"
    )
    assert qwen["^run_shell_command$"] == hooks["Bash|PowerShell"], (
        f"qwen shell guards drifted from hooks.json Bash|PowerShell.\n"
        f"  qwen: {qwen['^run_shell_command$']}\n  hooks.json: {hooks['Bash|PowerShell']}"
    )


def test_supply_chain_and_eval_guards_fire_on_their_scopes() -> None:
    """Regression pin for the original defect: the supply-chain guard fires on
    Write/Edit and the dynamic-eval guard on Write/Edit/Bash, in the committed
    engine hooks.json."""
    hooks = _pretooluse_guard_sets(_load(_HOOKS_JSON))
    assert "pretooluse-dependency-guard" in hooks["Write"]
    assert "pretooluse-dependency-guard" in hooks["Edit"]
    assert "pretooluse-dependency-guard" not in hooks["Bash|PowerShell"]
    assert "pretooluse-eval-guard" in hooks["Write"]
    assert "pretooluse-eval-guard" in hooks["Edit"]
    assert "pretooluse-eval-guard" in hooks["Bash|PowerShell"]
