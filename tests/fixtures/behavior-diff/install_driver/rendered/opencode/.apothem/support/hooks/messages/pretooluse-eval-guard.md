<!-- SPDX-License-Identifier: MIT -->

Dynamic-eval / unsafe-deserialization guard — advisory prompt-injection defense.

> Advisory: this hook reports; it does not block. Mechanical enforcement runs in CI.

This guard is ADVISORY, not a correctness gate. It surfaces a flagged construct for the operator's decision; it never rewrites code on its own and never blocks on a false positive without a confirmation step. Its purpose is to intercept the prompt-injection and unsafe-eval attack surface before a construct that evaluates untrusted or model-derived input lands in the codebase, per the security-conscious-code discipline (no `eval` / `exec` on untrusted input).

## Scope

Fires on every Write, Edit, and Bash command that introduces dynamic evaluation or unsafe deserialization of a value flowing from an untrusted or model-derived source — a language-model prompt, a language-model response, a tool-call result, network input, or any other input the program does not control. The guard is language- and runtime-agnostic: it inspects the construct's shape, not any specific vendor or framework. Skip the scan when the target is inside the Apothem source repo's own fixture trees that document these patterns as test material.

## Trigger / inspected patterns

The hook flags a construct when a dynamic-evaluation or unsafe-deserialization primitive receives an argument that originates from an untrusted source:

- Dynamic code evaluation — `eval(`, `exec(`, `Function(` / `new Function(`, `compile(` followed by `exec`, or an equivalent eval primitive in the target language — applied to interpolated prompt or response text.
- Shell-out on interpolated text — `subprocess` / `child_process` / `os.system` / backtick or `Popen` invocations with `shell=True` (or the runtime's shell-on equivalent) where the command string interpolates model-derived or untrusted input.
- Unsafe deserialization — `pickle.loads`, `yaml.load` without a safe loader, `marshal.loads`, or an equivalent native-object deserializer applied to model output or network input.

The discriminator is the data-flow: the primitive is benign on a trusted literal and a finding on a value that traces back to a prompt, a response, a tool result, or external input.

## Action — advisory flag

On a flagged construct: surface it through the structured-inquiry channel per `rules/interactive-questions.md` with a single-select three-option set, annotated per the canonical option-set discipline at `rules/interactive-questions-canonical-shapes.md` (three-segment body; concrete-driver rationale on every non-neutral recommendation). Do not author the full YAML here.

- **refactor-to-safe (Recommended)** — replace the construct with a non-evaluating equivalent (dispatch table over `eval`, argument-vector subprocess over shell interpolation, safe loader over native deserialization). Recommended because it removes the attack surface rather than documenting it.
- **accept-with-justification** — proceed with the construct, recording a justification that names why the input is trusted or already sanitized.
- **cancel** — block the edit; no file is modified.

Every option carries `default-pointer: no-default: user decision required` — the guard proposes no silent default on a security-relevant construct.

## Fail-disposition

Two layers govern failure. (a) The Python dispatcher at `hooks/dispatch.py` is fail-open: a hook error — the inspection itself fails to complete, or any Python exception inside the predicate — converts to a structured failure envelope on stdout and the tool call proceeds, so a harness error never silently blocks it. (b) The assistant's interpretation of this context is fail-closed on a detected construct: when the scan flags a dynamic-evaluation or unsafe-deserialization primitive on untrusted input, the directive is to surface it through the structured-inquiry channel and let the operator decide before the construct lands. The two layers are non-redundant: the dispatcher protects the runtime, this context protects the security discipline, which is enforced mechanically in CI and pre-commit (`bare_except_grep` and the security matchers).

## Non-matching writes

No action. The guard is scoped to the dynamic-evaluation and unsafe-deserialization primitives above applied to untrusted input; every other construct passes unaffected.

## Bindings (§0.j five-direction)

- **Drives →** The advisory flag on dynamic evaluation or unsafe deserialization of untrusted or model-derived input in a Write, Edit, or Bash command.
- **Established by ↑** The PreToolUse Write, Edit, and Bash registrations in `hooks/hooks.json` and the harness settings templates. `rules/code-craft-conventions.md` (M13.8 security-conscious code: no `eval` or `exec` on untrusted input).
- **Cross-bound with ↔** `hooks/messages/pretooluse-dependency-guard.md` (the sibling advisory security guard on the same write tools).
