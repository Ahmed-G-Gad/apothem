# SPDX-License-Identifier: MIT

"""apothem.lib package initializer.

Makes src/apothem/lib/ importable as a package so its shared internal helper
modules can be addressed by their fully-qualified names from sibling packages
and from external consumers. The package collects domain models and building
blocks reused across the apothem subpackages — profile, harness registry,
materializers, propagation, plugin-tree assembly, plan-tier classification,
frontmatter probing, parallel sweep, and structured reporting. These live in
the lib layer so harness adapters and tooling consume them without importing
the presentation-layer cli package. See README.md for the full module index.
"""
