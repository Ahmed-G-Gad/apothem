# SPDX-License-Identifier: MIT

"""Hermetic git environment for test subprocesses.

A test that runs git, directly or through a script under test, inherits the
developer's git configuration unless it opts out, and that configuration
changes what git does. ``gpg.format ssh`` makes ``git tag -s`` write an SSH
signature where the test expects an OpenPGP one, ``commit.gpgsign`` sends
every fixture commit to a signing program, and a global ``core.hooksPath``
runs the developer's hooks against fixture commits. Each one turns a passing
test into a host-dependent failure.

:func:`hermetic_git_env` returns a copy of an environment in which git reads
no configuration above the repository:

- ``GIT_CONFIG_GLOBAL`` names the null device, so neither ``~/.gitconfig``
  nor ``$XDG_CONFIG_HOME/git/config`` is read (git 2.32 or later; older git
  ignores the variable);
- ``GIT_CONFIG_NOSYSTEM=1`` skips the system file, including one named by an
  inherited ``GIT_CONFIG_SYSTEM``;
- the variables that carry configuration themselves are dropped:
  ``GIT_CONFIG_PARAMETERS`` (what ``git -c`` exports to child processes),
  ``GIT_CONFIG_COUNT`` with its ``GIT_CONFIG_KEY_<n>`` /
  ``GIT_CONFIG_VALUE_<n>`` pairs, and ``GIT_CONFIG``, which redirects
  ``git config`` writes away from the repository.

Repository-local configuration and ``-c`` options on the command line still
apply, so a fixture sets what it needs explicitly. Nothing is written to disk.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Final

# Variables that carry git configuration themselves, out of reach of
# GIT_CONFIG_GLOBAL and GIT_CONFIG_NOSYSTEM: GIT_CONFIG_PARAMETERS and the
# GIT_CONFIG_COUNT / _KEY_<n> / _VALUE_<n> pairs override every config file,
# and GIT_CONFIG points `git config` at a file other than the repository's.
_CONFIG_CARRIERS: Final[frozenset[str]] = frozenset(
    {"GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"}
)
_CONFIG_CARRIER_PREFIXES: Final[tuple[str, ...]] = (
    "GIT_CONFIG_KEY_",
    "GIT_CONFIG_VALUE_",
)


def hermetic_git_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a copy of *base* (default ``os.environ``) that hides the host's
    global, system, and environment-carried git configuration from git."""
    source = os.environ if base is None else base
    env = {
        name: value
        for name, value in source.items()
        if name not in _CONFIG_CARRIERS
        and not name.startswith(_CONFIG_CARRIER_PREFIXES)
    }
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env
