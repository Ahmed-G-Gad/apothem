<!-- SPDX-License-Identifier: MIT -->

# cross-platform-matrix-grep — fail fixture

CI workflow with two drift classes: the OS axis omits `macos-latest`
and the Python-version axis omits `3.13`. The validator must exit
non-zero against the directory tree rooted at this fixture's parent,
emitting `os-missing` (macos-latest), `python-version-missing` (3.13),
and `matrix-cell-count-mismatch` (expected 12, actual 6) findings.
