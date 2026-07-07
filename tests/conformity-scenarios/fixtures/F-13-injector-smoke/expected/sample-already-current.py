# SPDX-License-Identifier: MIT

"""Sample Python module that already carries the canonical SPDX line.

Pre-injection this file already carries ``# SPDX-License-Identifier: MIT``
at the insertion site. The injector detects the canonical form is
present and produces a no-op (zero diff, zero bytes changed).
"""


def hello() -> str:
    """Return the canonical greeting."""
    return "hello"
