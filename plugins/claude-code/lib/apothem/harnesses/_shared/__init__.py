# SPDX-License-Identifier: MIT

"""Shared install infrastructure for harness adapters.

Holds the common propagation-driver logic every harness adapter's
``install.py`` delegates to: manifest-rule loading, source/target path
resolution, the copytree ignore-filter builder, the directory-replace
primitive, the stale-sweep primitive, and the install/plan orchestrators.
The underscore-prefixed package name keeps it out of the
``apothem.harnesses`` entry-point namespace — it is shared infrastructure,
not a registrable adapter.
"""
