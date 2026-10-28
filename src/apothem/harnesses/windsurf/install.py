# SPDX-License-Identifier: MIT

"""Install logic for the windsurf harness adapter.

Materializes the apothem Windsurf rules surface into the operator-supplied
project root. The windsurf harness rebranded to Devin Desktop (OTA
2026-06-02); its preferred workspace-rules surface is now the project-scope
multi-file format at ``<project>/.devin/rules/*.md`` (per
https://docs.devin.ai/desktop/cascade/memories), which TAKES
PRECEDENCE over the retained backward-compat fallback at
``<project>/.windsurf/rules/*.md``. Apothem writes the canonical target into
``.devin/rules/`` to avoid being silently shadowed. The harness slug stays
``windsurf``. The legacy single-file ``.windsurfrules`` target is excluded.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``windsurf`` key
(a ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/.devin/rules/apothem-rules.md`` and an apothem-owned
``devin_agents`` operation targeting ``${PROJECT_ROOT}/.devin/agents/``, an
apothem-owned support tree for the hook scripts at
``${PROJECT_ROOT}/.apothem/support/windsurf/hooks/`` and an operator-owned
key-merge of the hook registration into the local config file
``${PROJECT_ROOT}/.devin/config.local.json``,
preceded by the user-level entries that
install the skills in ``~/.agents/skills/`` and the rules and templates corpus in
``~/.config/apothem/``) and applied by the
shared driver at ``apothem.harnesses._shared.install_driver``. The
``${PROJECT_ROOT}`` placeholder is substituted with the operator-supplied
``--project <path>`` value the CLI threads through; absence of
``--project`` is rejected upstream at ``apothem.cli._materialize`` via the
``requires_project`` opt-in. The ``${USER_HOME}`` placeholder is the user home, and
the folders under it are shared with every other install that names them.

The hook registration is the SessionStart bootstrap and the PostToolUse
proactive-compaction tracker, the two events whose ``additionalContext`` Devin Local
hands to the model (https://docs.devin.ai/cli/extensibility/hooks/overview.md,
retrieved 2026-10-28). Each command runs the dispatcher with the install-resolved
interpreter, the ``${PYTHON_BIN}`` token, which :func:`python_bin_tokens` resolves
once, before anything is written, so a host with no usable CPython aborts the
install with nothing on disk. The update inherits the same rendering. The uninstall
renders without that token, so it finds Apothem's handlers by the dispatcher their
command runs, not by the file's text.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_project_scope_plan,
    python_bin_tokens,
)

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "windsurf"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="windsurf adapter requires --project <path>; CLI must thread it through",
    content_tokens=python_bin_tokens,
)

plan = make_project_scope_plan(_HARNESS_NAME)
