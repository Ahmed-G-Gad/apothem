# SPDX-License-Identifier: MIT

"""Apothem harness adapter for qwen-code.

Materializes ``~/.qwen/settings.json`` from the shared profile per the
qwen-code vendor canonical schema at
https://qwenlm.github.io/qwen-code-docs/en/users/configuration/settings/;
the adapter-local
``STANDARD-CONVENTION-PIN.md`` records the current convention snapshot.
The install step also writes ``QWEN.md``, registers native hooks, and
propagates Apothem commands, skills, and agents into Qwen Code's native
Markdown discovery directories.
Delegates install logic to :mod:`apothem.harnesses.qwen_code.install`, which
renders the native config via :mod:`apothem.harnesses.qwen_code.materializer`.
"""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared.wrapper_factories import make_native_config_adapter
from apothem.harnesses.qwen_code.install import install as _install
from apothem.harnesses.qwen_code.materializer import (
    materialize_native_config as materialize_native_config,
)
from apothem.harnesses.qwen_code.uninstall import uninstall as _uninstall
from apothem.harnesses.qwen_code.update import update as _update
from apothem.harnesses.qwen_code.verify import verify as _verify

QwenCodeAdapter = make_native_config_adapter(
    "qwen-code",
    target_factory=lambda: Path.home() / ".qwen/settings.json",
    install_fn=_install,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="QwenCodeAdapter",
)
