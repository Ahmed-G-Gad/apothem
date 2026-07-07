# SPDX-License-Identifier: MIT

"""The self-contained plugin runtime — the assembled tree imports the engine
and its vendored dependencies directly; no package installation occurs.

The plugin-first distribution model assembles the engine + catalog into a
self-contained tree and runs it by prepending the tree's ``lib/`` to
``sys.path`` — no editable install, no package installation. This test
assembles a real tree from the in-repo source, then drives a *fresh*
subprocess that imports the engine and discovers every adapter purely from
the assembled tree, asserting the loaded engine resolves to the bundled copy
rather than any site-packages install.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from apothem.lib.harness_registry import SUPPORTED_HARNESS_COUNT
from apothem.lib.plugin_tree import assemble_plugin_tree

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENGINE_SRC = _REPO_ROOT / "src" / "apothem"
_EXPECTED_ADAPTER_COUNT = SUPPORTED_HARNESS_COUNT

# Runs inside the fresh subprocess: prepend ONLY the bundled tree's lib/,
# import the engine, exercise the real bootstrap shim, discover adapters.
_PROBE = r"""
import json, sys
from pathlib import Path

tree = Path(sys.argv[1])
lib = tree / "lib"
sys.path.insert(0, str(lib))  # the self-contained bootstrap action

import apothem
import apothem_lib
from apothem.lib.plugin_bootstrap import bootstrap_syspath

bootstrap_syspath(tree)  # idempotent; exercises the shipped shim

from apothem.lib.harness_registry import discover_adapters

adapters = discover_adapters(lib / "apothem")
print(json.dumps({
    "apothem_file": apothem.__file__,
    "apothem_lib_profile": hasattr(apothem_lib, "profile"),
    "apothem_lib_adapters": hasattr(apothem_lib, "adapters"),
    "adapter_names": sorted(adapters),
}))
"""


def test_bundled_tree_runs_engine_without_install(tmp_path: Path) -> None:
    """Assemble a plugin tree and run the engine from it in a clean subprocess."""
    plugin_root = assemble_plugin_tree(_ENGINE_SRC, tmp_path / "plugin")

    # A clean environment: no PYTHONPATH pointing at the repo source, and a
    # working directory outside the repo — so the ONLY route to the bundled
    # engine is the tree-lib prepend the probe performs.
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE, str(plugin_root)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        timeout=120,
    )

    assert completed.returncode == 0, (
        f"probe failed (exit {completed.returncode}):\n"
        f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
    )
    result = json.loads(completed.stdout.strip().splitlines()[-1])

    # The engine loaded from the bundled tree, not from site-packages.
    bundled_engine = (plugin_root / "lib" / "apothem").resolve()
    assert Path(result["apothem_file"]).resolve().is_relative_to(bundled_engine), (
        f"engine loaded from {result['apothem_file']}, "
        f"expected under bundled {bundled_engine}"
    )

    # The apothem_lib alias surface re-exports the engine submodules.
    assert result["apothem_lib_profile"] is True
    assert result["apothem_lib_adapters"] is True

    # Every adapter resolves by filesystem convention from the bundled tree.
    assert len(result["adapter_names"]) == _EXPECTED_ADAPTER_COUNT, (
        f"discovered {result['adapter_names']}"
    )
    assert "claude-code" in result["adapter_names"]
