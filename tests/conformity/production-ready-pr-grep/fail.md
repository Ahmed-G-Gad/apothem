<!-- SPDX-License-Identifier: MIT -->

# Production-ready-pr grep — FAIL fixture (deferred)

Per-file mode for production-ready-pr-grep is a no-op pass; the
substantive FAIL semantics fires via `--staged` against an actual git
index that contains a code-class file change without companion
tests / docs / changelog entries. The smoke test cannot drive the
substantive check from a single-file fixture; the substantive check is
exercised in CI against representative branches that simulate the
half-finished change-set shape.

The orchestrator therefore treats per-file dispatch of this grep as
a soft pass and the substantive enforcement runs at commit time. The
grep's module docstring records this design point explicitly.
