<!-- SPDX-License-Identifier: MIT -->

<!--
Fixture: editorconfig-presence-grep / pass

Canonical .editorconfig at this directory root. Carries the `root = true`
declaration, the six required `[*]` keys at their ratified values, the
`[*.{yml,yaml,json}]` two-space override, and the `[*.md]`
trim_trailing_whitespace = false override. Invoking the matcher with
this directory as the root argument exits 0 with an empty findings
list.
-->

# editorconfig-presence-grep — pass fixture

This subdirectory ships a conformant `.editorconfig`. The matcher reads
`<root>/.editorconfig` so this directory itself plays the part of the
project root for the test.
