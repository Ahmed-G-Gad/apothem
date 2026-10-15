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

The hook interpreter is resolved FIRST, before any tree is written, by
:func:`apothem.lib.python_resolver.resolve_python_bin`. The resolved absolute
path is substituted for the template's ``${PYTHON_BIN}`` placeholder while
``hooks.json`` is rendered, so each ``commandWindows`` entry runs a real
CPython rather than the ``py -3`` launcher. A resolution failure aborts the
install with nothing on disk. The POSIX ``command`` entries name ``python3``
and carry no placeholder, so they are unchanged.

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

from pathlib import Path
from typing import Any

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import MaterializationRun
from apothem.harnesses._shared.wrapper_factories import (
    make_plan_harness_root,
    make_user_scope_install,
)
from apothem.lib.python_resolver import resolve_python_bin

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "codex"

_base_install = make_user_scope_install(_HARNESS_NAME)

plan = make_plan_harness_root(_HARNESS_NAME)


def install(
    output_path: Path, profile: dict[str, Any], *, dry_run: bool = False
) -> MaterializationRun:
    """Materialize the profile into the codex harness root.

    Resolves the hook interpreter before anything is written, then runs the
    shared user-scope install with ``${PYTHON_BIN}`` substituted in every
    rendered template. With ``dry_run=True`` the preview shows the same resolved
    ``hooks.json`` and writes nothing. A resolution failure raises
    :class:`RuntimeError` and leaves the harness root untouched.
    """
    python_bin = resolve_python_bin().as_posix()
    with install_driver.content_tokens(PYTHON_BIN=python_bin):
        return _base_install(output_path, profile, dry_run=dry_run)
