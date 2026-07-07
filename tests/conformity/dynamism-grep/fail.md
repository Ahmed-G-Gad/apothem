<!-- SPDX-License-Identifier: MIT -->

<!-- dynamism-grep test fixture: fail.md
     Expected verdict: FAIL (literal static-version embeds in in-scope surface).
     Surface shape: README-like content with hard-coded semvers that would
     drift the moment the canonical version increments, per `rules/dynamism.md`
     + spec §3.2.c. -->

# Apothem

![Release](https://img.shields.io/badge/release-v1.2.3-blue)

Apothem 1.2.3 is a host-agnostic AI-harness configuration manager.

## Install

```bash
npx @ahmed-g-gad/apothem@1.2.3
```

The current pinned release is v1.2.3 and the documentation site mirrors
1.2.3 across every example page. See the install guide for the 2.0.0
migration notes.
