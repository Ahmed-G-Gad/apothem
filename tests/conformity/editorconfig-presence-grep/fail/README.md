<!-- SPDX-License-Identifier: MIT -->

<!--
Fixture: editorconfig-presence-grep / fail

Non-conformant .editorconfig at this directory root. Two drifts:
(1) missing the `root = true` declaration (drift class
missing-root-declaration), and (2) missing the `[*.md]` per-language
override (drift class missing-per-language-override). Invoking the
matcher with this directory as the root argument exits 2 with both
drift classes enumerated in the findings list.
-->

# editorconfig-presence-grep — fail fixture

This subdirectory ships a deliberately drifting `.editorconfig`. The
matcher reads `<root>/.editorconfig` so this directory itself plays the
part of the project root for the test.
