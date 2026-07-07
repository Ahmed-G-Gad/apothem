<!-- SPDX-License-Identifier: MIT -->

# Production-ready-pr grep — per-file PASS fixture

The grep's per-file mode is a no-op pass; the substantive check fires
only via `--staged` against an actual git index. This fixture
documents the per-file invariant: a single artifact in isolation
cannot evaluate change-set completeness.

The smoke test invokes the grep with this path and expects exit 0.
The FAIL fixture documents the same invariant — both per-file
invocations pass; the substantive check is exercised separately at
CI time.
