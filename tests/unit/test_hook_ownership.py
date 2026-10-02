# SPDX-License-Identifier: MIT

"""Apothem owns only the hook handlers that run its own installed scripts.

Hook ownership used to be decided by substring: any handler mentioning
``hooks/dispatch.py`` or ``conformity/gate.py`` anywhere was treated as
Apothem's and replaced on install and deleted on uninstall, taking operator
hooks in their own projects with it. Ownership is now the materialized path
under the harness root (or Apothem's module spellings), so a foreign
``/other/hooks/dispatch.py`` survives both directions.
"""

from __future__ import annotations

import json
from pathlib import Path

from apothem.harnesses._shared import install_driver

_FOREIGN_DISPATCH = {
    "type": "command",
    "command": "python3",
    "args": ["/home/me/myproj/hooks/dispatch.py", "--audit"],
}
_FOREIGN_GATE = {
    "type": "command",
    "command": "python3 /srv/tools/conformity/gate.py --strict",
}
_FOREIGN_SCRIPT = {"type": "command", "command": "/usr/local/bin/my-guard.sh"}


def _seed(harness_root: Path, legacy_handler: dict[str, object]) -> Path:
    harness_root.mkdir(parents=True)
    settings = harness_root / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Write",
                            "hooks": [
                                _FOREIGN_DISPATCH,
                                _FOREIGN_GATE,
                                _FOREIGN_SCRIPT,
                                legacy_handler,
                            ],
                        }
                    ]
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return settings


def _write_handlers(settings: Path) -> list[object]:
    data = json.loads(settings.read_text(encoding="utf-8"))
    for entry in data.get("hooks", {}).get("PreToolUse", []):
        if entry.get("matcher") == "Write":
            return list(entry["hooks"])
    return []


def test_foreign_dispatch_hooks_survive_install_and_uninstall(tmp_path: Path) -> None:
    harness_root = tmp_path / ".claude"
    # A handler from an older Apothem layout under this harness root: still
    # Apothem's, so install replaces it.
    legacy = {
        "type": "command",
        "command": "python3",
        "args": [f"{harness_root.resolve().as_posix()}/apothem/hooks/dispatch.py"],
    }
    settings = _seed(harness_root, legacy)

    install_driver.run_install("claude_code", harness_root=harness_root)
    installed = _write_handlers(settings)
    for foreign in (_FOREIGN_DISPATCH, _FOREIGN_GATE, _FOREIGN_SCRIPT):
        assert foreign in installed
    assert legacy not in installed

    install_driver.run_uninstall("claude_code", harness_root=harness_root)
    remaining = _write_handlers(settings)
    assert remaining == [_FOREIGN_DISPATCH, _FOREIGN_GATE, _FOREIGN_SCRIPT]


def test_handler_recognition_is_scoped_to_the_harness_root(tmp_path: Path) -> None:
    root = tmp_path / ".claude"
    posix = root.resolve().as_posix()
    ours = [
        {"command": "py", "args": [f"{posix}/.apothem/support/hooks/dispatch.py"]},
        {"command": f'python3 "{posix}/hooks/dispatch.py" Stop'},
        {"command": "py", "args": [f"{posix}/.apothem/support/conformity/gate.py"]},
        {"command": "python -m apothem.hooks.dispatch SessionStart"},
        {
            "command": "py",
            "args": ["${HARNESS_ROOT}/.apothem/support/hooks/dispatch.py"],
        },
    ]
    theirs = [_FOREIGN_DISPATCH, _FOREIGN_GATE, _FOREIGN_SCRIPT]
    for handler in ours:
        assert install_driver._is_apothem_hook(handler, harness_root=root), handler
    for handler in theirs:
        assert not install_driver._is_apothem_hook(handler, harness_root=root), handler
