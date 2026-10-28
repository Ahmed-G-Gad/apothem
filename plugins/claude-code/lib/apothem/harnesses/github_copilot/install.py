# SPDX-License-Identifier: MIT

"""Install logic for the github-copilot harness adapter.

Materializes the apothem GitHub Copilot instructions surface into the
operator-supplied project root. The GA repo-wide instructions file is
``<project>/.github/copilot-instructions.md`` per
https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot.
User-scope is unavailable — Copilot's user-level settings live in IDE
state (VS Code / JetBrains UI), not a file path the harness can write.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``github_copilot``
key (a ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/.github/copilot-instructions.md`` and an apothem-owned
``copilot_agents`` operation targeting ``${PROJECT_ROOT}/.github/agents/``, an
apothem-owned support tree for the hook scripts at
``${PROJECT_ROOT}/.apothem/support/github-copilot/hooks/`` and an apothem-owned
``native_hooks`` operation targeting ``${PROJECT_ROOT}/.github/hooks/apothem.json``,
preceded by the user-level entries that
install the skills in ``~/.agents/skills/`` and the rules and templates corpus in
``~/.config/apothem/``) and applied by the
shared driver at ``apothem.harnesses._shared.install_driver``. The
``${PROJECT_ROOT}`` placeholder is substituted with the operator-supplied
``--project <path>`` value the CLI threads through; absence of
``--project`` is rejected upstream at ``apothem.cli._materialize`` via the
``requires_project`` opt-in. The ``${USER_HOME}`` placeholder is the user home, and
the folders under it are shared with every other install that names them.

The hook registration is the sessionStart bootstrap and the postToolUse
proactive-compaction tracker, the two events whose ``additionalContext`` Copilot
hands to the model (https://docs.github.com/en/copilot/reference/hooks-reference,
retrieved 2026-10-28). Each entry carries a ``bash`` and a ``powershell`` command
that run the dispatcher with the install-resolved interpreter, the
``${PYTHON_BIN}`` token, which :func:`python_bin_tokens` resolves once, before
anything is written, so a host with no usable CPython aborts the install with
nothing on disk. The update inherits the same rendering. The uninstall renders
without that token, so it finds Apothem's entries by the dispatcher their command
runs, not by the file's text.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_project_scope_plan,
    python_bin_tokens,
)

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "github_copilot"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message=(
        "github_copilot adapter requires --project <path>; CLI must thread it through"
    ),
    content_tokens=python_bin_tokens,
)

plan = make_project_scope_plan(_HARNESS_NAME)
