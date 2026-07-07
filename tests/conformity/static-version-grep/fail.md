<!-- SPDX-License-Identifier: MIT -->

<!--
SPDX-License-Identifier: MIT
Test fixture for static-version-grep: FAIL case.
Demonstrates a badge URL with a literal version embedded and a
literal __version__ string assignment. The validator should
flag both as static-resolution findings.
-->

# Apothem

![npm version](https://img.shields.io/badge/npm-v1.2.3-blue)
![Release](https://img.shields.io/badge/release-1.2.3-green)

## Runtime version resolution

```python
__version__ = "1.2.3"
```

## Docs config

```yaml
site_name: Apothem
version: "1.2.3"
```
