# SPDX-License-Identifier: MIT

"""The VS Code extension runs a user-scoped runner, quoted, for a chosen harness.

The extension read ``apothem.runner`` with no scope (a cloned repository's
``.vscode/settings.json`` could set it), pasted it and the workspace path into
an integrated terminal with ``sendText`` (so ``$(...)`` in a path expanded),
and defaulted every lifecycle command to ``--harness all``.

The tests drive ``vscode-extension/extension.js`` under node with a stubbed
``vscode`` module and record what it would run. Skipped without node.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_EXTENSION_DIR = Path(__file__).resolve().parents[2] / "vscode-extension"
_NODE = shutil.which("node")

_VSCODE_STUB = r"""
const state = globalThis.__apothemStub;
class ShellExecution {
  constructor(command, args, options) {
    this.command = command; this.args = args; this.options = options;
  }
}
class Task {
  constructor(definition, scope, name, source, execution) {
    Object.assign(this, { definition, scope, name, source, execution });
  }
}
module.exports = {
  ShellExecution,
  Task,
  ShellQuoting: { Escape: 1, Strong: 2, Weak: 3 },
  TaskScope: { Global: 1, Workspace: 2 },
  env: { appName: state.appName },
  workspace: {
    workspaceFolders: state.folder ? [{ uri: { fsPath: state.folder } }] : undefined,
    getConfiguration: () => ({
      get: (key, fallback) => state.runnerSetting ?? fallback,
      inspect: () => state.inspect,
    }),
  },
  window: {
    terminals: [],
    createTerminal: () => ({
      show() {},
      sendText(text) { state.record.sendText.push(text); },
    }),
    showQuickPick: async (items) => {
      state.record.quickPick.push(items.map((item) => item.label ?? item));
      return state.pick === null ? undefined : items.find((i) => (i.label ?? i) === state.pick);
    },
    showInputBox: async () => state.input,
  },
  tasks: {
    executeTask: async (task) => { state.record.tasks.push(task); },
  },
  commands: {
    registerCommand: (id, handler) => { state.handlers[id] = handler; return {}; },
  },
};
"""

_DRIVER = r"""
const [extensionPath, stateJson, commandId] = process.argv.slice(2);
globalThis.__apothemStub = Object.assign(JSON.parse(stateJson), {
  record: { sendText: [], quickPick: [], tasks: [] },
  handlers: {},
});
const extension = require(extensionPath);
extension.activate({ subscriptions: [] });
Promise.resolve(globalThis.__apothemStub.handlers[commandId]()).then(() => {
  const { record } = globalThis.__apothemStub;
  process.stdout.write(JSON.stringify({
    sendText: record.sendText,
    quickPick: record.quickPick,
    tasks: record.tasks.map((t) => ({
      command: t.execution.command,
      args: t.execution.args,
      options: t.execution.options,
    })),
  }));
});
"""

pytestmark = pytest.mark.skipif(_NODE is None, reason="node is not on PATH")


def _run(tmp_path: Path, command_id: str, **state: object) -> dict:
    stub_dir = tmp_path / "node_modules" / "vscode"
    stub_dir.mkdir(parents=True, exist_ok=True)
    (stub_dir / "index.js").write_text(_VSCODE_STUB, encoding="utf-8")
    driver = tmp_path / "driver.js"
    driver.write_text(_DRIVER, encoding="utf-8")
    defaults: dict[str, object] = {
        "appName": "Visual Studio Code",
        "folder": "/work/project",
        "inspect": {"defaultValue": "npx @ahmed-g-gad/apothem"},
        "pick": "github-copilot",
        "input": None,
    }
    defaults.update(state)
    assert _NODE is not None
    result = subprocess.run(
        [
            _NODE,
            str(driver),
            str(_EXTENSION_DIR / "extension.js"),
            json.dumps(defaults),
            command_id,
        ],
        capture_output=True,
        text=True,
        env={"NODE_PATH": str(tmp_path / "node_modules"), "PATH": ""},
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _argv(record: dict) -> list[str]:
    (task,) = record["tasks"]
    return [task["command"]["value"], *(arg["value"] for arg in task["args"])]


def test_runner_setting_is_machine_scoped() -> None:
    manifest = json.loads((_EXTENSION_DIR / "package.json").read_text(encoding="utf-8"))
    runner = manifest["contributes"]["configuration"]["properties"]["apothem.runner"]
    assert runner["scope"] == "machine"
    assert runner["default"] == "npx @ahmed-g-gad/apothem"
    assert manifest["capabilities"]["untrustedWorkspaces"]["supported"] is False


def test_workspace_runner_value_is_ignored(tmp_path: Path) -> None:
    record = _run(
        tmp_path,
        "apothem.install",
        runnerSetting="touch /tmp/pwned;",
        inspect={
            "defaultValue": "npx @ahmed-g-gad/apothem",
            "workspaceValue": "touch /tmp/pwned;",
            "workspaceFolderValue": "touch /tmp/pwned;",
        },
    )
    assert record["sendText"] == []
    assert _argv(record)[:3] == ["npx", "@ahmed-g-gad/apothem", "install"]


def test_user_runner_value_is_used(tmp_path: Path) -> None:
    record = _run(
        tmp_path,
        "apothem.verify",
        inspect={
            "defaultValue": "npx @ahmed-g-gad/apothem",
            "globalValue": "python -m apothem",
        },
    )
    assert _argv(record)[:4] == ["python", "-m", "apothem", "verify"]


def test_install_asks_for_a_harness_and_offers_the_editor_first(tmp_path: Path) -> None:
    record = _run(tmp_path, "apothem.install", appName="Cursor", pick="cursor")
    (labels,) = record["quickPick"]
    assert labels[0] == "cursor"
    assert "all" in labels
    argv = _argv(record)
    assert argv[argv.index("--harness") + 1] == "cursor"
    assert "all" not in argv


def test_cancelled_pick_runs_nothing(tmp_path: Path) -> None:
    record = _run(tmp_path, "apothem.update", pick=None)
    assert record["tasks"] == []
    assert record["sendText"] == []


def test_workspace_path_is_one_strongly_quoted_argument(tmp_path: Path) -> None:
    folder = "/work/$(touch pwned) project"
    record = _run(tmp_path, "apothem.uninstall", folder=folder)
    (task,) = record["tasks"]
    project = next(
        task["args"][i + 1]
        for i, arg in enumerate(task["args"])
        if arg["value"] == "--project"
    )
    assert project == {"value": folder, "quoting": 2}
    assert all(arg["quoting"] == 2 for arg in task["args"])
    assert task["options"] == {"cwd": folder}


def test_doctor_asks_nothing_and_scopes_the_project(tmp_path: Path) -> None:
    record = _run(tmp_path, "apothem.doctor")
    assert record["quickPick"] == []
    assert _argv(record) == [
        "npx",
        "@ahmed-g-gad/apothem",
        "doctor",
        "--project",
        "/work/project",
    ]
