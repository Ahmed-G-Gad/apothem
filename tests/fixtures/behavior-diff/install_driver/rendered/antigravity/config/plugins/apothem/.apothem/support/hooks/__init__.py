# SPDX-License-Identifier: MIT

"""Hook dispatcher and per-event context emitters.

This package carries the apothem hook-event pipeline. The runtime
entry-points are:

* ``apothem.hooks.dispatch`` — the harness-side dispatcher. Harness
  hook entries invoke the materialized copy by absolute script path
  (``<harness-root>/apothem/hooks/dispatch.py`` or the harness's hook
  subtree), so no importable ``apothem`` package is required on the
  host. Receives an event name and an optional message name; emits the
  per-event Markdown context to stdout for the harness to surface in
  the operator's chat session.
* ``apothem.hooks.emit_hook_context`` — the per-event context emitter
  that materializes a Markdown payload from the bundled message
  fixtures and the live ecosystem state.
* ``apothem.hooks.session_start_bootstrap`` — the SessionStart-event
  bootstrap that surfaces the conformity posture, memory summary, plan
  summary, and session-source banner at every fresh session.

Shared helpers live under ``apothem.hooks.lib`` (event taxonomy,
logging, root resolution).
"""
