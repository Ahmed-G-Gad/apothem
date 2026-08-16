# SPDX-License-Identifier: MIT

"""Statusline renderer and conformity-posture surface.

This package carries the single operator-visible statusline renderer. The
runtime surfaces are:

* ``apothem.statuslines.render`` — the renderer, invoked through
  ``python -m apothem.statuslines.render``. The harness pipes its
  statusline JSON payload on stdin; the renderer reads only
  ``workspace.project_dir`` to locate the project-local plans tree, then
  emits the operating-posture line (active phase pointer, sprint goal,
  unresolved-inquiry count) the harness surfaces in its status bar.
* ``conformity.json`` — the harness statusline-config snippet (a
  ``type: command`` entry whose command invokes ``render.py`` through the
  ``${HARNESS_ROOT}`` token). It wires the renderer into the harness's
  statusline hook; the renderer never reads it.
* ``statusline.md`` — the operator-facing reference Markdown documenting
  the renderer's input contract, output shape, and degradation modes.
"""
