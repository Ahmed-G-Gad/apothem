# SPDX-License-Identifier: MIT

"""Shared helpers consumed by the hook dispatcher and per-event emitters.

Modules:

* ``events`` — canonical hook-event taxonomy plus per-event metadata.
* ``log`` — structured-logging surface used across the hook pipeline.
* ``resolve_root`` — ecosystem-root resolution from the dispatcher's
  invocation context (``CLAUDE_PROJECT_DIR`` / ``LLM_PROJECT_DIR`` /
  fallback heuristics).

The cross-platform shell stubs (``bootstrap.sh``, ``bootstrap.ps1``,
``find-python.sh``, ``find-python.ps1``, ``find-pwsh.sh``,
``find-pwsh.ps1``) live in this directory as data files; they are
invoked by the harness's ``settings.json`` ``command:`` field at
hook-fire time, not imported as Python modules.
"""
