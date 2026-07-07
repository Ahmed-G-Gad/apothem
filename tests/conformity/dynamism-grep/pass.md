<!-- SPDX-License-Identifier: MIT -->

<!-- dynamism-grep test fixture: pass.md
     Expected verdict: PASS (zero static-version embeds in in-scope surfaces).
     Surface shape: README-like content using dynamic substitutions for every
     version reference, per `rules/dynamism.md` + spec §3.2.c. -->

# Apothem

![npm](https://img.shields.io/npm/v/%40ahmed-g-gad%2Fapothem)
![Python](https://img.shields.io/badge/python-3.10+-blue)

Apothem is a host-agnostic AI-harness configuration manager.

## Install

The current release is published to the npm registry; run it with:

```bash
npx @ahmed-g-gad/apothem
```

The installed version resolves through `apothem.__version__` at runtime and
matches the `version` field declared in `pyproject.toml`. Documentation
pages render the version via `{{ version }}` substitution.

## Compatibility

Apothem supports CPython 3.10 and later. The minimum supported version
is declared dynamically by the build manifest, not by a literal pin in
this README.
