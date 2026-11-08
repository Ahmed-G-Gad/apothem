#!/bin/bash -eu
# SPDX-License-Identifier: MIT

# Build every fuzz target under tests/fuzz/ into $OUT. compile_python_fuzzer
# (from the OSS-Fuzz base image) freezes a target with PyInstaller; the extra
# arguments let PyInstaller find apothem and its vendored dependencies in the
# checkout and bundle the package's data files (schemas, hook templates); the
# hooks in pyinstaller-hooks/ adapt PyInstaller to the vendored copies. Each
# target's seeds go next to it as <target>_seed_corpus.zip.
cd "$SRC/apothem"
for target in tests/fuzz/fuzz_*.py; do
  name=$(basename "$target" .py)
  stem=${name#fuzz_}
  compile_python_fuzzer "$target" \
    --paths "$SRC/apothem/src" \
    --paths "$SRC/apothem/src/apothem/_vendor" \
    --add-data "$SRC/apothem/src/apothem:apothem" \
    --additional-hooks-dir "$SRC/apothem/.clusterfuzzlite/pyinstaller-hooks"
  zip -j -q "$OUT/${name}_seed_corpus.zip" "tests/fuzz/seeds/${stem//_/-}"/*.txt
done
