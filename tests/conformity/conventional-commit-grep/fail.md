<!-- SPDX-License-Identifier: MIT -->

<!--
  SPDX-License-Identifier: MIT
  Fixture: conventional-commit-grep FAIL cases.
  Each line illustrates at least one drift class against the
  Conventional-Commits grammar. Drift class noted inline.
-->

# conventional-commit-grep — fail fixtures

Sample non-conformant commit subjects with drift class annotations:

- `Add dry-run flag` — `missing-type` (no `<type>:` prefix)
- `wip(cli): scratch work` — `invalid-type` (`wip` not in allowed set)
- `feat(CLI Tools): add flag` — `scope-malformed` (uppercase + space in scope)
- `feat(cli): added support for the dry-run flag across every adapter and verifier` — `subject-too-long` plus `non-imperative-verb` (`added`)
- `fix(harness): adds missing settings.json handling.` — `non-imperative-verb` (`adds`) plus `subject-ends-with-period`
- `docs: refactoring the conformity dispatcher` — `non-imperative-verb` (`refactoring`)
