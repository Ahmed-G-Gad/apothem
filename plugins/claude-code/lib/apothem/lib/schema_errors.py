# SPDX-License-Identifier: MIT

"""Shared jsonschema-validation error formatting.

Several surfaces validate a candidate mapping against a packaged JSON schema and,
on failure, raise a domain error whose message lists every discovered violation.
The formatting is identical across them: gather the validator's errors, order
them by instance path for a deterministic message, and join the individual
messages with ``; ``. This helper is that single formatting step — each caller
keeps its own domain exception type and message prefix.
"""

from __future__ import annotations

from jsonschema import Draft202012Validator


def format_schema_errors(validator: Draft202012Validator, data: object) -> str | None:
    """Return the joined validation-error message for *data*, or ``None``.

    Collects every error the *validator* reports for *data*, orders them by
    instance ``path`` so the joined message is deterministic, and joins the
    per-error messages with ``; ``. Returns ``None`` when *data* satisfies the
    schema, so a caller can raise only on a truthy result.
    """
    # Type-stable sort key: an error path mixes str mapping keys with int
    # array indices, and comparing those directly raises TypeError.
    errors = sorted(
        validator.iter_errors(data),
        key=lambda error: [(isinstance(p, int), str(p)) for p in error.path],
    )
    if not errors:
        return None
    return "; ".join(error.message for error in errors)
