---
fixture: F-13
title: Injector smoke-test
spec-source: site/content/docs/reference/authorship-header.mdx §7 The Injector
mandates: [M9]
---

<!-- SPDX-License-Identifier: MIT -->

# F-13 Injector Smoke-Test Fixture — Expected Behavior

This fixture exercises `scripts/inject-header.{sh,py}` against the seven
sample files at the fixture root, validating per-filetype single-line SPDX
emission, retired-multi-line-banner migration, idempotency under the canonical
form, and exemption-list honoring. The canonical header is the single
`SPDX-License-Identifier: MIT` line per comment family — the bordered
multi-line banner box is retired and the root `LICENSE` carries the full
copyright instrument.

## Inputs (fixture root)

| File | Pre-state | Variant family | Expected outcome |
|------|-----------|----------------|------------------|
| `sample.py` | No header | hash | Inject `# SPDX-License-Identifier: MIT`; one blank-line separator before docstring |
| `sample.js` | No header | double-slash | Inject `// SPDX-License-Identifier: MIT`; one blank-line separator before existing `//` comment |
| `sample.md` | No header | html | Inject `<!-- SPDX-License-Identifier: MIT -->`; one blank-line separator before H1 |
| `sample.css` | No header | c-block | Inject `/* SPDX-License-Identifier: MIT */`; one blank-line separator before body rule |
| `sample-with-legacy.py` | Retired multi-line banner (a `Copyright (c) ...` author line with no SPDX line above it) | hash | Strip the retired banner block; insert the single `# SPDX-License-Identifier: MIT` line; preserve docstring and function below |
| `sample-already-current.py` | Canonical `# SPDX-License-Identifier: MIT` line already at the insertion site | hash | No-op (zero diff, zero bytes changed) |
| `sample-exempted.json` | JSON content (no comment syntax) | exempt (per `**/*.json` glob in `src/apothem/schemas/header-exceptions.txt`) | No-op (skipped) |

## Expected post-injection state

Every file at the fixture root, after a `--mode fix-in-place` pass, matches
the byte-exact reference at `expected/<filename>` of the same name. The
injection and migration cases (`sample.py`, `sample.js`, `sample.md`,
`sample.css`, `sample-with-legacy.py`) differ from their inputs; the no-op and
exempt cases (`sample-already-current.py`, `sample-exempted.json`) are
byte-identical to their inputs. Sub-checks:

1. **Per-variant single-line emission.** The four fresh-injection cases produce
   the single canonical SPDX line in the comment syntax of their filetype
   family per the per-filetype variant table at
   `site/content/docs/reference/authorship-header.mdx` §2 — `# ...` for hash,
   `// ...` for double-slash, `<!-- ... -->` for html, `/* ... */` for c-block —
   each followed by exactly one blank-line separator.
2. **Retired-banner migration.** The migration file's retired multi-line banner
   block (keyed on the `Copyright (c) ...` author line with no SPDX line above
   it) is stripped and replaced with the single `# SPDX-License-Identifier: MIT`
   line; the docstring and function definition below the banner are preserved
   verbatim.
3. **Idempotency.** Running the injector a second time against the
   post-first-pass tree produces zero diff (bytes unchanged). The
   `is_canonical_at_position` check returns True for every applicable file once
   the canonical single SPDX line sits at the insertion site.
4. **Exemption honoring.** `sample-exempted.json` is unchanged after any number
   of injector passes; the `**/*.json` glob in
   `src/apothem/schemas/header-exceptions.txt` short-circuits the per-file walk.
5. **Cross-implementation equivalence.** The bash wrapper at
   `scripts/inject-header.sh` (which delegates to the Python script via
   `find-python.{sh}` resolution) produces output bytes-identical to
   `scripts/inject-header.py` invoked directly under the same Python
   interpreter.

## Verifier invocation (POSIX bash)

```bash
# Copy fixture root to a tmpdir to avoid mutating committed fixtures.
TMPDIR="$(mktemp -d)"
cp -r tests/conformity-scenarios/fixtures/F-13-injector-smoke "${TMPDIR}/work"
cd "${TMPDIR}/work"

# First pass: fix-in-place.
python scripts/inject-header.py \
    --root "$(pwd)" \
    --banner /path/to/schemas/authorship-header.txt \
    --exceptions /path/to/schemas/header-exceptions.txt \
    --mode fix-in-place \
    sample.py sample.js sample.md sample.css \
    sample-with-legacy.py sample-already-current.py sample-exempted.json

# Per-file byte-exact comparison.
for f in sample.py sample.js sample.md sample.css \
         sample-with-legacy.py sample-already-current.py sample-exempted.json; do
    cmp "${f}" "expected/${f}" || { echo "DIVERGENCE: ${f}"; exit 1; }
done

# Idempotency: second pass produces zero changes.
SNAPSHOT="$(mktemp -d)"
cp -r . "${SNAPSHOT}"
python scripts/inject-header.py --mode fix-in-place \
    sample.py sample.js sample.md sample.css \
    sample-with-legacy.py sample-already-current.py sample-exempted.json
diff -r . "${SNAPSHOT}" || { echo "IDEMPOTENCY FAIL"; exit 1; }
echo "F-13 PASS"
```

## Verifier invocation (PowerShell)

```powershell
$TMP = New-TemporaryFile | ForEach-Object { Remove-Item $_; New-Item -ItemType Directory -Path $_.FullName }
Copy-Item -Recurse tests/conformity-scenarios/fixtures/F-13-injector-smoke "$TMP/work"
Set-Location "$TMP/work"

python scripts/inject-header.py `
    --root $PWD --banner /path/to/schemas/authorship-header.txt `
    --exceptions /path/to/schemas/header-exceptions.txt --mode fix-in-place `
    sample.py sample.js sample.md sample.css `
    sample-with-legacy.py sample-already-current.py sample-exempted.json

foreach ($f in 'sample.py','sample.js','sample.md','sample.css',
               'sample-with-legacy.py','sample-already-current.py','sample-exempted.json') {
    if ((Get-FileHash $f).Hash -ne (Get-FileHash "expected/$f").Hash) {
        throw "DIVERGENCE: $f"
    }
}
```

## Bindings

- **Drives →** The comprehensive header sweep and verification matcher; the matcher consumes the same canonical fixture at `src/apothem/schemas/authorship-header.txt` to gate post-sweep state.
- **Established by ↑** `site/content/docs/reference/authorship-header.mdx` §7 (the injector reference) and the canonical single-line SPDX header discipline.
- **Cross-bound with ↔** `src/apothem/schemas/authorship-header.txt` (canonical single-line fixture); `src/apothem/schemas/header-exceptions.txt` (exemption globs); `scripts/inject-header.{sh,py}` (the artifacts under test); `site/content/docs/reference/authorship-header.mdx` §2 (per-filetype variant table).
```
