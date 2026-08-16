# SPDX-License-Identifier: MIT

"""Install logic for the codex harness adapter.

Installs the Apothem convention surface into the OpenAI Codex CLI
harness target. Codex CLI reads ``$CODEX_HOME/AGENTS.md`` as the
vendor-canonical agent-instructions file and discovers lifecycle hooks
from ``$CODEX_HOME/hooks.json`` plus hook helpers under
``$CODEX_HOME/hooks/``. Agents are converted to
``$CODEX_HOME/agents/*.toml``. Skills and command prompts propagate to the
shared Codex skills root ``~/.agents/skills/``. Markdown rules and templates
live under ``~/.config/apothem/`` as support material because Codex reserves
``$CODEX_HOME/rules/`` for ``.rules`` execution-policy files.

Codex runtime configuration lives at ``$CODEX_HOME/config.toml`` and is
operator-owned; this adapter does not overwrite that file.

The adapter is user-scope: it propagates under the harness root resolved
as ``output_path.parent`` (``~/.codex/``). Its propagation contract is
declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``codex`` key
and applied by the shared driver at
``apothem.harnesses._shared.install_driver``. Drift between the
propagation contract and the on-disk install is impossible by
construction: the manifest IS the contract.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import (
    make_plan_harness_root,
    make_user_scope_install,
)

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "codex"

install = make_user_scope_install(_HARNESS_NAME)

plan = make_plan_harness_root(_HARNESS_NAME)
