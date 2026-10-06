# SPDX-License-Identifier: MIT

"""Apothem harness adapter for glm — project-scope backend-provider config.

GLM (Z.ai) is a **model backend**, not a first-party coding-agent tool: Z.ai
ships no native GLM coding CLI. GLM is the model an Anthropic-compatible or
OpenAI-compatible coding agent points at by setting backend environment
variables. The adapter therefore writes a provider configuration file —
``<project>/.apothem/providers/glm.toml`` — that records the Anthropic-compatible
and OpenAI-compatible base URLs, an auth-token placeholder, and
operator-configurable model-mapping placeholders so an operator can wire any
compatible agent to GLM. The file is materialized via ``write_text`` as an
operator-owned valid-TOML config: Apothem writes the template only when the file
is absent and never overwrites it afterwards, so the operator's backend secrets
and edits survive every ``install`` / ``update``; ``uninstall`` removes it only
while it is still the unedited template Apothem created. It carries **no** projected
shared-profile content and **no** coding-agent cohort (rules, commands, skills,
agents, hooks): a model backend is not rule-bearing and exposes none. The
managed-block sentinel machinery is markdown-only (HTML-comment delimiters, a
frozen contract), so it is deliberately not used here — folding sentinels into
a ``.toml`` surface would produce invalid TOML.

The adapter opts into the project-scope contract via ``requires_project = True``;
the CLI rejects an install / update / uninstall / verify invocation that omits
``--project <path>``. Delegates install logic to
:mod:`apothem.harnesses.glm.install`, which consumes the canonical propagation
manifest at ``src/apothem/lib/propagation-manifest.yaml`` under the ``glm`` key.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_project_scope_adapter
from apothem.harnesses.glm.install import install as _install
from apothem.harnesses.glm.install import plan as _plan
from apothem.harnesses.glm.uninstall import RELATIVE_TARGET as _SENTINEL_RELATIVE
from apothem.harnesses.glm.uninstall import uninstall as _uninstall
from apothem.harnesses.glm.update import update as _update
from apothem.harnesses.glm.verify import verify as _verify

# The sentinel relative path used by ``output_path`` for display purposes only
# and joined onto ``--project`` by ``resolve_output_path``. Sourced from
# ``uninstall`` so the target path and the uninstall project-root derivation
# share one definition.

GlmAdapter = make_project_scope_adapter(
    "glm",
    error_label="glm",
    relative_target=_SENTINEL_RELATIVE,
    install_fn=_install,
    plan_fn=_plan,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="GlmAdapter",
)
