# SPDX-License-Identifier: MIT

"""Install logic for the glm harness adapter.

Materializes the GLM backend-provider configuration into the operator-supplied
project root. GLM (Z.ai) is a model backend an Anthropic-compatible or
OpenAI-compatible coding agent points at; it exposes no native coding-agent
config surface, so the adapter writes a single provider file at
``<project>/.apothem/providers/glm.toml`` recording the backend base URLs, an
auth-token placeholder, and operator-configurable model-mapping placeholders.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``glm`` key (a single
operator-owned ``write_text`` operation targeting
``${PROJECT_ROOT}/.apothem/providers/glm.toml``) and applied by the shared
driver at ``apothem.harnesses._shared.install_driver``. ``write_text`` writes
the valid-TOML template only when the file is absent (an operator-owned target in
a format Apothem cannot merge into is create-if-missing); the operator owns the
file thereafter and no ``install`` / ``update`` overwrites it. The file carries
**no** projected shared-profile content — GLM is a
model backend, not a rule-bearing coding agent, so there is no instruction
cohort to fold in, and the markdown-only sentinel-merge machinery (HTML-comment
delimiters) would corrupt a ``.toml`` surface and is deliberately not used. The
``${PROJECT_ROOT}`` placeholder is substituted with the operator-supplied
``--project <path>`` value the CLI threads through; absence of ``--project`` is
rejected upstream at ``apothem.cli._materialize`` via the ``requires_project``
opt-in.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_project_scope_plan,
)

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "glm"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="glm adapter requires --project <path>; CLI must thread it through",
)

plan = make_project_scope_plan(_HARNESS_NAME)
