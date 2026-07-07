---
fixture: F-14
title: Header-form verification matcher
spec-source: _spec/spec.md §10.5 verification matcher
mandates: [M9]
---

<!-- SPDX-License-Identifier: MIT -->

# F-14 Header-Form Verification Matcher Fixture — Expected Behavior

This fixture exercises `src/apothem/conformity/file-header-grep.py` against
five sample files: one passing case (canonical 6-line form) and four
failure modes (legacy 5-line, missing header, malformed SPDX, wrong
variant). Each sample's expected verdict — exit code, `passed`, finding
rule (`HEADER_ABSENT` or `HEADER_MALFORMED`), and context substring —
lives at `expected/<sample>.verdict.txt`.

## Samples

| Sample | Pre-state | Expected verdict | Expected exit | Rule |
|--------|-----------|------------------|---------------|------|
| `sample-canonical.py` | Canonical 6-line form (SPDX top + 5 bordered + Licensed-under-MIT bottom) | PASS | 0 | n/a |
| `sample-header-5line.py` | Legacy 5-line form (no SPDX, "All rights reserved") | FAIL | 2 | HEADER_MALFORMED |
| `sample-no-header.py` | No banner whatsoever | FAIL | 2 | HEADER_ABSENT |
| `sample-malformed-spdx.py` | SPDX line carries `GPL-3.0` instead of `MIT` | FAIL | 2 | HEADER_MALFORMED |
| `sample-wrong-variant.py` | `.py` file with `//` double-slash variant (filetype-variant mismatch) | FAIL | 2 | HEADER_MALFORMED |

## Verifier invocation

```bash
for s in canonical legacy-5line no-header malformed-spdx wrong-variant; do
    python src/apothem/conformity/file-header-grep.py \
        "tools/conformity-scenarios/fixtures/F-14-header-form/sample-${s}.py"
    actual_exit=$?
    expected_exit=$(grep '^exit_code:' \
        "tools/conformity-scenarios/fixtures/F-14-header-form/expected/sample-${s}.verdict.txt" \
        | awk '{print $2}')
    [ "${actual_exit}" -eq "${expected_exit}" ] || {
        echo "FAIL: ${s} exit ${actual_exit} != expected ${expected_exit}"; exit 1; }
done
echo "F-14 PASS: all five samples produce expected matcher verdicts"
```

## Bindings

- **Drives →** Header-form PASS verdict (the matcher is exercised against this fixture before integration); the `file-header-grep` matcher's regression coverage at every future ecosystem touch.
- **Established by ↑** The canonical fixture at `src/apothem/schemas/authorship-header.txt`.
- **Cross-bound with ↔** `src/apothem/conformity/file-header-grep.py` (the matcher under test); `src/apothem/schemas/authorship-header.txt` (the canonical fixture the matcher reads); `tools/conformity-scenarios/fixtures/F-13-injector-smoke/` (the sibling fixture exercising the injector).
