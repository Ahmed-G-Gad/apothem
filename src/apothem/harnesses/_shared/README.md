<!-- SPDX-License-Identifier: MIT -->

# _shared

> **Role.** The cross-adapter shared-infrastructure package. Logic recurring across three or more harness adapters is hoisted here so each adapter holds only its harness-specific identity and scope. The underscore prefix keeps this package out of the `apothem.harnesses` entry-point namespace — it is shared machinery, not a registrable adapter.

## What lives here

`install_driver.py` is the shared propagation driver every adapter's `install.py` delegates to. It carries the install recipe once: load a harness's rules from `lib/propagation-manifest.yaml`, sweep stale top-level paths from earlier layouts, then apply each install entry in declaration order. The driver supplies:

- The structured materialization-result surface (`MaterializationResult` / `MaterializationRun`) with deterministic per-outcome counts.
- The safe-write primitives: path validation against an allowed root, backup-before-replace, atomic swap, no-op detection.
- The directory-replace and stale-sweep primitives.
- The operator-owned merge path: sentinel-block merge for Markdown anchors, key-preserving merge for JSON and YAML. An operator file that parses only as JSONC, JSON5 or commented YAML is left byte-identical when the merge changes no value and refused with `config.unparseable` when it would, so a rewrite never drops the operator's comments.
- The destructive-authorization gate.
- The per-mode entry appliers (`write_text`, `replace_tree`, `merge_tree_entries`, `command_skills`, and the per-harness agent/command converters).

The driver's implementation is decomposed into single-responsibility sibling modules — `install_driver_apply.py`, `install_driver_backup.py`, `install_driver_converters.py`, `install_driver_jsonmerge.py`, `install_driver_lifecycle.py`, `install_driver_materialize.py`, `install_driver_merge.py`, `install_driver_pathsafety.py`, `install_driver_planvalidation.py`, `install_driver_removal.py`, `install_driver_treeops.py`, and `install_driver_types.py` — which `install_driver.py` composes into the public driver surface. `wrapper_factories.py` builds the shared adapter classes (the user-scope and project-scope adapter factories) so each adapter's `__init__.py` declares only its harness identity and scope.

Scope is expressed by which root the caller supplies — a user-scope harness root or a project-scope project root.

## Conventions

- Writes go through the safe-write primitives — never bypass them with a raw `Path.write_*`.
- Targets whose ownership class is vendor-reserved or immutable are refused outright; operator-owned non-additive overwrites route through the authorization gate with a unified diff.
- The hoist threshold is structural similarity across **three or more** adapters, not mere topical overlap; genuinely per-harness logic stays in the adapter subpackage.
- The package name stays underscore-prefixed; nothing here registers as an adapter or joins the `apothem.harnesses` entry-point group.
- This package is in `mypy --strict` scope.

## Operating in this folder

Add or change a primitive here only when the behavior is shared by three or more adapters; a one-adapter need belongs in that adapter's own module. Preserve the structured result/run surface — callers depend on the outcome vocabulary (`created` / `updated` / `unchanged` / `skipped` / `warning` / `error`) and the dry-run contract — so extend it additively rather than redefining existing outcomes. Validate with `python -m ruff check`, `python -m mypy src/apothem/harnesses/`, the conformity gate (`python -m apothem.conformity.gate --all .`), and `python -m pytest` (the adapter round-trip integration suite exercises this driver through every adapter).

## Related

- [`../../lib/propagation-manifest.yaml`](../../lib/propagation-manifest.yaml) — the propagation contract the driver loads.
- [`../../lib/harness_materializer.py`](../../lib/harness_materializer.py) — managed-block merge building blocks.
- [`../../lib/frontmatter.py`](../../lib/frontmatter.py) — agent/command field extraction used by the converters.
