# SPDX-License-Identifier: MIT

"""Install logic for the cursor harness adapter.

Materializes the apothem Cursor rules surface into the operator-supplied
project root. Cursor's canonical user-facing rules surface is the
project-scope MDC ruleset at ``<project>/.cursor/rules/*.mdc`` (per
https://cursor.com/docs/rules). The legacy single-file
``~/.cursorrules`` target is excluded because Apothem targets the current
multi-file project rules surface.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``cursor`` key
(a ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/.cursor/rules/apothem-rules.mdc`` and an apothem-owned
``cursor_agents`` operation targeting ``${PROJECT_ROOT}/.cursor/agents/``, an
apothem-owned support tree for the hook scripts at
``${PROJECT_ROOT}/.apothem/support/cursor/hooks/`` and an operator-owned
``native_hooks`` operation targeting ``${PROJECT_ROOT}/.cursor/hooks.json``,
preceded by the user-level entries that
install the skills in ``~/.agents/skills/`` and the rules and templates corpus in
``~/.config/apothem/``) and applied by the
shared driver at ``apothem.harnesses._shared.install_driver``. The
``${PROJECT_ROOT}`` placeholder is substituted with the operator-supplied
``--project <path>`` value the CLI threads through; absence of
``--project`` is rejected upstream at ``apothem.cli._materialize`` via the
``requires_project`` opt-in. The ``${USER_HOME}`` placeholder is the user home, and
the folders under it are shared with every other install that names them.

The hook registration is the ``sessionStart`` bootstrap, the one hook version 1
registers (https://cursor.com/docs/hooks, retrieved 2026-10-28). Its command runs
the dispatcher with the install-resolved interpreter, the ``${PYTHON_BIN}`` token,
and the ``${CALL_OP}`` token that :func:`python_call_tokens` resolves with it:
``& `` on a Windows host, where Cursor's desktop app hands the command to
PowerShell, and nothing elsewhere. Both are resolved once, before anything is
written, so a host with no usable CPython aborts the install with nothing on disk.
The update inherits the same rendering. The uninstall renders without those
tokens, so it finds Apothem's hook by the dispatcher its command runs, not by the
file's text. ``.cursor/hooks.json`` is the operator's file: the merge keeps their
entries and keys, and a file it cannot merge into without damage is refused.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_project_scope_plan,
    python_call_tokens,
)

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "cursor"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="cursor adapter requires --project <path>; CLI must thread it through",
    content_tokens=python_call_tokens,
)

plan = make_project_scope_plan(_HARNESS_NAME)
