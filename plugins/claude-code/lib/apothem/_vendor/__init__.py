# SPDX-License-Identifier: MIT
"""Vendored pure-Python third-party dependencies for the self-contained runtime.

This package holds source copies of apothem's third-party runtime dependencies
so the engine runs registry-free, directly from a checkout or from the bundled
plugin tree. The plugin bootstrap prepends this directory to ``sys.path`` ahead
of site-packages, so a vendored copy here takes precedence over any
system-installed version.

Vendored set: ``attrs`` (with its ``attr`` compatibility package),
``jsonschema``, ``jsonschema_specifications``, ``referencing``,
``typing_extensions``, ``yaml`` (PyYAML), and a pure-Python ``rpds`` shim that
reimplements the persistent-data-structure subset the validation stack
exercises. Each upstream package retains its license file alongside its tree.

Placement rule: only **pure-Python** distributions belong here. A dependency
that ships a compiled extension (C, Rust/PyO3, Cython) cannot be vendored as
portable source — the binary is platform- and ABI-specific. Such dependencies
are handled out-of-band (stdlib reduction, a pure-Python shim such as ``rpds``,
or a documented system-Python prerequisite). ``click`` and ``rich`` are
intentionally not vendored — they are engine prerequisites the host
environment provides. See
``site/content/docs/architecture/vendoring-strategy.mdx`` for the
per-dependency decisions and the rationale behind this boundary.
"""
