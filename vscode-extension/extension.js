// SPDX-License-Identifier: MIT

// Apothem VS Code extension — a thin wrapper that drives the Apothem engine
// from the editor. Each contributed command runs the configured Apothem runner
// (the npm shim by default) as a task at the workspace root, so the extension
// carries no engine logic of its own and always reflects the installed Apothem
// version. The same engine powers the CLI, the npm shim, and every harness
// adapter, so the VS Code surface stays in lock-step with them.
//
// Three rules keep a cloned repository from steering what runs:
// - The runner comes from user settings only. `apothem.runner` is declared
//   machine-scoped in package.json, and this file reads only its user (global)
//   value, so a workspace `.vscode/settings.json` cannot replace it.
// - Nothing is pasted into a shell as text. The runner and every argument,
//   including the workspace path, are passed to a ShellExecution as separate,
//   strongly quoted arguments, so `$(...)` or `;` in a path is never run.
// - Lifecycle commands ask which harness to act on, offering this editor's own
//   harness first. `all` is offered but never assumed.

const vscode = require('vscode');

// Contributed command id -> Apothem subcommand.
const SUBCOMMANDS = {
  'apothem.install': 'install',
  'apothem.verify': 'verify',
  'apothem.update': 'update',
  'apothem.uninstall': 'uninstall',
  'apothem.doctor': 'doctor',
};

// Lifecycle subcommands that take `--harness`. `doctor` checks every installed
// harness and takes only `--project`.
const HARNESS_SUBCOMMANDS = new Set(['install', 'verify', 'update', 'uninstall']);

const DEFAULT_RUNNER = 'npx @ahmed-g-gad/apothem';

// The VS Code-family harnesses, matched against the editor's application name.
// The first entry is the fallback for VS Code itself.
const EDITOR_HARNESSES = [
  { id: 'github-copilot', appName: /visual studio code|vscodium|code - oss/i },
  { id: 'cursor', appName: /cursor/i },
  { id: 'windsurf', appName: /windsurf/i },
];

// A harness id typed by hand: lowercase letters, digits and hyphens.
const HARNESS_ID = /^[a-z0-9][a-z0-9-]*$/;
const OTHER_HARNESS = 'Other harness…';

/**
 * The runner as argument tokens, from the user's (global) setting only.
 * A workspace or folder value is ignored even if the editor would offer one.
 */
function runnerTokens() {
  const inspected = vscode.workspace.getConfiguration('apothem').inspect('runner') || {};
  const configured =
    typeof inspected.globalValue === 'string' && inspected.globalValue.trim()
      ? inspected.globalValue
      : DEFAULT_RUNNER;
  return configured.trim().split(/\s+/);
}

/** The harness id of the editor this extension runs in. */
function editorHarness() {
  const appName = vscode.env.appName || '';
  const match = EDITOR_HARNESSES.find((harness) => harness.appName.test(appName));
  return (match || EDITOR_HARNESSES[0]).id;
}

/** Ask which harness to act on; resolves to undefined when cancelled. */
async function pickHarness(subcommand) {
  const preferred = editorHarness();
  const items = [
    { label: preferred, description: 'this editor' },
    ...EDITOR_HARNESSES.filter((harness) => harness.id !== preferred).map((harness) => ({
      label: harness.id,
    })),
    { label: OTHER_HARNESS, description: 'type a harness name' },
    { label: 'all', description: 'every supported harness, including your home directory' },
  ];
  const picked = await vscode.window.showQuickPick(items, {
    placeHolder: `Which harness should Apothem ${subcommand}?`,
    ignoreFocusOut: true,
  });
  if (!picked) {
    return undefined;
  }
  if (picked.label !== OTHER_HARNESS) {
    return picked.label;
  }
  const typed = await vscode.window.showInputBox({
    prompt: 'Harness name (run "apothem harnesses list" for the names)',
    validateInput: (value) =>
      HARNESS_ID.test(value.trim()) ? undefined : 'Use a harness name such as claude-code.',
  });
  return typed && HARNESS_ID.test(typed.trim()) ? typed.trim() : undefined;
}

/** The command and argument list for one Apothem invocation. */
function buildInvocation(tokens, subcommand, harness, workspaceFolder) {
  const args = [...tokens.slice(1), subcommand];
  if (harness) {
    args.push('--harness', harness);
  }
  if (workspaceFolder) {
    args.push('--project', workspaceFolder);
  }
  return { command: tokens[0], args };
}

async function run(subcommand) {
  let harness;
  if (HARNESS_SUBCOMMANDS.has(subcommand)) {
    harness = await pickHarness(subcommand);
    if (!harness) {
      return;
    }
  }
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const { command, args } = buildInvocation(runnerTokens(), subcommand, harness, workspaceFolder);
  const strong = (value) => ({ value, quoting: vscode.ShellQuoting.Strong });
  const execution = new vscode.ShellExecution(
    strong(command),
    args.map(strong),
    workspaceFolder ? { cwd: workspaceFolder } : undefined,
  );
  const task = new vscode.Task(
    { type: 'apothem', subcommand },
    vscode.TaskScope.Workspace,
    `apothem ${subcommand}`,
    'apothem',
    execution,
  );
  await vscode.tasks.executeTask(task);
}

function activate(context) {
  for (const [command, subcommand] of Object.entries(SUBCOMMANDS)) {
    context.subscriptions.push(
      vscode.commands.registerCommand(command, () => run(subcommand)),
    );
  }
}

function deactivate() {}

module.exports = { activate, deactivate, buildInvocation };
