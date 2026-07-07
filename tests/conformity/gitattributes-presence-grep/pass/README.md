<!-- SPDX-License-Identifier: MIT -->

<!--
  Pass-fixture for gitattributes-presence-grep.

  The sibling `.gitattributes` carries every required element of the
  supply-chain contract: the `* text=auto eol=lf` baseline,
  binary declarations for PNG / JPG / JPEG, an explicit `*.svg text`
  declaration, and `export-ignore` for `.plans/`, `tests/`, and
  `.github/`. Pointing the validator at this directory MUST exit 0
  with an empty findings list.
-->

# gitattributes-presence-grep — pass fixture

Run `python -m apothem.conformity.gitattributes_presence_grep <this-dir>` to confirm a clean PASS.
