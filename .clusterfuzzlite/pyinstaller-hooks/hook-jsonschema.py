# SPDX-License-Identifier: MIT

"""PyInstaller hook for the vendored jsonschema (src/apothem/_vendor/).

The hook pyinstaller-hooks-contrib ships for jsonschema also copies the
package's install metadata, which a vendored source copy does not have, so the
build fails. A hook in this folder takes precedence; it bundles the package's
data files (its bundled schemas) and nothing else. jsonschema reads its metadata
only for ``jsonschema.__version__``, which apothem does not use.
"""

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("jsonschema")
