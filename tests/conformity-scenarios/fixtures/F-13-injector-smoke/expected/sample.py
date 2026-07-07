# SPDX-License-Identifier: MIT

"""Sample Python module used as an F-13 injector smoke-test input.

Pre-injection this file carries no header. The injector detects the
``.py`` suffix, resolves the hash variant, and prepends the single
canonical ``# SPDX-License-Identifier: MIT`` line followed by one
blank-line separator before this docstring.
"""


def hello() -> str:
    """Return the canonical greeting."""
    return "hello"
