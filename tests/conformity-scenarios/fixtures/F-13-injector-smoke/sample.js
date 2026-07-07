// Sample JavaScript module used as an F-13 injector smoke-test input.
// Pre-injection this file carries no header. The injector detects the
// ``.js`` suffix, resolves the double-slash variant, and prepends the
// single canonical ``// SPDX-License-Identifier: MIT`` line followed by
// one blank-line separator before this comment.

function hello() {
  return "hello";
}
