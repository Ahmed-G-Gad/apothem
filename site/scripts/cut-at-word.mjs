// SPDX-License-Identifier: MIT

// Shorten Markdown text for the generated reference tables without leaving
// markup the page would show as literal characters.
//
// `cutAtWord(text, limit)` cuts `text` to at most `limit` characters on a word
// boundary and ends it with " …". A cut can land inside inline markup, and the
// open half would then show on the page as a stray character: a backtick with
// no partner, a "**" that never closes, a "*", "_" or "__" whose closer the
// cut removed, a "[" or "(" from a half-cut link. The cut therefore drops a
// trailing unclosed code span, bold run, emphasis run, link label or link
// target. When that leaves nothing (the text opens with one long code span,
// for example), it falls back to a hard cut at `limit` that closes an open
// code span and removes any other unclosed marker, so the excerpt is never
// just " …". A hard cut inside a link target ("[label](/very/lo") keeps only
// the label, as plain text.
//
// Emphasis follows CommonMark's flanking rules closely enough for one-line
// table text: a "*", "_" or "__" opens only when a word follows it, and "_"
// never opens or closes inside a word, so snake_case names and "5 * 3" are left
// alone. Runs of three or more "*" or "_" are not treated as markup. Openers
// and closers are paired over the whole uncut text, with code spans, link
// targets, autolinks and bare URLs masked first, so a run counts as unclosed
// only when it opens before the cut and its closer lies past it. A run that
// never closes in the full text shows on the page as a literal character, and
// the cut leaves it alone.

const BOLD = /\*\*/g;

// Blank out the inside of each complete code span, keeping positions, so the
// markers checked below are only the ones outside code.
function maskCode(text) {
	return text.replace(/`[^`]*`/g, (span) => ' '.repeat(span.length));
}

function lastUnclosed(text, open, close) {
	const stack = [];
	for (let i = 0; i < text.length; i += 1) {
		if (text[i] === open) stack.push(i);
		else if (text[i] === close && stack.length > 0) stack.pop();
	}
	return stack.length > 0 ? stack[stack.length - 1] : -1;
}

const PUNCT = /[\p{P}\p{S}]/u;
const SPACE = /\s/u;

// Fill the inside of each code span, link target ("](...)"), autolink
// ("<https://...>") and bare URL with a letter, keeping positions and the
// delimiters around it, so no "*" or "_" inside one reads as emphasis.
function maskForEmphasis(text) {
	const fill = (s) => 'x'.repeat(s.length);
	return text
		.replace(/`[^`]*`/g, (span) => `\`${fill(span.slice(1, -1))}\``)
		.replace(/\]\([^()\s]*\)/g, (target) => `](${fill(target.slice(2, -1))})`)
		.replace(/<[a-z][a-z0-9+.-]*:[^\s<>]*>/gi, (link) => `<${fill(link.slice(1, -1))}>`)
		.replace(/\b(?:https?|ftp):\/\/[^\s<>()]+/gi, fill);
}

// The emphasis pairs of the whole text, "*", "_" and "__" runs only ("**" is
// left to the bold check): each opener's index, its closer's index and the run
// width. An opener that never closes is literal text and is left out.
function emphasisPairs(text) {
	const masked = maskForEmphasis(text);
	const stack = [];
	const pairs = [];
	for (const m of masked.matchAll(/\*+|_+/g)) {
		const run = m[0];
		const ch = run[0];
		if (run.length > 2 || (ch === '*' && run.length === 2)) continue;
		const before = masked[m.index - 1] ?? ' ';
		const after = masked[m.index + run.length] ?? ' ';
		const left = !SPACE.test(after) && (!PUNCT.test(after) || SPACE.test(before) || PUNCT.test(before));
		const right = !SPACE.test(before) && (!PUNCT.test(before) || SPACE.test(after) || PUNCT.test(after));
		const opens = ch === '*' ? left : left && (!right || PUNCT.test(before));
		const closes = ch === '*' ? right : right && (!left || PUNCT.test(after));
		const top = stack.findLastIndex((o) => o.run === run);
		if (closes && top !== -1) {
			pairs.push({ open: stack[top].index, close: m.index, width: run.length });
			stack.splice(top);
		} else if (opens) {
			stack.push({ run, index: m.index });
		}
	}
	return pairs.sort((a, b) => a.open - b.open);
}

// The pairs that open inside the first `length` characters and whose closer
// does not fit inside them, in opening order.
function splitByCut(pairs, length) {
	return pairs.filter((p) => p.open < length && p.close + p.width > length);
}

function countBackticks(text) {
	return (text.match(/`/g) || []).length;
}

// Drop the trailing fragment that opens a construct the cut never closed,
// repeating until nothing changes (dropping one fragment can expose another).
// `full` is the uncut text, of which `text` is a prefix.
function dropUnclosed(text, full) {
	const pairs = emphasisPairs(full);
	let cut = text;
	for (;;) {
		const before = cut;
		if (countBackticks(cut) % 2 === 1) cut = cut.slice(0, cut.lastIndexOf('`'));
		const masked = maskCode(cut);
		const bold = [...masked.matchAll(BOLD)].map((m) => m.index);
		const paren = lastUnclosed(masked, '(', ')');
		const bracket = lastUnclosed(masked, '[', ']');
		const emphasis = splitByCut(pairs, cut.length).at(-1);
		if (bold.length % 2 === 1) {
			cut = cut.slice(0, bold[bold.length - 1]);
		} else if (emphasis) {
			cut = cut.slice(0, emphasis.open);
		} else if (paren !== -1) {
			cut = cut.slice(0, paren);
			// "[label](" cut inside the target: drop the label too, or the page
			// shows "[label]" with its brackets.
			if (cut.endsWith(']')) {
				const open = lastUnclosed(maskCode(cut).slice(0, -1), '[', ']');
				if (open !== -1) cut = cut.slice(0, open);
			}
		} else if (bracket !== -1) {
			cut = cut.slice(0, bracket);
		}
		cut = cut.trimEnd();
		if (cut === before) return cut;
	}
}

// Keep the text of a hard cut but make its markup whole: remove the opener of
// each "*", "_" or "__" run the cut splits from its closer (and any part of
// that closer the cut kept), close an open code span, and remove the unclosed
// "**", "[" and "(" markers (only the markers). An unclosed "(" right after a
// "]" is a cut link target: the target and the label's "[" and "]" go, and
// the label stays as plain text. `full` is the uncut text, of which `text` is
// a prefix.
function closeHardCut(text, full) {
	let cut = text;
	const ranges = [];
	for (const p of splitByCut(emphasisPairs(full), cut.length)) {
		ranges.push([p.open, p.open + p.width]);
		if (p.close < cut.length) ranges.push([p.close, cut.length]);
	}
	for (const [start, end] of ranges.sort((a, b) => b[0] - a[0])) {
		cut = cut.slice(0, start) + cut.slice(end);
	}
	if (countBackticks(cut) % 2 === 1) cut = `${cut.trimEnd()}\``;
	for (;;) {
		const masked = maskCode(cut);
		const bold = [...masked.matchAll(BOLD)].map((m) => m.index);
		let at = -1;
		let width = 1;
		if (bold.length % 2 === 1) {
			at = bold[bold.length - 1];
			width = 2;
		} else {
			const paren = lastUnclosed(masked, '(', ')');
			if (paren > 0 && masked[paren - 1] === ']') {
				const open = lastUnclosed(masked.slice(0, paren - 1), '[', ']');
				if (open !== -1) {
					// An empty label leaves the target's text instead.
					const label = cut.slice(open + 1, paren - 1);
					cut = cut.slice(0, open) + (label || cut.slice(paren + 1));
					continue;
				}
			}
			at = Math.max(paren, lastUnclosed(masked, '[', ']'));
		}
		if (at === -1) return cut.trim();
		cut = cut.slice(0, at) + cut.slice(at + width);
	}
}

export function cutAtWord(text, limit) {
	if (text.length <= limit) return text;
	const hard = text.slice(0, limit);
	const space = hard.lastIndexOf(' ');
	const cut = dropUnclosed(space > 0 ? hard.slice(0, space) : hard, text);
	return `${cut || closeHardCut(hard, text)} …`;
}
