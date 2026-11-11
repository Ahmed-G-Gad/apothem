<!-- SPDX-License-Identifier: MIT -->

# OpenCode Standard Convention Pin

## Snapshot

- Snapshot date: 2026-11-09
- Snapshot note (`opencode.jsonc`): the v1.19.5, v2.2.5 and v2.2.6 source were read on 2026-11-09, with the global configuration fold checked back to v1.0.0 (see the 2026-11-09 source bullet under Vendor Sources). OpenCode 1 lets an `instructions` list in `opencode.jsonc` replace the one in the `opencode.json` the install writes, and OpenCode 2 joins the two, so install, update and verify print a note for such a file. A `config.json`, `opencode.json` or `opencode.jsonc` in that folder that OpenCode 1 cannot parse, whose top level is not an object, whose `instructions` is not a list of strings, whose `{file:path}` names a file it cannot read, or that it cannot read for a reason it does not skip, stops it with an error before it loads any configuration, so each such file gets a note too. OpenCode 2 reads no `config.json`, skips a file it cannot parse or whose top level is not an object, escapes `{env:NAME}` values the text would not parse with, puts in empty text for a `{file:path}` it cannot read, ignores an `instructions` value that is not a list and drops the items of a list that are not strings; each note says which applies. Previous 2026-11-03.
- Snapshot note (OpenCode 2): the OpenCode 2 docs and the v1.19.5 and v2.2.5 source were read on 2026-11-03 (see OpenCode 2 below). The install now writes only `deny` helper rules, writes each MCP `${NAME}` as `{env:NAME}`, installs into `$XDG_CONFIG_HOME/opencode` when that names an absolute folder, warns when `OPENCODE_CONFIG_DIR` names another folder, and finds an MCP server an operator converted to OpenCode 2's `mcp.servers` shape. Previous 2026-10-14.
- Snapshot note (CLAUDE.md fallback): the rules page and the OpenCode 2 Instructions page were read on 2026-11-03, with the instruction loaders in the v1.19.5 and v2.2.5 source. OpenCode 1 loads `~/.claude/CLAUDE.md` only when no `<config dir>/AGENTS.md` exists; the config dir is `OPENCODE_CONFIG_DIR` when set, else `$XDG_CONFIG_HOME/opencode`, so `~/.config/opencode` by default. `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1` or `OPENCODE_DISABLE_CLAUDE_CODE=1` turns that read off. OpenCode 2, first published as a GitHub Release with v2.2.0 on 2026-10-27 (npm `@opencode/cli` has carried 2.x since 2.0.0 on 2026-09-11), reads the same `~/.config/opencode/` configuration but discovers only `AGENTS.md` files, with no `CLAUDE.md` fallback. The installer at `opencode.ai/install` and the `opencode-ai` npm package still install OpenCode 1. Previous 2026-10-14.
- Snapshot note: refreshed against `opencode.ai/docs` (config, rules, skills, agents, commands, MCP servers, tools), and the `instructions` path semantics re-observed at opencode-ai 1.19.0 (see Vendor Sources). `opencode.json` sources (global `~/.config/opencode/opencode.json` plus project), Markdown agents and commands in plural `agents/` and `commands/` directories, `skills/<name>/SKILL.md`, the `instructions` key, plugins in `.opencode/plugins/` or `~/.config/opencode/plugins/`, and the `webfetch` / `websearch` tools are confirmed. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/opencode/`
- Evidence level: vendor-doc pinned for `opencode.json` and its
  `instructions` / `agent` / `command` / `mcp` / `plugin` keys; skills are a
  documented native surface; plugins are vendor-native and operator-owned; the
  native config is rendered directly (no Jinja template). OpenCode also loads
  `~/.claude/skills/` and `~/.agents/skills/`, so the Claude Code and Codex
  skill installs reach it, and OpenCode 1 loads `~/.claude/CLAUDE.md` when its
  configuration folder holds no `AGENTS.md`, so the Claude Code install's block
  reaches it too (shared roots in the registry). No vendor-native UI
  claim is made here. Rolling docs carry no version or SHA — no-immutable-source
  exception on every source row.
- Official references:
  - <https://opencode.ai/docs/config/>
  - <https://opencode.ai/docs/rules/>
  - <https://opencode.ai/v2/docs/instructions/>
  - <https://opencode.ai/docs/agents/>
  - <https://opencode.ai/docs/commands/>
  - <https://opencode.ai/docs/mcp-servers/>
  - <https://opencode.ai/docs/skills/>
  - <https://opencode.ai/docs/plugins/>

## Web-Fetch / Browser-Retrieval Surface

- Capability: `web_fetch` = **partial**. The backing dimension for
  `rules/source-accessibility.md` step 1 ("retrieve through the host's browser /
  fetch capability").
- Vendor-confirmed PARTIAL: opencode ships an unconditional built-in `webfetch`
  tool (fetch + read web pages), but the `websearch` tool is available only when
  using the OpenCode provider or when the `OPENCODE_ENABLE_EXA` env var is set.
  The `partial` subset boundary is: fetch always-on, search provider/env-gated.
- Evidence: vendor-doc-url <https://opencode.ai/docs/tools/>; snapshot-id living
  docs; snapshot-date 2026-06-21 (the URL still resolves on 2026-10-03).

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://opencode.ai/docs/config/> (config sources, plural directories, plugins)
- <https://opencode.ai/docs/rules/> (`AGENTS.md` and `instructions`; the `~/.claude/CLAUDE.md` fallback when no `~/.config/opencode/AGENTS.md` exists, and the `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT` and `OPENCODE_DISABLE_CLAUDE_CODE` opt-outs, retrieved 2026-11-03)
- <https://opencode.ai/v2/docs/instructions/> (OpenCode 2 discovers only `AGENTS.md` files, with no `CLAUDE.md` fallback; retrieved 2026-11-03)
- Installer script, read 2026-11-03: `opencode.ai/install` redirects to `raw.githubusercontent.com/anomalyco/opencode/refs/heads/v1/install`, the `install` file on the `v1` branch of `anomalyco/opencode`. With no version given, it installs the version that the `opencode-ai` npm package's `latest` tag names when that is a 1.x release, else the newest v1 release on GitHub, and it refuses a requested version of 2 or later.
- Source read, 2026-11-03: in v1.19.5, `packages/opencode/src/session/instruction.ts` takes the first of `<config dir>/AGENTS.md` and `~/.claude/CLAUDE.md` that exists, and `packages/core/src/global.ts` sets the config dir to `OPENCODE_CONFIG_DIR` when set, else `$XDG_CONFIG_HOME/opencode`. In v2.2.5, `packages/core/src/config/plugin/instruction.ts` discovers only `AGENTS.md` files (<https://github.com/anomalyco/opencode/tree/v1.19.5>, <https://github.com/anomalyco/opencode/tree/v2.2.5>).
- Source read, 2026-11-09 (the `opencode.jsonc` note): in v1.19.5 (commit
  `810c0eba1a7348036f8bdf61e6632d0c36c6876c`, the newest v1 release and the
  `opencode-ai` npm `latest` tag on 2026-11-09),
  `packages/opencode/src/config/config.ts:272-274` loads `config.json`,
  `opencode.json` and then `opencode.jsonc` from the global folder, the last as
  `result = mergeConfig(result, yield* loadFile(path.join(Global.Path.config,
  "opencode.jsonc"), env))`. `mergeConfig` is remeda's `mergeDeep`
  (`config.ts:42-44`; remeda 2.26.0, `packages/remeda/src/mergeDeep.ts`, `const
  output = { ...destination, ...source }`), so a later list replaces the earlier
  one, an empty list too. Only `mergeConfigConcatArrays` joins `instructions`
  (`merged.instructions = Array.from(new Set([...target.instructions,
  ...source.instructions]))`, `config.ts:46-52`), and it merges the folded
  global result, the `OPENCODE_CONFIG` file, project files and the
  `OPENCODE_CONFIG_DIR` folder (`config.ts:365-366, 412-446`). `OPENCODE_CONFIG`
  is read after the global result (`if (Flag.OPENCODE_CONFIG) { yield*
  merge(Flag.OPENCODE_CONFIG, yield* loadFile(Flag.OPENCODE_CONFIG, authEnv))`,
  `config.ts:415-416`; the flag is `process.env["OPENCODE_CONFIG"]`,
  `packages/core/src/flag/flag.ts:21`), so naming the written `opencode.json`
  there joins its list back. `packages/opencode/src/config/paths.ts` lists the
  global folder first in `directories`, and `config.ts:438-446` reads
  `opencode.json` and `opencode.jsonc` again with that join when
  `OPENCODE_CONFIG_DIR` names it. Earlier v1 releases, read the same day: the
  global fold is the same in v1.0.0 (commit `b9a39b81`, `config.ts:679-681`),
  v1.0.100 (commit `37bb07e7`, `config.ts:657-659`), v1.1.4 (commit `b2341c2d`,
  `config.ts:980-986`) and v1.18.35 (commit `53d1eabb`, `config.ts:272-274`).
  The `OPENCODE_CONFIG_DIR` folder is read again with the join in v1.1.4
  (`config.ts:96-99`) and v1.18.35 (`config.ts:439-440`); v1.0.100 reads it
  again with `mergeDeep`, `opencode.jsonc` first and `opencode.json` last
  (`config.ts:78-81`), so the written list replaces the other; v1.0.0 pushes
  that folder onto `directories` but reads only commands, agents, modes and
  plugins there (`config.ts:75-88`), so the `opencode.jsonc` list still hides
  the written one and the install gives no note for it. `OPENCODE_CONFIG` is
  read after the global fold in every one of these (v1.0.0 `config.ts:40`,
  v1.0.100 `config.ts:30`, with `mergeDeep`; v1.1.4 `config.ts:44`, with the
  join). Parsing: v1.19.5 reads the file with `FSUtil.readFileStringSafe`
  (`packages/core/src/fs-util.ts:62-67`, a missing or unreadable file gives
  `undefined`, which `loadFile` reads as `{}`, `config.ts:253-257`), which calls
  Effect's `readFileString` (`effect` 4.0.0-beta.83, the version in the root
  `package.json` catalog; `Effect-TS/effect-smol` tag `effect@4.0.0-beta.83`,
  `packages/effect/src/FileSystem.ts:782`, `new
  TextDecoder(encoding).decode(_)`). A default `TextDecoder` drops a leading
  byte order mark and replaces bytes that are not UTF-8 instead of failing
  (WHATWG Encoding Standard,
  <https://encoding.spec.whatwg.org/#interface-textdecoder>). The text is then
  parsed by jsonc-parser 3.3.1 with `parseJsoncImpl(text, errors, {
  allowTrailingComma: true })` (`packages/opencode/src/config/parse.ts:10`), and
  `parse.ts:11-31` throws `JsonError` on any parse error; `parse.ts:35-61`
  throws `InvalidError` when the schema does not match, and the schema types
  `instructions` as
  `Schema.optional(Schema.mutable(Schema.Array(Schema.String)))`
  (`packages/core/src/v1/config/config.ts:124`). So OpenCode 1 refuses an
  `opencode.jsonc` that is not JSONC or whose `instructions` is not a list of
  strings, and loads none of the global configuration. Install, update and
  verify note both cases, for `config.json` and `opencode.json` too (see the
  parse-failure source bullet below).
  OpenCode 2: in v2.2.6 (commit `dc2ffcf8bf26f9e669b6aa22b95f50e12be15e06`) and
  v2.2.5 (commit `9bbb8ce18c80f099e0e448775f59d965ead40a21`),
  `packages/core/src/config.ts:266-273` (`loadDirectory`) loads each name in
  `ConfigDiscovery.names` as its own document, `config.ts:330` loads the global
  folder that way, `packages/core/src/config/discovery.ts:12` names only
  `opencode.json` and `opencode.jsonc`, and
  `packages/core/src/config/plugin/instruction.ts:155` joins every document's
  list (`new Set(entries.flatMap((entry) => (entry.type === "document" ?
  (entry.info.instructions ?? []) : [])))`; the file is the same in both tags).
  v2.2.6 `config.ts:138` parses JSONC the same way, `parse(text, errors, {
  allowTrailingComma: true })`. So install, update and verify note an
  `opencode.jsonc` with a top-level `instructions` list of strings beside the
  `opencode.json` they write, for OpenCode 1 only, unless `OPENCODE_CONFIG_DIR`
  names that folder or `OPENCODE_CONFIG` names that `opencode.json`. No OpenCode
  binary was run, and no upstream test covers two global files replacing a list
  (<https://github.com/anomalyco/opencode/tree/v1.19.5>,
  <https://github.com/anomalyco/opencode/tree/v2.2.6>).
- Source read, 2026-11-09 (the note for a `config.json`, `opencode.json` or
  `opencode.jsonc` OpenCode 1 cannot load): in v1.19.5 and v1.18.35 (`parse.ts`
  is the same in both tags), `ConfigParse.jsonc` parses with only
  `allowTrailingComma` (`packages/opencode/src/config/parse.ts:10`) and throws
  `JsonError` on any parse error (`parse.ts:26`). `loadFile` returns `{}` for
  empty text before replacing any token and parsing (`if (!text) return {} as
  Info`, `config.ts:255-256`), and `loadGlobal` reads all three global files
  every time (`config.ts:272-274`). Each parsed document then goes through
  `decodeConfig` (`config.ts:188-199`): `ConfigV2Compat.lower` passes a document
  that is not a record through unchanged
  (`packages/opencode/src/config/v2-compat.ts:91-93`), and `ConfigParse.schema`
  throws `InvalidError` when `ConfigV1.Info`, a `Schema.Struct`
  (`packages/core/src/v1/config/config.ts:32`), does not match
  (`parse.ts:35-61`). For a struct, `effect` 4.0.0-beta.83 refuses a top level
  that is not an object, an array or `null` included
  (`packages/effect/src/SchemaAST.ts:2065`); for `instructions` it refuses
  anything but an array (`SchemaAST.ts:1628`), whose items must be strings
  (`v1/config/config.ts:124`). `decodeConfig` is itself an `Effect.fnUntraced`
  generator (`config.ts:188`), which `loadConfig` yields at `config.ts:241`, so
  its throw (`parse.ts:48`) stops the configuration the same way. The check
  looks at these two shapes only; other keys the schema refuses, and the
  OpenCode 2 `permissions` key `lower` refuses (`v2-compat.ts:106-113`), get no
  note. The parse and schema throws happen inside Effect generators
  (`parse.ts:26` in `loadConfig`, `parse.ts:48` in `decodeConfig`), which
  `effect` 4.0.0-beta.83 turns into a defect
  (`packages/effect/src/internal/effect.ts:646-650`, `exitDie`); the `failed to
  load global config, using defaults` fallback is `Effect.orElseSucceed`
  (`config.ts:297-300`), which catches only typed failures
  (`internal/effect.ts:2456` and `:3209`), and `config.ts:412` calls
  `loadGlobal` directly when an auth environment is set (with no fallback at
  all) and the cached `getGlobal` otherwise, and the config state applies
  `Effect.orDie` (`config.ts:616`), so `Config.get` fails and OpenCode 1 loads
  none of its configuration, the `opencode.json` instructions included. The text
  parsed is the file's text after `ConfigVariable.substitute`
  (`config.ts:233-240`; `packages/opencode/src/config/variable.ts:34-38` puts in
  each `{env:NAME}` value unescaped, or nothing, and `variable.ts:40-89` puts in
  each `{file:path}` file's text, trimmed with JavaScript's `trim()`, as the
  inside of a JSON string, leaving a token on a line whose text before it starts
  with `//` after `trimStart()`), so Apothem parses after the same replacement,
  with its own environment and the same whitespace set (ECMA-262 WhiteSpace and
  LineTerminator, which holds U+FEFF but not U+0085 or U+001C-U+001F, unlike
  Python's `str.strip()`). OpenCode 1 resolves a relative `{file:path}` with
  Node's `path.resolve(configDir, ...)` and a `~/` one with
  `path.join(os.homedir(), ...)` (`variable.ts:61-66`), which drop `.` and `..`
  from the text before the system sees it, so on Linux and macOS the check
  normalizes those paths the same way (Windows does already); `path.join` keeps
  a trailing `/`, and the check keeps it too. An absolute path is used exactly
  as written (`variable.ts:66`), and the check opens it that way, not through
  `pathlib`, which drops a trailing `/` or `/.`: on Linux and macOS the system
  refuses a regular file named with either (`ENOTDIR`), which
  `Filesystem.readText` (`packages/opencode/src/util/filesystem.ts:40-41`,
  `fs/promises` `readFile`) passes on, so OpenCode 1 stops with a `bad file
  reference`. On Windows a `{file:path}` rooted without a drive letter is read
  on the drive OpenCode 1 runs from (`path.isAbsolute` is true for it), which
  the check cannot know, so the check does not read it. OpenCode 2 (v2.2.6)
  also puts the `{env:NAME}` values in
  unescaped, but when that text holds `{env:` and fails jsonc-parser it
  substitutes again with each value escaped by
  `JSON.stringify(value).slice(1, -1)`
  (`packages/core/src/config/variable.ts:27-37`). So a value with a
  backslash (a Windows path), a double quote or a control character can stop
  OpenCode 1 alone; the check runs the same escaped parse, and when it succeeds
  the note says the `{env:NAME}` values break the file and checks the shape of
  the escaped document: a top level that is not an object is refused by
  OpenCode 1 once the values change and skipped by OpenCode 2
  (`normalize.ts:57-64`), and an `instructions` value that is not a list of
  strings is refused by OpenCode 1 and ignored or trimmed by OpenCode 2, so
  the note says so instead of offering the value change alone. Apothem writes
  an `{env:NAME}` into the `mcp` block of `opencode.json` for each `${NAME}`
  in a profile MCP server's environment, headers or URL, and an update writes
  it back when it is removed, so for such a reference, found in what the
  install record says Apothem owns there, the note names the server and the
  `harnesses.opencode.mcp_servers.<name>` override with the value as
  `{file:path}`, as the install's MCP note does. With a Windows folder such as
  `C:\Users\name\AppData\Roaming` in the variable, OpenCode 1 cannot parse the
  `opencode.json` Apothem writes: jsonc-parser 3.3.1 reports
  `InvalidEscapeCharacter` for `\U` (`lib/esm/impl/scanner.js:145`,
  `lib/esm/impl/parser.js:400-401`; run 2026-11-10 with Node 26.7.0 over an
  `opencode.json` an isolated install rendered), while a value whose
  backslashes all start JSON escapes, such as `C:\new\tmp`, parses into other
  text. OpenCode 1 also takes `{env:NAME}` values from the well-known
  `opencode auth` entries (`variable.ts:37`, `config.ts:370-374` and `:412`),
  which Apothem cannot see. A `{file:path}` naming a file it cannot read, inside
  a `/* */` comment too, throws `InvalidError` (`bad file reference`,
  `variable.ts:67-82`, since `missing` defaults to `error` at `variable.ts:35`);
  `loadConfig` runs `substitute` in `Effect.promise` (`config.ts:233-239`),
  which turns the rejection into a defect, so the install notes it as well.
  v1.0.0 `config.ts` `load()` also replaces both before parsing, but finds a
  commented `{file:path}` by the first line that holds it and puts in the text
  with a string-pattern `replace` (`config.ts:722-757`), so its result can
  differ for a token written twice or a file holding `$'`. OpenCode's own test
  `throws error for invalid JSON`
  (`packages/opencode/test/config/config.test.ts:799-805`) expects a parse
  failure for a project file. The CLI commands that format the error with
  `FormatError` report it as `Config file at <path> is not valid JSON(C)`
  followed by the file and the errors (`packages/opencode/src/cli/error.ts:82`;
  the same text in v1.0.0 `cli/error.ts:11`), and a schema error or a bad file
  reference as `Configuration is invalid at <path>` (`error.ts:109-118`); the
  TUI was not checked, so the note names each error without quoting it. v1.0.0
  fails the same way: the three global files are read in one promise
  (`config.ts:676-682`) and a parse error throws `JsonError`
  (`config.ts:761-783`). jsonc-parser 3.3.1, run with OpenCode's options on
  2026-11-09, reports an error for unquoted keys, single quotes, `NaN`, plain
  text, a block comment never closed, two top-level values, a comma with no
  value before it (`[,]`), and text that holds only whitespace or only comments
  (`ValueExpected`, `lib/esm/impl/parser.js:601-606`, since OpenCode does not
  set `allowEmptyContent`, so a file whose tokens put in nothing fails too); it
  reports none for comments or trailing commas, and it counts only space and tab
  as whitespace on a line (`lib/esm/impl/scanner.js:352-354`). A byte order mark
  alone is dropped by `TextDecoder` (`effect` `FileSystem.ts:782`), so such a
  file reads as `{}` in v1.18.35 and later; v1.0.0 through at least v1.1.4 read
  with `Bun.file().text()` (v1.1.4 `config.ts:1006-1016`), and whether that
  drops it was not checked, so the docs say this of current releases only.
  Reading: v1.19.5 `readFileStringSafe` skips only `NotFound` and
  `PermissionDenied` (`packages/core/src/fs-util.ts:62-67`); the
  `PermissionDenied` skip first appears in v1.17.15 (commit `5fb0d1cd`,
  `fs-util.ts:64-65`), and v1.17.14 (commit `0ed10fbd`, `fs-util.ts:65`) skips
  only `NotFound`; `readConfigFile` applies `Effect.orDie` to every other read
  error (`config.ts:186`, the same line in v1.17.14 and v1.17.15).
  `@effect/platform-node-shared` 4.0.0-beta.83 (the version the root
  `package.json` pins) maps only `ENOENT` to `NotFound` and `EACCES` to
  `PermissionDenied`; `EISDIR`, `ENOTDIR` and `ELOOP` become `BadResource`,
  `EBUSY` becomes `Busy`, and every other code, `EPERM` included, becomes
  `Unknown` (`src/internal/utils.ts:13-41`; a later release adds `EPERM`). So a
  folder named `opencode.jsonc`, a symbolic link loop, or a file another program
  holds stops the configuration the same way, and the install notes each, except
  a path through a file instead of a folder (`ENOTDIR`, which OpenCode 1 does
  not skip either, but nothing is installed there). A file OpenCode 1 may not
  read is skipped on Linux and macOS when the error is `EACCES`; Python raises
  `PermissionError` for `EPERM` too, which OpenCode 1 does not skip, so the
  check follows the error number, not the exception class. On Windows, Bun 1.4.4
  (the root `package.json` `packageManager` from v1.19.4) reports a denied read
  as `EPERM`, both from a Win32 error and from an NT status
  (`src/errno/windows_errno.rs:736` and `:833`, tag `bun-v1.4.4`;
  `SHARING_VIOLATION` is `EBUSY`, `:664` and `:845`), and so does Bun 1.3.14,
  which v1.17.15 through v1.19.3 pin (`src/errno/windows_errno.zig:1078`, tag
  `bun-v1.3.14`; `SHARING_VIOLATION` is `EBUSY`, `:1006`), so OpenCode 1
  releases from v1.17.15 on stop for it there, and the install notes it on
  Windows only; no Windows OpenCode binary was run. Re-check this when an
  OpenCode 1 tag pins `@effect/platform-node` 4.0.6 or later:
  `@effect/platform-node-shared` 4.0.6, 4.1.0 and 4.1.2 map `EPERM` to
  `PermissionDenied` (4.1.2 `src/internal/utils.ts:18-21`), so such a release
  skips a denied read on Windows too, and the Windows branch must go. Earlier
  releases throw for any read error but `ENOENT`, permission denied included,
  from v1.0.0 (`config.ts:709-713`) through v1.17.14 (v1.1.4
  `config.ts:1006-1016`, v1.0.100 `config.ts:680-690`), so on those a file they
  may not read stops the configuration on every system and gets no note outside
  Windows. The check covers the three global files OpenCode 1 folds
  (`config.ts:272-274`). The OpenCode install refuses an `opencode.json` it
  cannot parse even as JSON5 with a `config.unparseable` error and stops before
  any note, so that file gets the note only from verify, or when it parses as
  JSON5 and the install leaves it as it is. Text nested deeper than Python's
  parser handles (about 1000 levels on Python 3.10) gets no note, whatever
  OpenCode 1 makes of it. jsonc-parser handles deeper text and fails only past
  its runtime's stack depth (under Node 26.7.0, jsonc-parser 3.3.1 parsed arrays
  nested 8000 deep and threw `RangeError` at 12000, run 2026-11-09), so such a
  file can stop OpenCode 1 without a note. The check reads nothing but a regular
  file or a folder, and no file larger than 16 MiB, so a configuration file that
  is a named pipe or a device, which could block the read, or a very large one,
  gets no note either. A `{file:path}` naming a very large file, or one past
  the first 16 MiB that a file's `{env:NAME}` values and `{file:path}` files
  put in, counted as escaped text, is checked as empty text while it sits
  inside a string value and not within an escape sequence, where text escaped
  as a string's inside cannot change the outcome;
  in a key (a string followed by `:` after spaces and comments, the only
  separators jsonc-parser 3.3.1 skips, `lib/esm/impl/scanner.js:352-357`),
  after an odd backslash, inside a `\u` escape, or outside a string, the file
  gets no note, since that text decides it. OpenCode 1 reads `/dev/null` as
  empty text and goes on (`readFile`), so the check puts in empty text for it
  anywhere. The system refuses to open a socket (`ENXIO` on Linux, run under
  WSL 2026-11-10; macOS was not run), for `readFile` too, so OpenCode 1 stops
  with a `bad file reference`. A named pipe or another device can keep
  `readFile` waiting forever, and OpenCode 1 reads the references in order
  (`variable.ts:48-87`),
  so such a reference leaves the file without a note, and no reference after
  it counts. On Windows a `{file:path}` naming anything but a file or a folder,
  or a path with a part that ends in a dot or a space, is not read: Python
  reads `NUL` in any folder as the device and drops such a dot or space, while
  Node 26.7.0 opens `<folder>\NUL` and `f.txt.` beside `f.txt` as missing files
  (`ENOENT`) and reads a folder named `sub.` by that name (run 2026-11-10), and
  the Bun runtime was not checked. Such a reference is checked as empty text
  inside a string value, like a very large file, since OpenCode 1 then refuses
  a file refused for the rest of its text whether the read succeeds or fails,
  and the note says OpenCode 1 may stop at that reference first; outside a
  string value the file gets no note unless another reference there names a
  file OpenCode 1 cannot read. A file whose references name more than 1,000
  paths gets no note. When the text with its `{env:NAME}` values escaped
  depends on such a reference, the note says OpenCode 1 cannot parse the file
  and nothing of OpenCode 2. Names among the three that lead to one file
  through a symbolic link share one note,
  given to `opencode.json` when it is one of them, else to the name that is not
  a link, else to the first one read; when that is `config.json` and
  `opencode.jsonc` leads to it, the note says OpenCode 2 reads the file as
  `opencode.jsonc`. Names in a loop of links lead to no file and get a note
  each. OpenCode 2: v2.2.6 `Config.parseInfo` logs
  `rejected malformed JSON or JSONC document` and skips the file
  (`packages/core/src/config.ts:136-147`, then `loadFile` returns nothing for
  it, `:168-174`), and `loadDirectory` keeps the other files
  (`config.ts:266-270`), so `opencode.json` still loads when only
  `opencode.jsonc` is broken; `ConfigDiscovery.names` holds no `config.json`
  (`packages/core/src/config/discovery.ts:12`). For the other cases, v2.2.6 puts
  in empty text for a `{file:path}` it cannot read and logs `config file
  reference is missing or unreadable`
  (`packages/core/src/config/variable.ts:63-73`); `ConfigNormalize.normalize`
  rejects a top level that is not an object
  (`packages/core/src/config/normalize.ts:57-64`), after which `parseInfo`
  returns nothing and the file is skipped (`config.ts:148-157`); it drops an
  `instructions` value that is not an array, a string included (`decodeList`
  returns `[]` for it at `normalize.ts:698-701`, and `:229` keeps
  `instructions` only for an array or a non-empty list), and each item that is
  not a string, as a `skipped malformed recognized value`
  (`normalize.ts:228-229`, `:690-706` and `:813-815`); and a document that
  fails the final validation is skipped too, with `rejected canonical configuration after final validation`
  (`config.ts:158-166`). The notes say what OpenCode 2 does in each of those
  cases. They do not describe OpenCode 2 for a folder or a read error: the
  source suggests the config layer dies for a folder (`config.ts:330` and
  `:378`), and a read error was not checked. No OpenCode binary was run
  (<https://github.com/anomalyco/opencode/tree/v1.19.5>,
  <https://github.com/anomalyco/opencode/tree/v2.2.6>).
- Runtime observation, 2026-10-14: opencode-ai 1.19.0 (npm), run against a
  local OpenAI-compatible mock provider that recorded the request. The
  `instructions` entries `~/probe/home-note.md`, an absolute
  `<dir>/*.md` glob and `rel-note.md` loaded `<home>/probe/home-note.md`, both
  files the glob matched, and `<project>/rel-note.md`. So a leading `~/`
  expands to the home directory, an absolute entry matches as a glob on its
  final segment, and a relative entry resolves against the project directory.
  The upstream source moved from `sst/opencode` (now
  <https://github.com/anomalyco/opencode>, under `packages/core/`), and the
  docs page above does not describe these semantics. This is an observation,
  not a retrieved source; re-run it when the CLI version changes.
- <https://opencode.ai/docs/mcp-servers/> (`mcp` block)
- <https://opencode.ai/docs/skills/> (skill locations; retrieved 2026-10-02)
- <https://opencode.ai/docs/agents/> (agents; retrieved 2026-10-02)
- <https://opencode.ai/docs/commands/> (commands; retrieved 2026-10-02)

## OpenCode 2

OpenCode 2 (`anomalyco/opencode` v2.2.0, 2026-10-27, to v2.2.5, 2026-10-30;
npm `@opencode/cli`) reads the same configuration folder as OpenCode 1
(v1.19.5; npm `opencode-ai`, which `opencode.ai/install` still installs). What
each surface the install writes does under each line, read on 2026-11-03 from
the OpenCode 2 docs and the v1.19.5 and v2.2.5 source (the `opencode.jsonc`
row on 2026-11-09, from the v1.19.5, v2.2.5 and v2.2.6 source; v2.2.6 was
published 2026-11-06):

| Surface the install writes | OpenCode 1.19.5 | OpenCode 2.2.5 |
| --- | --- | --- |
| `opencode.json` in `$XDG_CONFIG_HOME/opencode`, else `~/.config/opencode` | read | read; `OPENCODE_CONFIG_DIR` replaces that folder (OpenCode 1 adds it), so the install warns when it names another folder |
| `$schema` and `instructions` (`~/`-anchored or absolute paths) | read | read the same way |
| `instructions` beside an `opencode.jsonc` that holds its own `instructions` list | replaced by that list, an empty list too; install, update and verify print a note | joined with that list (v2.2.5 and v2.2.6) |
| `instructions` in or beside a `config.json`, `opencode.json` or `opencode.jsonc` that is not JSONC once its `{env:...}` and `{file:...}` tokens are put in, holds only whitespace or comments, has a top level that is not an object or an `instructions` that is not a list of strings, has a `{file:...}` naming a file it cannot read, or cannot be read for a reason OpenCode 1 does not skip | not loaded: OpenCode 1 stops with an error and loads none of its configuration; install, update and verify print a note | `config.json` is not read; a file that cannot be parsed or whose top level is not an object is skipped with a warning, so the written list is lost only when that file is `opencode.json`; a file that parses once its `{env:...}` values are escaped is loaded; an unreadable `{file:...}` puts in empty text; an `instructions` value that is not a list is ignored, and items of a list that are not strings are dropped; a folder or a read error was not checked (v2.2.6) |
| `mcp.<name>` (`type`, `command`, `environment`, `url`, `headers`, `enabled`) | read | read in place and converted in memory, `enabled` to `disabled` (`packages/core/src/v1/config/migrate.ts`); the file is never rewritten, but an operator may convert it to the `mcp.servers` shape (migrate-v1 page), and update and uninstall remove a converted entry there only when its `mcp.<name>` is gone and it matches what the install wrote as a whole. OpenCode 1.19.5 also lowers `mcp.servers.<name>` to a flat entry; on a name clash the flat entry wins in OpenCode 1 and the `mcp.servers` one in OpenCode 2 |
| `${NAME}` in an MCP value | not expanded | not expanded; the install writes `{env:NAME}` in environment, headers and URL values, which both lines substitute. Both insert the value into the config text unescaped (OpenCode 2 escapes it only when that text would not parse otherwise), so a backslash, double quote or control character can stop OpenCode 1 from reading the file, and a `\t` or `\n` reaches the server as a control character in both lines; the install warns about such a value |
| helper `permission` map | read | translated in memory (`bash` becomes `shell`); the install writes only `deny` rules, so the default ask before reading `.env` and `.env.*` files and the operator's stricter rules apply |
| commands, skills and `$ARGUMENTS` | read | read; a skill with `disable-model-invocation: true` is hidden from the model |
| `~/.claude/CLAUDE.md` (the Claude Code install) | read when no global `AGENTS.md` exists | not read |

Decision, 2026-11-03 (the operator's choice): the install writes the OpenCode
1 shapes for both lines. OpenCode 1 reads them natively, and OpenCode 2
translates them in memory. Apothem moves to version-aware output, writing
OpenCode 2's own shapes where OpenCode 2 runs, when either of two signals
appears: OpenCode 2 announces a removal date for its translation of the
OpenCode 1 shapes, or `opencode.ai/install` or the `opencode-ai` npm package
moves to OpenCode 2.

Re-check by 2027-02-01, when this snapshot passes the 90-day limit, for those
two signals: a removal date for the translation of the helper `permission`
map and the bare `mcp.<name>` entries (OpenCode 2's live schema already marks
them deprecated), and the default installer or `opencode-ai` serving
OpenCode 2.

- <https://opencode.ai/v2/docs/migrate-v1/> (shared configuration locations; V1 shapes keep working; retrieved 2026-11-03)
- <https://github.com/anomalyco/opencode/tree/v2.2.5> (the instruction, agent, command and skill loaders, `packages/core/src/v1/config/migrate.ts`, `packages/core/src/config/variable.ts`, `packages/schema/src/agent.ts`; read 2026-11-03)
- <https://github.com/anomalyco/opencode/tree/v1.19.5> (`packages/opencode/src/agent/agent.ts`, `packages/opencode/src/permission/index.ts`, `packages/core/src/global.ts`, `packages/opencode/src/config/variable.ts`, `packages/opencode/src/config/parse.ts`, `packages/opencode/src/config/v2-compat.ts`; read 2026-11-03)

## Discovery Targets

- None. No capability cell for this harness is discovery-pending.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. OpenCode adapter output preserves that suffix when prompt text is materialized.
- Boundary: this pin does not claim a harness-native recommended-option widget. It only pins the text-rendered convention used by `rules/interactive-questions.md`.

## Long Context and Compaction

- Status: profile-managed.
- Mechanism: Apothem keeps full-suite `/plan-execute` runs continuous by externalizing state to `.apothem/plans/`, compacting or restarting the harness session at phase boundaries as needed, and restoring via the Blind Bootstrap sequence.
- Boundary: this pin does not claim vendor-native autocompaction or a long-context size. It pins the adapter-local state handoff and compaction-restoration convention used by `rules/context-management.md`.

## Large-Codebase Practice Projection

- Layered context: declared in `capabilities.yml` under `layered_context_surface`; no vendor-native hierarchy is claimed beyond the adapter's documented file/template surface.
- LSP symbol navigation: `tracked-gap` until a vendor-ratified plugin or tool surface is pinned.
- Hook learning capture: routed through the `persistent-conventions-vigilance` artifact-evolution cycle; pass-class hooks stay silent and recurring findings become rule, skill, hook, or documentation updates.

## Plugin-alone Persistence

OpenCode documents a vendor-native `plugin` key plus a `plugins/` directory, but
that surface is operator-owned and **Apothem ships no OpenCode plugin bundle** —
and OpenCode exposes no harness-native plugin marketplace Apothem distributes
through. The cohort lands via native skills/commands/agents surfaces, all written
by the engine. There is no standalone-installable bundle; every artifact requires
the full `apothem install --harness opencode` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Skills | No — requires `apothem install` | Native `~/.config/opencode/skills/*/SKILL.md` is engine-written; no pre-built bundle carries it. |
| Commands | No — requires `apothem install` | Apothem commands are engine-converted to OpenCode Markdown under `~/.config/opencode/commands/`. |
| Agents | No — requires `apothem install` | Apothem agents are engine-converted to OpenCode Markdown under `~/.config/opencode/agents/`. |
| Rules (as native primitive) | No — platform limit | OpenCode has no native rules-directory primitive; Apothem rules land as `~/.config/opencode/.apothem/support/rules/` reference material via the engine, and `opencode.json` `instructions` names the projected profile document and the `alwaysApply: true` rules by explicit path (OpenCode loads every listed file in every session): the four core rules and the rule index. OpenCode scopes no rule by path, so every other rule is read on demand through the index. |
| Hooks | No — platform limit | Engine support material only under `~/.config/opencode/.apothem/support/hooks/`. |
| MCP | No — requires `apothem install` | The adapter's materializer projects the profile's MCP inventory into the `opencode.json` `mcp` block; nothing persists before the engine run. |
| Plugins / Settings | No — operator-owned | The `plugin` key in `opencode.json` is operator-owned; the adapter authors no plugin entries. |

Platform limit: OpenCode's `plugin` surface is operator-owned and Apothem
distributes no OpenCode plugin package, so a plugin-alone story does not exist —
the engine install is the sole persistence path.
