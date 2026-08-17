# SPDX-License-Identifier: MIT

"""JSON-output helper for the apothem CLI.

Writes a single JSON document to stdout terminated by a newline, so
shell consumers can ``jq .`` the result directly.
"""

from __future__ import annotations

import json
import sys


def emit_json(data: object) -> None:
    """Serialize *data* to stdout as a JSON document followed by a newline.

    Uses ``default=str`` so :class:`pathlib.Path` and other non-JSON-native
    types round-trip to their string form rather than raising.
    """
    sys.stdout.write(json.dumps(data, default=str) + "\n")
