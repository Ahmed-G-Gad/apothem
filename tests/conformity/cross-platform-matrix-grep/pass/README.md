<!-- SPDX-License-Identifier: MIT -->

# cross-platform-matrix-grep — pass fixture

Canonical CI workflow declaring the full 3-OS x 4-Python release matrix:
`ubuntu-latest`, `macos-latest`, `windows-latest` crossed with
Python `3.10`, `3.11`, `3.12`, `3.13` (twelve cells). The validator
must exit 0 against the directory tree rooted at this fixture's parent.
