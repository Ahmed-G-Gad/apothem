<!-- SPDX-License-Identifier: MIT -->

# Fuzz targets

Coverage-guided fuzz targets for the parsers that read files an operator writes, or that a crash can leave damaged. [Atheris](https://github.com/google/atheris) runs them, and [ClusterFuzzLite](https://google.github.io/clusterfuzzlite/) runs Atheris in CI: `.clusterfuzzlite/` builds the targets and `.github/workflows/fuzzing.yml` fuzzes each pull request that touches `src/apothem/` for five minutes, split across the targets, and runs a fifteen-minute batch every day. A pull-request run fails on any crash it finds, an old one too. The profile-loader target is the slow one (about 50 inputs a second), so the daily batch carries most of its coverage.

## Files

| File | Fuzzes | Invariants beyond "no unexpected exception" |
|------|--------|---------------------------------------------|
| `fuzz_lenient_json.py` | `apothem.lib.lenient_json.loads`, the JSONC / JSON5 reader for OpenCode and OpenClaw configs | Text `json.loads` accepts parses to the same value; the only allowed difference is the reader's nesting limit (`MAX_DEPTH`). |
| `fuzz_hook_registration.py` | `merge_registration` and `strip_registration`, the hook-file merge for Kiro, GitHub Copilot and Cursor | A second install leaves the file byte for byte the same; the merge keeps the operator's hooks in order; an uninstall leaves no Apothem hook. Only an operator-owned file may be refused. |
| `fuzz_profile_loader.py` | `load_profile_file`, the shared-profile loader every command runs first | The result is a `CanonicalProfile` or a `ProfileValidationError`; a loaded profile normalizes to itself; every harness projection works. |
| `fuzz_install_ledger.py` | `install_ledger.read_records`, the JSON-lines ledger uninstall and rollback trust | The result is records or a `LedgerError`; each record serializes and reads back to the same line. |
| `fuzz_frontmatter.py` | `apothem.lib.frontmatter`, the frontmatter probe of the conformity validators and rule emitters | `split_frontmatter` loses no text; a field value is text from the file. |
| `test_fuzz_seed_replay.py` | Every target, without Atheris | Runs each target's `fuzz_one_input` over its seeds in the ordinary `pytest` run, on every operating system. |
| `seeds/` | One folder per target, named after it without `fuzz_` and in kebab case | Seed inputs as `.txt` files. ClusterFuzzLite starts from them, and the replay test runs them. |

## How a target is written

Each target is a plain module with a `fuzz_one_input(data: bytes) -> None` function that raises `AssertionError` when an invariant breaks, and a `main()` that imports Atheris, instruments the loaded code, and hands the function to `atheris.Fuzz()`. Atheris is imported only in `main()`, so the replay test imports the targets on any platform without it. A target that needs a choice besides the file content takes it from the first input byte (`fuzz_hook_registration.py`: byte modulo 3 picks the template, and an odd byte divided by 3 makes the file operator-owned; ASCII `0` to `2` and `3` to `5` cover the six cases).

## Running a target locally

Atheris needs Linux or macOS, Python 3.11 or later, and a wheel or a clang build of it. Point `PYTHONPATH` at the checkout and its vendored dependencies, the way the engine runs, and copy the seeds to a scratch folder, because libFuzzer writes new inputs into the corpus folder it is given:

```bash
python -m pip install atheris
export PYTHONPATH="$PWD/src:$PWD/src/apothem/_vendor"
mkdir -p /tmp/corpus && cp tests/fuzz/seeds/lenient-json/*.txt /tmp/corpus/
python tests/fuzz/fuzz_lenient_json.py -max_total_time=60 /tmp/corpus
```

A crash writes a `crash-<hash>` file in the current folder; run the target with that file as its only argument to reproduce it.

## Working in this folder

When a fuzzer finds a crash, fix the code, add a unit test for the fix next to the module's other tests, and add the crashing input to the target's `seeds/` folder so the replay test keeps it fixed. A new target is a new `fuzz_<name>.py` with a `seeds/<name-in-kebab-case>/` folder holding at least one seed; `.clusterfuzzlite/build.sh` and the replay test pick both up by name. Seed files carry no SPDX line: `src/apothem/schemas/header-exceptions.txt` exempts them, and `REUSE.toml` covers them.
