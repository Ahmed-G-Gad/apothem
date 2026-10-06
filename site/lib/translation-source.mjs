// SPDX-License-Identifier: MIT

/**
 * The source hash that ties a locale page to the English text it translates.
 *
 * Each page under `content/docs/<locale>/` records `sourceHash` in its
 * frontmatter: the hash of the English page it was translated from. The docs
 * route recomputes the hash from the current English page at build time; when
 * the two differ, the English page has changed since the translation and the
 * locale page shows a staleness marker. `scripts/translation-sources.mjs`
 * reports stale pages and records a new hash after a translation is refreshed.
 *
 * The hash covers the English file's translatable text: its frontmatter and
 * prose, with line endings and trailing spaces normalized. Generated blocks
 * (the reference tables and the changelog body) are left out, because the
 * reference generator rewrites them in every locale copy at once, so a change
 * there never makes a translation stale.
 */

import { createHash } from 'node:crypto';

const GENERATED_REGIONS = [
	['{/* apothem:generated-reference:start */}', '{/* apothem:generated-reference:end */}'],
	['{/* apothem:changelog:start */}', '{/* apothem:changelog:end */}'],
];

/**
 * The part of an English page a translation follows.
 *
 * @param {string} source - the English page's full text.
 * @returns {string}
 */
export function translatableText(source) {
	let text = source.replace(/\r\n?/g, '\n');
	for (const [start, end] of GENERATED_REGIONS) {
		let from = 0;
		for (;;) {
			const open = text.indexOf(start, from);
			if (open === -1) break;
			const close = text.indexOf(end, open + start.length);
			if (close === -1) break;
			text = text.slice(0, open + start.length) + text.slice(close);
			from = open + start.length + end.length;
		}
	}
	return text
		.split('\n')
		.map((line) => line.trimEnd())
		.join('\n')
		.trim();
}

/**
 * The 16-hex-digit hash a locale page records as `sourceHash`.
 *
 * @param {string} englishSource - the English page's full text.
 * @returns {string}
 */
export function sourceHash(englishSource) {
	return createHash('sha256').update(translatableText(englishSource)).digest('hex').slice(0, 16);
}
