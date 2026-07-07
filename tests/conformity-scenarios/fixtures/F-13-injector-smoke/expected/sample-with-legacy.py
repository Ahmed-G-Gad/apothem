# SPDX-License-Identifier: MIT

"""Sample Python module carrying a retired multi-line authorship banner.

Pre-injection this file carries the retired multi-line banner block (a
``Copyright (c) ...`` author line with no SPDX line above it). The
injector strips that legacy block and replaces it with the single
canonical ``# SPDX-License-Identifier: MIT`` line, preserving this
docstring and the function definition below.
"""


def hello() -> str:
    """Return the canonical greeting."""
    return "hello"
