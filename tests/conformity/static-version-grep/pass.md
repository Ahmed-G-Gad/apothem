<!-- SPDX-License-Identifier: MIT -->

<!--
SPDX-License-Identifier: MIT
Test fixture for static-version-grep: PASS case.
Demonstrates a shields.io dynamic badge URL and a dynamic
runtime __version__ resolution. The validator should report
zero findings against a project shaped like this.
-->

# Apothem

![npm version](https://img.shields.io/npm/v/%40ahmed-g-gad%2Fapothem)
![npm downloads](https://img.shields.io/npm/dm/%40ahmed-g-gad%2Fapothem)
![GitHub release](https://img.shields.io/github/v/release/ahmed-g-gad/apothem)

## Runtime version resolution

```python
from importlib.metadata import version

__version__ = version("apothem")
```

## Docs config

```yaml
site_name: Apothem
# version derived dynamically at build time
version: !ENV [APOTHEM_VERSION, "dev"]
```
