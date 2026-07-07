# SPDX-License-Identifier: MIT

"""FAIL fixture: bare except plus broad except without re-raise."""

from __future__ import annotations


def fetch_silently(url: str) -> str:
    try:
        return _do_fetch(url)
    except:
        return ""


def fetch_broad(url: str) -> str:
    try:
        return _do_fetch(url)
    except Exception:
        return ""


def _do_fetch(url: str) -> str:
    return f"<{url}>"
