# SPDX-License-Identifier: MIT

"""Sample module — contains a commented-out code block."""

from __future__ import annotations


def fetch(url: str) -> str:
    """Return the response body for a URL."""
    # Old implementation kept around in comments rather than version control:
    # response = requests.get(url, timeout=30)
    # if response.status_code != 200:
    #     raise RuntimeError(f"unexpected status {response.status_code}")
    # return response.text
    return f"<response from {url}>"
