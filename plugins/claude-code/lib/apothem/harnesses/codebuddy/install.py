# SPDX-License-Identifier: MIT

"""Install logic for the codebuddy harness adapter.

Materializes the apothem CodeBuddy rules surface into the operator-supplied
project root. CodeBuddy's canonical rules surface is the project-scope
multi-file format at ``<project>/.codebuddy/rules/*.md`` (per
https://www.codebuddy.ai/docs/ide/Rules). The adapter writes a dedicated
``apothem-rules.md`` file so the operator's own rules files are never
clobbered. The ``CODEBUDDY.md`` memory file and ``.codebuddy/settings.json``
permissions/MCP surface are operator-owned and out of apothem's adapter
scope.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``codebuddy`` key
(an operator-owned ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/.codebuddy/rules/apothem-rules.md``, an apothem-owned
``codebuddy_agents`` operation targeting ``${PROJECT_ROOT}/.codebuddy/agents/``,
an apothem-owned support tree for the hook scripts at
``${PROJECT_ROOT}/.apothem/support/hooks/`` and an operator-owned key-merge of
the hook registration into the uncommitted ``${PROJECT_ROOT}/.codebuddy/settings.local.json``,
preceded by the user-level entries that
install the skills in ``~/.codebuddy/skills/`` and the rules and templates corpus in
``~/.config/apothem/``) and applied by the
shared driver at ``apothem.harnesses._shared.install_driver``. The
``${PROJECT_ROOT}`` placeholder is substituted with the operator-supplied
``--project <path>`` value the CLI threads through; absence of
``--project`` is rejected upstream at ``apothem.cli._materialize`` via the
``requires_project`` opt-in. The ``${USER_HOME}`` placeholder is the user home, and
the folders under it are shared with every other install that names them.

The hook registration is the SessionStart bootstrap and the PostToolUse
proactive-compaction tracker: the two events whose output CodeBuddy hands to the
model (https://www.codebuddy.ai/docs/cli/hooks, retrieved 2026-10-28). Each
command runs the dispatcher with the install-resolved interpreter, the
``${PYTHON_BIN}`` token, which :func:`python_bin_tokens` resolves once, before
anything is written, so a host with no usable CPython aborts the install with
nothing on disk. The update inherits the same rendering. CodeBuddy does not
hot-load an edited settings file; the operator restarts it and reviews the
entries in its ``/hooks`` panel (see
:mod:`apothem.lib.install_advisories`).
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_project_scope_plan,
    python_bin_tokens,
)

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "codebuddy"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="codebuddy adapter requires --project <path>; CLI must thread it through",
    content_tokens=python_bin_tokens,
)

plan = make_project_scope_plan(_HARNESS_NAME)
