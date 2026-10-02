# SPDX-License-Identifier: MIT

"""JSON-output helper for the apothem CLI.

Writes a single JSON document to stdout terminated by a newline, so
shell consumers can ``jq .`` the result directly. Every document carries a
top-level ``schema_version`` as its first key (see :data:`JSON_SCHEMA_VERSION`).
"""

from __future__ import annotations

import json
import sys

#: Version of the CLI's JSON output contract, emitted as the first key of every
#: ``--json`` document. Adding a key keeps the version; renaming or removing a
#: key, or changing a value's type, bumps it. A document that is itself a
#: versioned artifact (``profile show`` emits a profile) carries that
#: artifact's own ``schema_version`` instead.
JSON_SCHEMA_VERSION = 1


def emit_json(data: object) -> None:
    """Serialize *data* to stdout as a JSON document followed by a newline.

    A mapping without a ``schema_version`` gains one as its first key. Uses
    ``default=str`` so :class:`pathlib.Path` and other non-JSON-native types
    round-trip to their string form rather than raising.
    """
    if isinstance(data, dict) and "schema_version" not in data:
        data = {"schema_version": JSON_SCHEMA_VERSION, **data}
    sys.stdout.write(json.dumps(data, default=str) + "\n")
