// SPDX-License-Identifier: MIT

// Inject generated artifact inventories into the Fumadocs docs pages.
//
// The script is intentionally non-destructive: page authors control all prose
// outside the marker block, while this build step refreshes only the content
// between the generated-reference markers. Two outputs are owned whole: the
// generated command pages under pipeline/ (marked with GENERATED_PAGE) and the
// `pages` order of every pipeline/meta.json.
//
// The target pages are Fumadocs MDX (`.mdx`) under `site/content/docs/`. Two
// adaptations follow from MDX (versus the prior Markdown stack):
//
//   1. Markers use the MDX-comment form `{/* … */}` rather than the HTML
//      comment form `<!-- … -->`. HTML comments are invalid in MDX, so the
//      ported pages carry the MDX-comment markers and this generator matches
//      them byte-for-byte.
//   2. Generated cell content is MDX-escaped. MDX parses a bare `<` as the
//      start of a JSX element and a bare `{` as the start of a JSX expression,
//      so any `<`, `>`, `{`, or `}` that appears in cell text OUTSIDE an inline
//      code span is escaped to its HTML entity. Content inside backtick code
//      spans is literal in MDX and is left untouched. The `<br />` row
//      separator the generator emits itself is a deliberate self-closed JSX
//      void element and is preserved verbatim.

import { spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const SITE_ROOT = join(SCRIPT_DIR, '..');
const REPO_ROOT = join(SITE_ROOT, '..');
const DOCS_ROOT = join(SITE_ROOT, 'content', 'docs');
// Normalize to lower case so the generated blob URLs are byte-identical
// regardless of environment: CI injects GITHUB_REPOSITORY with the canonical
// login casing (Ahmed-G-Gad/apothem) while the local fallback is lower case.
// GitHub owner/repo slugs are case-insensitive, so lowering keeps every link
// resolvable while making the drift gate deterministic across local and CI.
const GITHUB_REPOSITORY = (process.env.APOTHEM_GITHUB_REPOSITORY ||
	process.env.GITHUB_REPOSITORY ||
	'ahmed-g-gad/apothem').toLowerCase();

const START = '{/* apothem:generated-reference:start */}';
const END = '{/* apothem:generated-reference:end */}';

const CHANGELOG_START = '{/* apothem:changelog:start */}';
const CHANGELOG_END = '{/* apothem:changelog:end */}';

const SOURCES = [
	{
		kind: 'rules',
		title: 'Generated Rule Inventory',
		sourceDir: join(REPO_ROOT, 'src', 'apothem', 'rules'),
		recursive: false,
		target: join(DOCS_ROOT, 'reference', 'rules.mdx'),
	},
	{
		kind: 'commands',
		title: 'Generated Command Inventory',
		sourceDir: join(REPO_ROOT, 'src', 'apothem', 'commands'),
		recursive: false,
		target: join(DOCS_ROOT, 'reference', 'commands.mdx'),
	},
	{
		kind: 'skills',
		title: 'Generated Skill Inventory',
		sourceDir: join(REPO_ROOT, 'src', 'apothem', 'skills'),
		recursive: true,
		target: join(DOCS_ROOT, 'reference', 'skills.mdx'),
		match: (path) => path.endsWith(`${sep}SKILL.md`),
	},
	{
		kind: 'agents',
		title: 'Generated Agent Inventory',
		sourceDir: join(REPO_ROOT, 'src', 'apothem', 'agents'),
		recursive: false,
		target: join(DOCS_ROOT, 'reference', 'agents.mdx'),
	},
	{
		kind: 'hooks',
		title: 'Generated Hook Message Inventory',
		sourceDir: join(REPO_ROOT, 'src', 'apothem', 'hooks', 'messages'),
		recursive: false,
		target: join(DOCS_ROOT, 'reference', 'hooks.mdx'),
	},
];

function walk(dir, recursive) {
	const out = [];
	if (!existsDir(dir)) return out;
	for (const entry of readdirSync(dir, { withFileTypes: true })) {
		const full = join(dir, entry.name);
		if (entry.isDirectory() && recursive) {
			out.push(...walk(full, recursive));
		} else if (entry.isFile() && entry.name.endsWith('.md')) {
			out.push(full);
		}
	}
	return out.sort();
}

function existsDir(path) {
	try {
		return statSync(path).isDirectory();
	} catch {
		return false;
	}
}

function parseFrontmatter(raw) {
	const text = raw.replace(/^\s*<!--[\s\S]*?-->\s*/, '');
	const match = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
	const frontmatter = {};
	let body = text;
	if (match) {
		for (const line of match[1].split(/\r?\n/)) {
			const kv = line.match(/^(\w[\w-]*):\s*(.*)$/);
			if (!kv) continue;
			frontmatter[kv[1]] = unquote(kv[2].trim());
		}
		body = text.slice(match[0].length);
	}
	return { frontmatter, body };
}

function unquote(value) {
	if (
		(value.startsWith('"') && value.endsWith('"')) ||
		(value.startsWith("'") && value.endsWith("'"))
	) {
		return value.slice(1, -1);
	}
	return value;
}

function excerpt(body) {
	const lines = [];
	for (const line of body.split(/\r?\n/)) {
		const trimmed = line.trim();
		if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith('```')) {
			if (lines.length > 0) break;
			continue;
		}
		lines.push(trimmed);
	}
	return lines.join(' ').slice(0, 180);
}

function displayName(path, frontmatter) {
	return frontmatter.name || frontmatter.title || basename(path);
}

function basename(path) {
	const file = path.split(/[\\/]/).pop();
	return file.replace(/\.md$/i, '');
}

// MDX-escape cell text. MDX parses a bare `<` as the start of a JSX element
// and a bare `{` as the start of a JSX expression; both break the build. Any
// such character that lands OUTSIDE an inline code span (a backtick-delimited
// run) is escaped to its HTML entity. Backtick spans are literal in MDX and
// are emitted untouched, so a path like `<project>/foo` inside backticks
// renders verbatim. The escape runs after pipe-escaping and whitespace
// normalization so the `\|` introduced by escapePipe is never misread.
function escapeMdx(value) {
	const text = String(value);
	let out = '';
	let inCode = false;
	for (let i = 0; i < text.length; i += 1) {
		const ch = text[i];
		if (ch === '`') {
			inCode = !inCode;
			out += ch;
			continue;
		}
		if (inCode) {
			out += ch;
			continue;
		}
		switch (ch) {
			case '<':
				out += '&lt;';
				break;
			case '>':
				out += '&gt;';
				break;
			case '{':
				out += '&#123;';
				break;
			case '}':
				out += '&#125;';
				break;
			default:
				out += ch;
		}
	}
	return out;
}

function generateBlock(config) {
	const files = walk(config.sourceDir, config.recursive).filter((path) =>
		config.match ? config.match(path) : true,
	);
	const rows = files.map((path) => {
		const { frontmatter, body } = parseFrontmatter(readFileSync(path, 'utf8'));
		const rel = relative(REPO_ROOT, path).split(sep).join('/');
		const description = frontmatter.description || excerpt(body) || 'No description.';
		return `| \`${escapePipe(displayName(path, frontmatter))}\` | ${escapeMdx(escapePipe(description))} | [\`${rel}\`](https://github.com/${GITHUB_REPOSITORY}/blob/main/${rel}) |`;
	});
	return [
		`## ${config.title}`,
		'',
		START,
		'',
		'| Name | Description | Source |',
		'| --- | --- | --- |',
		...rows,
		'',
		END,
		'',
	].join('\n');
}

function escapePipe(value) {
	return String(value).replace(/\|/g, '\\|').replace(/\s+/g, ' ').trim();
}

// -----------------------------------------------------------------------
// Source-generated reference blocks (CLI, harness adapters, profile fields).
//
// These three pages are populated from Apothem's own source of truth rather
// than from a directory walk: the CLI command tree and the harness registry
// are introspected by a deterministic Python emitter, and the profile fields
// come straight from the JSON Schema. Every collection is sorted so repeated
// runs against an unchanged tree are byte-identical.
// -----------------------------------------------------------------------

const PROFILE_SCHEMA = join(
	REPO_ROOT,
	'src',
	'apothem',
	'schemas',
	'profile.schema.json',
);

const EMITTER_CACHE = new Map();

function runEmitter(kind) {
	if (!EMITTER_CACHE.has(kind)) EMITTER_CACHE.set(kind, spawnEmitter(kind));
	return EMITTER_CACHE.get(kind);
}

function spawnEmitter(kind) {
	const args = ['-m', 'apothem.cli.reference_export', kind];
	const options = {
		cwd: REPO_ROOT,
		encoding: 'utf8',
		env: { ...process.env, PYTHONPATH: join(REPO_ROOT, 'src') },
	};
	let result = spawnSync('python', args, options);
	if (result.error && result.error.code === 'ENOENT') {
		result = spawnSync('python3', args, options);
	}
	if (result.error) {
		if (result.error.code === 'ENOENT') {
			throw new Error(
				`update-reference-inventory: no Python interpreter found on PATH for '${kind}' ` +
					`(tried 'python' then 'python3'). Install Python 3.10+ and ensure 'python' or ` +
					`'python3' is on PATH; the reference pages are source-generated from the Python ` +
					`engine at prebuild. Underlying error: ${result.error.message}`,
			);
		}
		throw new Error(
			`update-reference-inventory: failed to spawn python for '${kind}': ${result.error.message}`,
		);
	}
	if (result.status !== 0) {
		throw new Error(
			`update-reference-inventory: python emitter for '${kind}' failed — exited ${result.status} ` +
				`(the interpreter was found and ran, but the emitter itself errored): ${result.stderr || ''}`,
		);
	}
	return JSON.parse(result.stdout);
}

function tableBlock(title, header, rows) {
	return [
		`## ${title}`,
		'',
		START,
		'',
		header,
		`| ${header.split('|').slice(1, -1).map(() => '---').join(' | ')} |`,
		...rows,
		'',
		END,
		'',
	].join('\n');
}

function generateCliBlock() {
	const payload = runEmitter('cli');
	const rows = payload.commands.map((command) => {
		const flags = command.flags.map((flag) => `\`${flag}\``).join(', ') || '—';
		return `| \`apothem ${escapePipe(command.name)}\` | ${flags} | ${escapeMdx(escapePipe(command.description))} |`;
	});
	return tableBlock(
		'Generated Command and Flag Reference',
		'| Command | Flags | Description |',
		rows,
	);
}

function generateHarnessBlock() {
	const payload = runEmitter('harnesses');
	const rows = payload.harnesses.map((harness) => {
		const targets = harness.target_paths
			.map((path) => `\`${escapePipe(path)}\``)
			.join('<br />');
		return `| ${escapeMdx(escapePipe(harness.display_name))} (\`${escapePipe(harness.id)}\`) | ${escapeMdx(escapePipe(harness.scope))} | ${escapeMdx(escapePipe(harness.output_format))} | ${targets} |`;
	});
	return tableBlock(
		'Generated Harness Adapter Reference',
		'| Harness | Scope | Format | Target paths |',
		rows,
	);
}

function flattenProfileFields(properties, defs, required, prefix) {
	const fields = [];
	for (const [name, rawSchema] of Object.entries(properties || {})) {
		let schema = rawSchema;
		if (schema.$ref) {
			const refName = schema.$ref.replace('#/$defs/', '');
			schema = defs[refName] || {};
		}
		const path = prefix ? `${prefix}.${name}` : name;
		const isRequired = (required || []).includes(name);
		fields.push({
			field: path,
			type: schema.type || (schema.enum ? 'enum' : 'object'),
			required: isRequired ? 'yes' : 'no',
			description: schema.description || '',
		});
		if (schema.type === 'object' && schema.properties) {
			fields.push(
				...flattenProfileFields(
					schema.properties,
					defs,
					schema.required,
					path,
				),
			);
		}
	}
	return fields;
}

function generateProfileBlock() {
	const schema = JSON.parse(readFileSync(PROFILE_SCHEMA, 'utf8'));
	const fields = flattenProfileFields(
		schema.properties,
		schema.$defs || {},
		schema.required,
		'',
	);
	fields.sort((a, b) => a.field.localeCompare(b.field));
	const rows = fields.map(
		(field) =>
			`| \`${escapePipe(field.field)}\` | ${escapeMdx(escapePipe(field.type))} | ${field.required} | ${escapeMdx(escapePipe(field.description)) || '—'} |`,
	);
	return tableBlock(
		'Generated Profile Field Reference',
		'| Field | Type | Required | Description |',
		rows,
	);
}

// The architecture page's list of top-level CLI commands. The emitter returns
// leaf commands (`profile init`, `harnesses list`), so the first word of each
// name is the top-level command. A command with a CLI reference page links to
// it; one without is listed unlinked, so a new command never emits a dead link.
function generateCliCommandListBlock() {
	const payload = runEmitter('cli');
	const topLevel = [...new Set(payload.commands.map((command) => command.name.split(' ')[0]))].sort();
	const items = topLevel.map((name) => {
		const label = `\`apothem ${name}\``;
		const page = join(DOCS_ROOT, 'cli-reference', `${name}.mdx`);
		return existsFile(page) ? `- [${label}](/docs/cli-reference/${name})` : `- ${label}`;
	});
	return [
		START,
		'',
		`The \`cli/\` package registers ${topLevel.length} top-level commands:`,
		'',
		...items,
		'',
		END,
	].join('\n');
}

// The conformity-gate page's validator table, one row per module that declares
// a GREP_NAME. `mode` says how the gate runs the validator (see
// apothem.cli.reference_export.export_conformity).
function generateConformityBlock() {
	const payload = runEmitter('conformity');
	const counts = { 'per-write': 0, standalone: 0, 'change-set': 0 };
	const rows = payload.validators.map((validator) => {
		counts[validator.mode] = (counts[validator.mode] || 0) + 1;
		const anchor = validator.rule_anchor ? escapeMdx(escapePipe(validator.rule_anchor)) : '—';
		return `| \`${escapePipe(validator.name)}\` | ${validator.mode} | ${anchor} | ${escapeMdx(escapePipe(validator.summary))} |`;
	});
	return [
		START,
		'',
		`The gate registers ${payload.validators.length} validators: ${counts['per-write']} per-write, ` +
			`${counts.standalone} standalone and ${counts['change-set']} change-set.`,
		'',
		'| Validator | Runs | Rule anchor | What it checks |',
		'| --- | --- | --- | --- |',
		...rows,
		'',
		END,
	].join('\n');
}

// The MCP page's per-adapter table, from each registry entry's `mcp_servers`
// capability cell: `native` means the adapter writes the profile's MCP
// inventory into the tool's own config; every other status means it authors
// no server entries, with the registry's recorded reason.
function generateMcpBlock() {
	const payload = runEmitter('harnesses');
	const rows = payload.harnesses.map((harness) => {
		const status = harness.capabilities.mcp_servers;
		const cell =
			status === 'native'
				? "Projected: written into the tool's MCP config"
				: `Not projected (${status})`;
		const note = harness.capability_notes.mcp_servers;
		return `| ${escapeMdx(escapePipe(harness.display_name))} (\`${escapePipe(harness.id)}\`) | ${escapeMdx(cell)} | ${note ? escapeMdx(escapePipe(note)) : '—'} |`;
	});
	return [
		START,
		'',
		'| Harness | MCP inventory | Note |',
		'| --- | --- | --- |',
		...rows,
		'',
		END,
	].join('\n');
}

function existsFile(path) {
	try {
		return statSync(path).isFile();
	} catch {
		return false;
	}
}

const GENERATED_SOURCES = [
	{
		generate: generateCliBlock,
		target: join(DOCS_ROOT, 'reference', 'cli.mdx'),
	},
	{
		generate: generateHarnessBlock,
		target: join(DOCS_ROOT, 'reference', 'harness-registry.mdx'),
	},
	{
		generate: generateProfileBlock,
		target: join(DOCS_ROOT, 'reference', 'profile-fields.mdx'),
	},
	{
		generate: generateCliCommandListBlock,
		target: join(DOCS_ROOT, 'architecture', 'source-layout.mdx'),
	},
	{
		generate: generateConformityBlock,
		target: join(DOCS_ROOT, 'conformity-gate', 'index.mdx'),
	},
	{
		generate: generateMcpBlock,
		target: join(DOCS_ROOT, 'reference', 'mcp.mdx'),
	},
];

function inject(target, block) {
	const existing = readFileSync(target, 'utf8');
	const startIndex = existing.indexOf(START);
	const endIndex = existing.indexOf(END);
	// Fail loudly on missing or malformed markers rather than appending a second
	// generated-reference block. A caller that intends to bootstrap a fresh page
	// writes a marker-ready shell first (see ensureProfileFieldsPage); a target
	// that reaches inject() without a well-formed marker pair is a real defect —
	// a hand-broken page or a splice that lost its markers — and appending would
	// silently duplicate the table. This mirrors injectChangelog's contract.
	if (startIndex === -1 || endIndex === -1 || endIndex <= startIndex) {
		throw new Error(
			`update-reference-inventory: generated-reference markers missing or ` +
				`malformed in ${target}`,
		);
	}
	const markerBlock = block.slice(block.indexOf(START), block.indexOf(END) + END.length);
	const suffix = existing.slice(endIndex + END.length);
	const normalizedSuffix = suffix.trim() ? `\n\n${suffix.trimStart()}` : '\n';
	const next =
		existing.slice(0, startIndex).replace(/\s+$/, '\n\n') +
		markerBlock +
		normalizedSuffix;
	if (next !== existing) {
		writeFileSync(target, next, 'utf8');
		return true;
	}
	return false;
}

// -----------------------------------------------------------------------
// Locale fanout.
//
// Translated pages under <locale>/ carry the same generated-region markers
// as their English sources. The injected tables are source-generated (names,
// paths, schema fields), so every locale receives the identical block while
// the marker splice preserves the surrounding translated prose. A locale
// copy without the markers — or an untranslated locale — is left untouched,
// so fanout can never corrupt an operator-authored page.
// -----------------------------------------------------------------------

const LOCALE_DIRS = readdirSync(DOCS_ROOT, { withFileTypes: true })
	.filter((entry) => entry.isDirectory() && /^[a-z]{2}(-[a-z]{2})?$/i.test(entry.name))
	.map((entry) => entry.name)
	.sort();

function injectAcrossLocales(target, block) {
	let count = inject(target, block) ? 1 : 0;
	const rel = relative(DOCS_ROOT, target);
	for (const locale of LOCALE_DIRS) {
		const localeTarget = join(DOCS_ROOT, locale, rel);
		let existing;
		try {
			existing = readFileSync(localeTarget, 'utf8');
		} catch {
			continue;
		}
		if (!existing.includes(START)) continue;
		if (inject(localeTarget, block)) count += 1;
	}
	return count;
}

// -----------------------------------------------------------------------
// Root CHANGELOG injection.
//
// The /changelog/ page is a thin shell: page authors own the frontmatter and
// the intro prose, while this build step injects the root CHANGELOG.md body
// between the changelog markers. The root file stays the single source of
// truth; a re-run against an unchanged tree is byte-identical, so the same
// drift gate that covers the reference pages covers the changelog.
// -----------------------------------------------------------------------

const CHANGELOG_SOURCE = join(REPO_ROOT, 'CHANGELOG.md');
const CHANGELOG_TARGET = join(DOCS_ROOT, 'changelog.mdx');

function changelogBody() {
	const raw = readFileSync(CHANGELOG_SOURCE, 'utf8');
	// Drop the leading license-header comment so the page prose never carries
	// a bare license token (the REUSE lint treats a literal tag in body text
	// as a stray license declaration).
	return raw.replace(/^\s*<!--[\s\S]*?-->\s*/, '').trim();
}

function injectChangelog(target) {
	const existing = readFileSync(target, 'utf8');
	const startIndex = existing.indexOf(CHANGELOG_START);
	const endIndex = existing.indexOf(CHANGELOG_END);
	if (startIndex === -1 || endIndex === -1 || endIndex < startIndex) {
		throw new Error(
			`update-reference-inventory: changelog markers missing or malformed in ${target}`,
		);
	}
	const body = changelogBody();
	const block = `${CHANGELOG_START}\n\n${body}\n\n${CHANGELOG_END}`;
	const next =
		existing.slice(0, startIndex) +
		block +
		existing.slice(endIndex + CHANGELOG_END.length);
	if (next !== existing) {
		writeFileSync(target, next, 'utf8');
		return true;
	}
	return false;
}

// -----------------------------------------------------------------------
// Root ROADMAP injection.
//
// ROADMAP.md is the single roadmap; the /community/roadmap/ page is a shell
// whose body is copied from it between the roadmap markers, exactly as the
// changelog page mirrors CHANGELOG.md. Two hand-written roadmaps had drifted
// apart. Only the English page is mirrored; locale pages keep their
// translations.
// -----------------------------------------------------------------------

const ROADMAP_START = '{/* apothem:roadmap:start */}';
const ROADMAP_END = '{/* apothem:roadmap:end */}';
const ROADMAP_SOURCE = join(REPO_ROOT, 'ROADMAP.md');
const ROADMAP_TARGET = join(DOCS_ROOT, 'community', 'roadmap.mdx');

function roadmapBody() {
	const raw = readFileSync(ROADMAP_SOURCE, 'utf8');
	// Drop the license-header comment (as for the changelog) and the H1: the
	// page title comes from the MDX frontmatter.
	return raw
		.replace(/^\s*<!--[\s\S]*?-->\s*/, '')
		.replace(/^# [^\n]*\n/, '')
		.trim();
}

function injectRoadmap(target) {
	const existing = readFileSync(target, 'utf8');
	const startIndex = existing.indexOf(ROADMAP_START);
	const endIndex = existing.indexOf(ROADMAP_END);
	if (startIndex === -1 || endIndex === -1 || endIndex < startIndex) {
		throw new Error(
			`update-reference-inventory: roadmap markers missing or malformed in ${target}`,
		);
	}
	const block = `${ROADMAP_START}\n\n${roadmapBody()}\n\n${ROADMAP_END}`;
	const next =
		existing.slice(0, startIndex) + block + existing.slice(endIndex + ROADMAP_END.length);
	if (next !== existing) {
		writeFileSync(target, next, 'utf8');
		return true;
	}
	return false;
}

// The bootstrap page carries an empty generated-reference marker pair so the
// first generation splices the table in through the normal marker path — the
// same path every subsequent run and every other reference page uses. Without
// the markers, inject() would have to append the first block, which is the
// exact silent-duplicate hole this file closes; a marker-ready shell keeps
// inject()'s missing-marker case a hard error.
const PROFILE_FIELDS_PAGE = [
	'---',
	'title: "Profile fields"',
	'description: "Source-generated reference for every field in the Apothem shared profile schema."',
	'---',
	'{/* SPDX-License-Identifier: MIT */}',
	'',
	'Every field below is generated from the canonical profile JSON Schema at',
	'`src/apothem/schemas/profile.schema.json`. The table is the source of truth',
	'for what a shared profile may declare; edit the schema, then regenerate.',
	'',
	START,
	'',
	END,
	'',
].join('\n');

function ensureProfileFieldsPage(target) {
	try {
		readFileSync(target, 'utf8');
	} catch {
		writeFileSync(target, PROFILE_FIELDS_PAGE, 'utf8');
	}
}

// -----------------------------------------------------------------------
// Slash-command pages and the command-pipeline nav.
//
// Every shipped command definition under src/apothem/commands/ has a page at
// pipeline/<name>.mdx. A command with no hand-written page gets a generated
// page: this script owns the whole file (it carries GENERATED_PAGE) and
// rewrites it from the definition on every run, and deletes it when the
// command is removed. A hand-written page (no GENERATED_PAGE marker) is never
// touched. The sidebar order in pipeline/meta.json is generated as well, in
// English and in every locale, so a new command cannot ship without a page or
// a nav entry. Locale meta files keep their translated title.
// -----------------------------------------------------------------------

const COMMANDS_DIR = join(REPO_ROOT, 'src', 'apothem', 'commands');
const SKILLS_DIR = join(REPO_ROOT, 'src', 'apothem', 'skills');
const PIPELINE_DIR = join(DOCS_ROOT, 'pipeline');
const GENERATED_PAGE_PREFIX = '{/* apothem:generated-page';
const GENERATED_PAGE =
	`${GENERATED_PAGE_PREFIX} — generated from src/apothem/commands; edit the ` +
	'command definition and rerun site/scripts/update-reference-inventory.mjs */}';

function commandDefinitions() {
	return walk(COMMANDS_DIR, false)
		.filter((path) => basename(path) !== 'README')
		.map((path) => {
			const { frontmatter, body } = parseFrontmatter(readFileSync(path, 'utf8'));
			return { name: frontmatter.name || basename(path), path, frontmatter, body };
		});
}

// The paragraph that opens with a bold label, e.g. "**Pipeline position.** …".
function labelledParagraph(body, label) {
	const lines = body.split(/\r?\n/);
	const lead = `**${label}.**`;
	const start = lines.findIndex((line) => line.trim().startsWith(lead));
	if (start === -1) return '';
	const out = [lines[start].trim().slice(lead.length).trim()];
	for (const line of lines.slice(start + 1)) {
		if (!line.trim()) break;
		out.push(line.trim());
	}
	return out.join(' ');
}

// The lines of a `## <heading>` section, up to the next heading or rule.
function sectionLines(body, heading) {
	const lines = body.split(/\r?\n/);
	const start = lines.findIndex((line) => line.trim() === `## ${heading}`);
	if (start === -1) return [];
	const out = [];
	for (const line of lines.slice(start + 1)) {
		if (/^#{1,2}\s/.test(line) || /^---\s*$/.test(line)) break;
		out.push(line);
	}
	return out;
}

function firstParagraph(lines) {
	const out = [];
	for (const line of lines) {
		if (!line.trim()) {
			if (out.length > 0) break;
			continue;
		}
		out.push(line.trim());
	}
	return out.join(' ');
}

// Command definitions cite repository paths with relative links that do not
// resolve on the site; keep the link text and drop a non-absolute target.
function plainLinks(text) {
	return text.replace(/\[([^\]]+)\]\((?!https?:\/\/)[^)]*\)/g, '$1');
}

function prose(text) {
	return escapeMdx(plainLinks(text));
}

function yamlString(value) {
	return JSON.stringify(value);
}

function commandPage(command) {
	const { name, frontmatter, body } = command;
	const rel = relative(REPO_ROOT, command.path).split(sep).join('/');
	const hint = frontmatter['argument-hint'] || '';
	const description = frontmatter.description || excerpt(body);
	const position = labelledParagraph(body, 'Pipeline position');
	const consumed = labelledParagraph(body, 'Consumed');
	const emitted = labelledParagraph(body, 'Emitted');
	const table = sectionLines(body, 'Inputs')
		.map((line) => line.trim())
		.filter((line) => line.startsWith('|'));
	const next = firstParagraph(sectionLines(body, 'Recommended Next Step'));
	const parts = [
		'---',
		`title: ${yamlString(`/${name}`)}`,
		`description: ${yamlString(`Reference for the /${name} command: invocation, arguments, inputs and outputs.`)}`,
		'---',
		'{/* SPDX-License-Identifier: MIT */}',
		GENERATED_PAGE,
		'',
		START,
		'',
		prose(description),
		'',
		'## Invocation',
		'',
		'```text',
		`/${name}${hint ? ` ${hint}` : ''}`,
		'```',
	];
	if (frontmatter['disable-model-invocation'] === 'true') {
		parts.push(
			'',
			'The definition sets `disable-model-invocation: true`, so a harness that honors that key ' +
				'starts this command only when you type it.',
		);
	}
	if (position) parts.push('', '## Pipeline position', '', prose(position));
	if (consumed || table.length > 0) {
		parts.push('', '## Inputs');
		if (consumed) parts.push('', prose(consumed));
		if (table.length > 0) parts.push('', ...table.map((row) => prose(row)));
	}
	if (emitted) parts.push('', '## Outputs', '', prose(emitted));
	if (next) parts.push('', '## Next step', '', prose(next));
	parts.push('', '## Source', '', sourceNote(name, rel), '', END, '');
	return parts.join('\n');
}

// A skill that shares the command's name takes the name wherever an install
// puts commands and skills in one namespace: Claude Code resolves the pair to
// the skill, and the engine installs that turn commands into skills keep it.
function sourceNote(name, rel) {
	const link = (path) =>
		`[\`${path}\`](https://github.com/${GITHUB_REPOSITORY}/blob/main/${path})`;
	const skill = join(SKILLS_DIR, name, 'SKILL.md');
	if (!existsFile(skill)) {
		return `Generated from ${link(rel)}, the command definition every harness installs.`;
	}
	const skillRel = relative(REPO_ROOT, skill).split(sep).join('/');
	return (
		`Generated from ${link(rel)}. The skill ${link(skillRel)} has the same name. ` +
		'Where an install puts commands and skills under one name (the Claude Code ' +
		'plugin, and the engine installs that turn commands into skills), the skill ' +
		'runs; installs that keep commands and skills apart ship both.'
	);
}

function writeCommandPages(commands) {
	let count = 0;
	const names = new Set(commands.map((command) => command.name));
	for (const command of commands) {
		const target = join(PIPELINE_DIR, `${command.name}.mdx`);
		const existing = existsFile(target) ? readFileSync(target, 'utf8') : null;
		if (existing !== null && !existing.includes(GENERATED_PAGE_PREFIX)) continue;
		const next = commandPage(command);
		if (next !== existing) {
			writeFileSync(target, next, 'utf8');
			count += 1;
		}
	}
	// A generated page whose command was removed would otherwise linger as an
	// orphan; hand-written pages are left for their authors.
	for (const entry of readdirSync(PIPELINE_DIR)) {
		if (!entry.endsWith('.mdx')) continue;
		const path = join(PIPELINE_DIR, entry);
		if (names.has(entry.replace(/\.mdx$/, ''))) continue;
		if (readFileSync(path, 'utf8').includes(GENERATED_PAGE_PREFIX)) {
			rmSync(path);
			count += 1;
		}
	}
	return count;
}

// Sidebar order: each orchestrator, then its stages in the order its
// `--from` argument declares, then that family's remaining commands; the audit
// orchestrator and the -audit / -review dimensions; /fortress; then every
// other command alphabetically. Every command appears exactly once.
function pipelineNavPages(commands) {
	const byName = new Map(commands.map((command) => [command.name, command]));
	const sorted = [...byName.keys()].sort();
	const ordered = [];
	const take = (name) => {
		if (byName.has(name) && !ordered.includes(name)) ordered.push(name);
	};
	const stagesOf = (orchestrator) => {
		const hint = byName.get(orchestrator)?.frontmatter['argument-hint'] || '';
		const match = hint.match(/--from\s+([a-z|-]+)/);
		return match ? match[1].split('|') : [];
	};
	for (const family of ['plan', 'research']) {
		take(family);
		for (const stage of stagesOf(family)) take(`${family}-${stage}`);
		for (const name of sorted) if (name.startsWith(`${family}-`)) take(name);
	}
	take('audit');
	for (const name of sorted) if (/-(audit|review)$/.test(name)) take(name);
	take('fortress');
	for (const name of sorted) take(name);
	return ['index', ...ordered, '...'];
}

// The first sentence of a description, cut on a word boundary when long.
function firstSentence(text, limit = 160) {
	const sentence = text.split(/(?<=[.!?])\s+(?=[A-Z/`])/)[0].trim();
	if (sentence.length <= limit) return sentence;
	const cut = sentence.slice(0, limit);
	return `${cut.slice(0, cut.lastIndexOf(' '))} …`;
}

// The pipeline overview's index of every command, in nav order.
function commandIndexBlock(commands, pages) {
	const byName = new Map(commands.map((command) => [command.name, command]));
	const rows = pages
		.filter((page) => byName.has(page))
		.map((name) => {
			const { frontmatter, body } = byName.get(name);
			const summary = firstSentence(frontmatter.description || excerpt(body));
			return `| [/${name}](/docs/pipeline/${name}) | ${prose(escapePipe(summary))} |`;
		});
	return [START, '', '| Command | Summary |', '| --- | --- |', ...rows, '', END].join('\n');
}

function writePipelineNav(pages) {
	let count = 0;
	const targets = [
		join(PIPELINE_DIR, 'meta.json'),
		...LOCALE_DIRS.map((locale) => join(DOCS_ROOT, locale, 'pipeline', 'meta.json')),
	];
	for (const target of targets) {
		if (!existsFile(target)) continue;
		const existing = readFileSync(target, 'utf8');
		const meta = JSON.parse(existing);
		meta.pages = pages;
		const next = `${JSON.stringify(meta, null, 2)}\n`;
		if (next !== existing) {
			writeFileSync(target, next, 'utf8');
			count += 1;
		}
	}
	return count;
}

let changed = 0;
for (const config of SOURCES) {
	mkdirSync(dirname(config.target), { recursive: true });
	const block = generateBlock(config);
	changed += injectAcrossLocales(config.target, block);
}

for (const config of GENERATED_SOURCES) {
	mkdirSync(dirname(config.target), { recursive: true });
	if (config.target.endsWith(`reference${sep}profile-fields.mdx`)) {
		ensureProfileFieldsPage(config.target);
	}
	const block = config.generate();
	changed += injectAcrossLocales(config.target, block);
}

if (injectChangelog(CHANGELOG_TARGET)) changed += 1;
// Locale changelog copies carry the same markers; missing markers skip the
// copy rather than throwing, since only the English shell is mandatory.
for (const locale of LOCALE_DIRS) {
	const localeChangelog = join(DOCS_ROOT, locale, 'changelog.mdx');
	let existing;
	try {
		existing = readFileSync(localeChangelog, 'utf8');
	} catch {
		continue;
	}
	if (!existing.includes(CHANGELOG_START)) continue;
	if (injectChangelog(localeChangelog)) changed += 1;
}

if (injectRoadmap(ROADMAP_TARGET)) changed += 1;

const commands = commandDefinitions();
const pipelinePages = pipelineNavPages(commands);
changed += writeCommandPages(commands);
changed += writePipelineNav(pipelinePages);
if (inject(join(PIPELINE_DIR, 'index.mdx'), commandIndexBlock(commands, pipelinePages))) changed += 1;

// Inventories: the walked sources, the emitter-backed blocks, the changelog,
// the roadmap, the command pages, the command nav and the command index.
const total = SOURCES.length + GENERATED_SOURCES.length + 5;
process.stdout.write(`update-reference-inventory: refreshed ${total} inventories; changed ${changed} pages.\n`);
