#!/usr/bin/env node
// SPDX-License-Identifier: MIT

// npx launcher for the apothem CLI.
//
// Locates a Python 3.10+ interpreter, points PYTHONPATH at the package's
// source tree (vendored dependencies first, then the engine), and executes
// `python -m apothem` with the caller's arguments. The engine requires the
// `click` and `rich` Python packages to be importable; every other runtime
// dependency ships vendored inside the tree. The engine entry point checks
// for click and rich itself, using the standard library only, and prints the
// exact pip command for the interpreter (or a JSON error under --json), so
// every channel reports a missing prerequisite the same way.

import { spawnSync } from "node:child_process";
import { delimiter, join } from "node:path";
import { fileURLToPath } from "node:url";

const MIN_PYTHON = [3, 10];

const packageRoot = fileURLToPath(new URL("..", import.meta.url));
const vendorPath = join(packageRoot, "src", "apothem", "_vendor");
const sourcePath = join(packageRoot, "src");

// The probe both enforces the version floor and rejects the Microsoft Store
// launcher shims (zero-byte stubs under AppData\Local\Microsoft\WindowsApps).
// Those stubs satisfy `python`/`py` on PATH but, when executed, open the Store
// install page instead of running Python — every other entry path (install.sh
// via hooks/lib/find-python.sh, install.ps1) already rejects them. `sys.executable`
// is printed so a real interpreter can be distinguished from a shim by path.
const versionProbe =
  "import sys; " +
  `sys.exit(1) if sys.version_info[:2] < (${MIN_PYTHON[0]}, ${MIN_PYTHON[1]}) else ` +
  "print(sys.executable or '')";

/** True when a resolved interpreter path is a Microsoft Store launcher shim. */
function isWindowsAppsShim(execPath) {
  return /[\\/]Microsoft[\\/]WindowsApps[\\/]/i.test(execPath);
}

/** Interpreter candidates, ordered; each is [command, ...leading args]. */
const candidates = [];
if (process.env.APOTHEM_PYTHON) {
  candidates.push([process.env.APOTHEM_PYTHON]);
}
candidates.push(["python3"], ["python"], ["py", "-3"]);

function probe(candidate) {
  const [command, ...lead] = candidate;
  const result = spawnSync(command, [...lead, "-c", versionProbe], {
    encoding: "utf8",
  });
  if (result.status !== 0) {
    return false;
  }
  // Reject the Store shim: it can exit 0 on the probe yet trigger a Store
  // popup (or fail) on the real invocation.
  const execPath = (result.stdout || "").trim();
  return !isWindowsAppsShim(execPath);
}

const interpreter = candidates.find(probe);
if (!interpreter) {
  process.stderr.write(
    "apothem: Python " +
      `${MIN_PYTHON[0]}.${MIN_PYTHON[1]}+` +
      " is required but no suitable interpreter was found.\n" +
      "Install Python from https://www.python.org/downloads/ or point the\n" +
      "APOTHEM_PYTHON environment variable at an interpreter, then retry.\n",
  );
  process.exit(1);
}

const [command, ...lead] = interpreter;
const env = {
  ...process.env,
  PYTHONPATH: [vendorPath, sourcePath, process.env.PYTHONPATH]
    .filter(Boolean)
    .join(delimiter),
};

const run = spawnSync(command, [...lead, "-m", "apothem", ...process.argv.slice(2)], {
  stdio: "inherit",
  env,
});

// A spawn-level failure (ENOENT: interpreter vanished between probe and run;
// EPERM: not executable) leaves `run.status` null with the cause in `run.error`
// — report it instead of exiting a bare 1. A signal termination likewise leaves
// `status` null; surface the signal so a killed child is not mistaken for a
// clean exit.
if (run.error) {
  process.stderr.write(
    `apothem: failed to run '${command}': ${run.error.message}\n`,
  );
  process.exit(1);
}
if (run.signal) {
  process.stderr.write(`apothem: interpreter terminated by signal ${run.signal}\n`);
  process.exit(1);
}
process.exit(run.status ?? 1);
