<!-- SPDX-License-Identifier: MIT -->

# Absent-Banner Fixtures

The absent-banner test suite at
`tests/scripts/inject-header/test_absent_fails_check.py` constructs its
fixtures at runtime via `tmp_path` rather than checking them into this
directory, because shipping an absent-banner file at a long-lived
fixture path would itself be flagged by every codebase-wide
header-coverage scan.

This README is the directory's only persistent file; its banner is
canonical so the injector treats it as a no-op.
