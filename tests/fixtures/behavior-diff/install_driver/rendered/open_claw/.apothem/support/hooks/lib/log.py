# SPDX-License-Identifier: MIT

"""Shared logger factory for the apothem hook scripts.

Purpose: a single source of truth for how hook modules acquire a
``logging.Logger``. Both ``hooks/emit_hook_context.py`` and
``hooks/session_start_bootstrap.py`` previously instantiated their
loggers via ``logging.getLogger(<hard-coded-name>)``, which drifted
over time and made downstream handler configuration inconsistent.

Contract: ``get_logger(name)`` returns a ``logging.Logger`` whose
name is the caller's ``__name__``. The hook runtime configures
handlers itself; this factory does not attach handlers, set levels,
or alter the root logger — it only provides a uniform acquisition
point so future structured-logging changes land in one file.

Sibling files in hooks/lib/: events.py (event-name single source of
truth), resolve_root.py (project-root resolver), bootstrap.sh +
bootstrap.ps1 (the entry stubs that exec the Python hook scripts
this logger serves), find-python.sh + find-python.ps1 (interpreter
locators).

Note on module name: this file is `log.py` rather than `logging.py`
because ``hooks/lib/`` is inserted at ``sys.path[0]`` by the
dispatcher; a sibling named ``logging.py`` would shadow the stdlib
``logging`` module on first ``import logging`` and break every
caller.
"""

from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a logger named ``name``, typically the caller's ``__name__``.

    The factory deliberately does no handler/level/formatter setup —
    that is the hook runtime's responsibility. Centralizing the
    acquisition point keeps the call sites uniform and makes future
    structured-logging migrations a single-file change.
    """
    return logging.getLogger(name)
