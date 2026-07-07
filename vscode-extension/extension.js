// SPDX-License-Identifier: MIT

// Apothem VS Code extension — a thin wrapper that drives the Apothem engine
// from the editor. Each contributed command runs the configured Apothem runner
// (the npm shim by default) in an integrated terminal at the workspace root, so
// the extension carries no engine logic of its own and always reflects the
// installed Apothem version. The same engine powers the CLI, the npm shim, and
// every harness adapter, so the VS Code surface stays in lock-step with them.

const vscode = require('vscode');

// Contributed command id -> Apothem subcommand.
const SUBCOMMANDS = {
  'apothem.install': 'install',
  'apothem.verify': 'verify',
  'apothem.update': 'update',
  'apothem.uninstall': 'uninstall',
  'apothem.doctor': 'doctor',
};

// Lifecycle subcommands whose `--harness` flag is required (name-or-'all').
// The extension defaults them to `--harness all` so the terminal command runs
// without the operator having to name a harness. `doctor` takes no `--harness`
// (nor `--project`) and is intentionally absent.
const HARNESS_SUBCOMMANDS = new Set(['install', 'verify', 'update', 'uninstall']);

// The single reused terminal name, so repeated commands share one terminal.
const TERMINAL_NAME = 'Apothem';

function runnerCommand() {
  return vscode.workspace
    .getConfiguration('apothem')
    .get('runner', 'npx @ahmed-g-gad/apothem');
}

function run(subcommand) {
  const existing = vscode.window.terminals.find((t) => t.name === TERMINAL_NAME);
  const terminal = existing || vscode.window.createTerminal(TERMINAL_NAME);
  terminal.show();

  const args = [];
  // Lifecycle subcommands require `--harness`; default to every harness so the
  // command runs without the operator naming one. `doctor` takes no `--harness`.
  if (HARNESS_SUBCOMMANDS.has(subcommand)) {
    args.push('--harness', 'all');
    // Scope project-scope harnesses to the open workspace folder when present.
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (workspaceFolder) {
      args.push('--project', `"${workspaceFolder}"`);
    }
  }

  const suffix = args.length ? ` ${args.join(' ')}` : '';
  terminal.sendText(`${runnerCommand()} ${subcommand}${suffix}`);
}

function activate(context) {
  for (const [command, subcommand] of Object.entries(SUBCOMMANDS)) {
    context.subscriptions.push(
      vscode.commands.registerCommand(command, () => run(subcommand)),
    );
  }
}

function deactivate() {}

module.exports = { activate, deactivate };
