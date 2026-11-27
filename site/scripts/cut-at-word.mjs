// SPDX-License-Identifier: MIT

// Shorten Markdown text for the generated reference tables without leaving
// markup the page would show as literal characters.
//
// `cutAtWord(text, limit)` shortens `text` to at most `limit` visible
// characters, on a word boundary, and ends it with " …". Visible characters
// are what the page shows: text, code-span content and link labels, not the
// markup around them or a link's target. Text that already fits is returned
// unchanged.
//
// The text is parsed as GFM Markdown (micromark and mdast, the parser the docs
// site already ships), so the cut sees the same inline nodes the page renders.
// Every node that ends before the cut is kept as its exact source text. The one
// node the cut lands in is handled whole, so no markup is ever left open:
//
//   - text keeps the part before the cut, sliced from its source so escapes
//     and character references stay whole;
//   - a code span, image, HTML tag or other atomic node is dropped;
//   - an emphasis, bold or strikethrough run is dropped with its content;
//   - a link keeps the part of its label before the cut, as plain text.
//
// When that leaves nothing (the text opens with one long code span or bold
// run, for example), a second pass keeps more of the node the cut lands in: a
// code span is shortened and closed again, and an emphasis, bold or
// strikethrough run keeps the content before the cut without its markers. The
// cut there is still on a word boundary when the first `limit` visible
// characters hold a space, and a hard cut at `limit` otherwise.

import { fromMarkdown } from 'mdast-util-from-markdown';
import { gfmFromMarkdown, gfmToMarkdown } from 'mdast-util-gfm';
import { toMarkdown } from 'mdast-util-to-markdown';
import { gfm } from 'micromark-extension-gfm';
import { decodeString } from 'micromark-util-decode-string';

// GFM's autolink-literal step also finds URLs the tokenizer skipped (after a
// "[" or a code span, for example) by rewriting text nodes after the parse,
// and the nodes it makes carry no source position. That step is left out: such
// a URL stays plain text, which shows the same characters.
const PARSE_OPTIONS = {
	extensions: [gfm()],
	mdastExtensions: gfmFromMarkdown().map((extension) =>
		extension.transforms ? { ...extension, transforms: [] } : extension,
	),
};
const SERIALIZE_OPTIONS = { extensions: [gfmToMarkdown()] };

// Parents whose children are inline (phrasing) content. The children of any
// other parent are blocks, which the visible text separates with one space.
const PHRASING_PARENTS = new Set([
	'paragraph',
	'heading',
	'tableCell',
	'emphasis',
	'strong',
	'delete',
	'link',
	'linkReference',
]);

const WRAPPERS = new Set(['emphasis', 'strong', 'delete']);
const LINKS = new Set(['link', 'linkReference']);

export function parseMarkdown(text) {
	return fromMarkdown(text, PARSE_OPTIONS);
}

// The text a node shows on the page.
export function visibleText(node) {
	switch (node.type) {
		case 'text':
		case 'inlineCode':
		case 'html':
			return node.value;
		case 'image':
		case 'imageReference':
			return node.alt || '';
		case 'break':
			return ' ';
		case 'footnoteReference':
			return node.label || node.identifier || '';
		default:
			break;
	}
	if (!node.children) return '';
	const parts = node.children.map(visibleText);
	return parts.join(PHRASING_PARENTS.has(node.type) ? '' : ' ');
}

// The shown text of `node` as a string, and the indexes in it of the markup
// characters (*, _, ~, [ and backtick) that show as literal text rather than
// as code, a link target or other markup.
const MARKUP = /[*_~[`]/g;

function literalMarkup(node, out = { shown: '', literal: new Set() }) {
	if (node.type === 'text') {
		for (const m of node.value.matchAll(MARKUP)) out.literal.add(out.shown.length + m.index);
		out.shown += node.value;
	} else if (!node.children) {
		out.shown += visibleText(node);
	} else {
		node.children.forEach((child, index) => {
			if (index > 0 && !PHRASING_PARENTS.has(node.type)) out.shown += ' ';
			literalMarkup(child, out);
		});
	}
	return out;
}

// Whether `cut` (a cut of the source, " …" included) shows the start of what
// the source shows and no markup character as literal text that the source
// did not show as literal text. A cut can change how the markup before it
// pairs (a "_" closer that a following word turns into an inner-word "_"), so
// every candidate is parsed again and checked.
function faithful(cut, original) {
	const result = literalMarkup(parseMarkdown(cut));
	if (!result.shown.endsWith(' …')) return false;
	const body = result.shown.slice(0, -2);
	if (!original.shown.startsWith(body)) return false;
	for (const index of result.literal) {
		if (index < body.length && !original.literal.has(index)) return false;
	}
	return true;
}

function source(node, text) {
	if (!node.position) return serialize(node);
	return text.slice(node.position.start.offset, node.position.end.offset);
}

function serialize(node) {
	return toMarkdown(node, SERIALIZE_OPTIONS).replace(/\n+$/, '');
}

// The source of a text node that shows its first `count` characters: the
// shortest source prefix that decodes to them, so a backslash escape or a
// character reference is never split. When no prefix decodes exactly (a
// reference that decodes to two code units, cut between them), the shown
// characters are serialized again instead.
function textPrefix(node, text, count) {
	const raw = source(node, text);
	const want = node.value.slice(0, count);
	for (let end = count; end <= raw.length; end += 1) {
		const decoded = decodeString(raw.slice(0, end));
		if (decoded === want) return raw.slice(0, end);
		if (decoded.length > want.length + 32) break;
	}
	return serialize({ type: 'paragraph', children: [{ type: 'text', value: want }] });
}

// Render `tree` cut at visible offset `at`. `keepMore` is the second pass: a
// code span the cut lands in is shortened and closed, and an emphasis, bold or
// strikethrough run keeps its content without its markers.
function render(tree, text, at, keepMore) {
	let offset = 0;

	// The rendered children of `node`, with the source between kept children
	// (for blocks, the line breaks and markers between them); null when none
	// is kept.
	function children(node) {
		const flow = !PHRASING_PARENTS.has(node.type);
		let out = '';
		let previous = null;
		for (const child of node.children) {
			if (flow && previous) offset += 1;
			const rendered = emit(child);
			if (rendered === null) break;
			if (previous) out += text.slice(previous.position.end.offset, child.position.start.offset);
			out += rendered;
			previous = child;
		}
		return out.trim() ? out : null;
	}

	function emit(node) {
		const start = offset;
		const length = visibleText(node).length;
		if (start >= at) return null;
		if (start + length <= at) {
			offset += length;
			return source(node, text);
		}
		const room = at - start;
		if (node.type === 'text') {
			offset += room;
			return textPrefix(node, text, room);
		}
		if (node.type === 'inlineCode') {
			const value = node.value.slice(0, room).trimEnd();
			if (!keepMore || !value) return null;
			offset += room;
			return serialize({ type: 'inlineCode', value });
		}
		if (node.type === 'html' && keepMore) {
			offset += room;
			return node.value.slice(0, room);
		}
		if ((node.type === 'image' || node.type === 'imageReference') && keepMore) {
			offset += room;
			return serialize({ type: 'paragraph', children: [{ type: 'text', value: node.alt.slice(0, room) }] });
		}
		if (!node.children || !node.position) return null;
		if (WRAPPERS.has(node.type)) return keepMore ? children(node) : null;
		if (LINKS.has(node.type)) return children(node);
		const inner = children(node);
		if (inner === null || node.children.length === 0) return null;
		// A block or paragraph keeps its own opening markers ("- ", "> ").
		return text.slice(node.position.start.offset, node.children[0].position.start.offset) + inner;
	}

	return (emit(tree) ?? '').trim();
}

export function cutAtWord(text, limit) {
	if (text.length <= limit) return text;
	const tree = parseMarkdown(text);
	const shown = visibleText(tree);
	if (shown.length <= limit) return text;
	const original = literalMarkup(tree);
	const accept = (cut) => (cut && faithful(`${cut} …`, original) ? `${cut} …` : null);
	// Each word boundary at or before the limit, latest first.
	for (let at = shown.lastIndexOf(' ', limit - 1); at > 0; at = shown.lastIndexOf(' ', at - 1)) {
		const cut = render(tree, text, at, false) || render(tree, text, at, true);
		const result = accept(cut);
		if (result) return result;
	}
	// No cut keeps the markup whole (a code span that opens with spaces, cut to
	// one character, say): the text is left as it is rather than broken.
	return accept(render(tree, text, limit, true)) ?? text;
}
