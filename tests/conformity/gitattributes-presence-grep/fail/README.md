<!-- SPDX-License-Identifier: MIT -->

<!--
  Fail-fixture for gitattributes-presence-grep.

  The sibling `.gitattributes` deliberately omits two required
  contract elements: the `*.svg text` declaration (SVG would be
  treated as binary, losing diffability) and the `.plans/ export-ignore`
  declaration (planning ephemera would leak into source archives).
  Pointing the validator at this directory MUST exit 2 with findings
  carrying drift classes `missing-binary-declaration` (for the SVG
  omission) and `missing-export-ignore` (for the .plans/ omission).
-->

# gitattributes-presence-grep — fail fixture

Run `python -m apothem.conformity.gitattributes_presence_grep <this-dir>` to confirm a non-zero exit with two findings.
