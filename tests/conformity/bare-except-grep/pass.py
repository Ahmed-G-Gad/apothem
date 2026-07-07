# SPDX-License-Identifier: MIT

"""PASS fixture: every except clause is typed and either handles or re-raises."""

from __future__ import annotations


def fetch(url: str) -> str:
    """Fetch URL with typed exception handling."""
    try:
        return _do_fetch(url)
    except TimeoutError:
        return ""
    except Exception as err:
        # Broad catch is permitted because we re-raise with context.
        raise RuntimeError(f"unexpected failure for {url!r}") from err


def _do_fetch(url: str) -> str:
    return f"<{url}>"
