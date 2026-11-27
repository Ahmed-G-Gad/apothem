// SPDX-License-Identifier: MIT

// Shorten Markdown text for the generated reference tables without leaving
// markup the page would show as literal characters.
//
// `cutAtWord(text, limit)` cuts `text` to at most `limit` characters on a word
// boundary and ends it with " …". A cut can land inside inline markup, and the
// open half would then show on the page as a stray character: a backtick with
// no partner, a "**" that never closes, a "[" or "(" from a half-cut link. The
// cut therefore drops a trailing unclosed code span, bold run, link label or
// link target. When that leaves nothing (the text opens with one long code
// span, for example), it falls back to a hard cut at `limit` that closes an
// open code span and removes any other unclosed marker, so the excerpt is
// never just " …".

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

function countBackticks(text) {
	return (text.match(/`/g) || []).length;
}

// Drop the trailing fragment that opens a construct the cut never closed,
// repeating until nothing changes (dropping one fragment can expose another).
function dropUnclosed(text) {
	let cut = text;
	for (;;) {
		const before = cut;
		if (countBackticks(cut) % 2 === 1) cut = cut.slice(0, cut.lastIndexOf('`'));
		const masked = maskCode(cut);
		const bold = [...masked.matchAll(BOLD)].map((m) => m.index);
		const paren = lastUnclosed(masked, '(', ')');
		const bracket = lastUnclosed(masked, '[', ']');
		if (bold.length % 2 === 1) {
			cut = cut.slice(0, bold[bold.length - 1]);
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

// Keep the text of a hard cut but make its markup whole: close an open code
// span and remove the unclosed "**", "[" and "(" markers (only the markers).
function closeHardCut(text) {
	let cut = text;
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
			at = Math.max(lastUnclosed(masked, '(', ')'), lastUnclosed(masked, '[', ']'));
		}
		if (at === -1) return cut.trim();
		cut = cut.slice(0, at) + cut.slice(at + width);
	}
}

export function cutAtWord(text, limit) {
	if (text.length <= limit) return text;
	const hard = text.slice(0, limit);
	const space = hard.lastIndexOf(' ');
	const cut = dropUnclosed(space > 0 ? hard.slice(0, space) : hard);
	return `${cut || closeHardCut(hard)} …`;
}
