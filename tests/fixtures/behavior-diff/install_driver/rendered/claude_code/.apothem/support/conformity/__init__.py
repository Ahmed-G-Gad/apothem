# SPDX-License-Identifier: MIT

"""Pre-emission conformity gate — the standalone validators and their orchestrator.

This package holds the mechanical fraction of Apothem's pre-emission gate: a set
of independent, grep-style validators (the ``*_grep.py`` modules plus
``link_check.py``) that each check one discipline over a target tree — authorship
headers, naming, plans-locality, plain-language, RFC 2119 usage, supply-chain
workflow posture, cross-surface coherence, and the rest — and the ``gate.py``
orchestrator that runs them and aggregates a single verdict.

The gate is advisory by default: findings are reported and the command exits 0.
``--strict`` (or ``APOTHEM_CONFORMITY_STRICT=1``) exits non-zero on a blocking
finding so a CI or pre-commit step fails; a CLI-usage error such as an unknown
validator name exits 3, distinct from the strict findings-block code 2. Each
validator is importable and runnable on its own, and a subset is wired as
PreToolUse hooks so the same checks fire at authoring time.
"""
