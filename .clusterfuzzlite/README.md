<!-- SPDX-License-Identifier: MIT -->

# ClusterFuzzLite build

The build definition [ClusterFuzzLite](https://google.github.io/clusterfuzzlite/) uses to compile the fuzz targets in `tests/fuzz/`. `.github/workflows/fuzzing.yml` runs it.

| File | Purpose |
|------|---------|
| `project.yaml` | Declares the project language, `python`. |
| `Dockerfile` | The build image: the OSS-Fuzz Python base, pinned by tag and digest, with the checkout copied in. The base ships Python 3.11, Atheris and PyInstaller, so nothing is installed. Dependabot proposes a new digest (the docker entry in `.github/dependabot.yml`). |
| `build.sh` | Freezes each `tests/fuzz/fuzz_*.py` with `compile_python_fuzzer`, with `src/` and `src/apothem/_vendor/` on the search path and the package's data files bundled, and zips each target's seeds into `<target>_seed_corpus.zip`. |

## Working in this folder

Run a target without this build as `tests/fuzz/README.md` describes. To check the build itself, use the OSS-Fuzz helper with Docker from a clone of `google/oss-fuzz`: `python infra/helper.py build_fuzzers --external <path-to-apothem>`.
