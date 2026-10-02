// SPDX-License-Identifier: MIT

// Contrast test for the code-block syntax colours.
//
// The docs highlight code with Shiki's github-light and github-dark themes.
// Their stock comment colour (#6a737d) measured 3.65:1 on the dark code-block
// surface, and several github-light token colours sit under 4.5:1 on the
// light surfaces, failing WCAG 1.4.3. `code-theme.mjs` replaces those colours;
// this test applies the replacements to every token colour the themes define
// and checks each against every surface a code block can sit on. Run:
//
//   cd site && node --test lib/code-theme.test.mjs

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import githubDark from '@shikijs/themes/github-dark';
import githubLight from '@shikijs/themes/github-light';
import { CODE_COLOR_REPLACEMENTS } from './code-theme.mjs';

// Code-block surfaces per theme: the figure background (`bg-fd-card`), the
// tabbed variant (`bg-fd-secondary`), and the page background, as computed in
// the built site: light uses the site's own tokens (white and oklch(0.95 0.006
// 250)); dark resolves to the Fumadocs neutral palette.
const SURFACES = {
	'github-light': ['#ffffff', '#ebeff2', '#f2f2f2'],
	'github-dark': ['#191919', '#212121', '#121212'],
};

function luminance(hex) {
	const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
	const [r, g, b] = channels.map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a, b) {
	const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (hi + 0.05) / (lo + 0.05);
}

// Token colours a code block can render as text. A rule that also sets its own
// background (diff markers, illegal characters) is drawn on that background,
// not on the code-block surface, so it is out of scope here.
function textColours(theme) {
	const colours = new Set();
	for (const rule of theme.tokenColors) {
		const settings = rule.settings || {};
		if (settings.foreground && !settings.background) colours.add(settings.foreground.toLowerCase());
	}
	return [...colours];
}

describe('code-block syntax colours', () => {
	for (const theme of [githubLight, githubDark]) {
		it(`${theme.name} token colours reach 4.5:1 on every code surface`, () => {
			const replacements = CODE_COLOR_REPLACEMENTS[theme.name] || {};
			const failures = [];
			for (const colour of textColours(theme)) {
				const shown = replacements[colour] || colour;
				for (const surface of SURFACES[theme.name]) {
					const ratio = contrast(shown, surface);
					if (ratio < 4.5) failures.push(`${colour} -> ${shown} on ${surface}: ${ratio.toFixed(2)}`);
				}
			}
			assert.deepEqual(failures, []);
		});
	}

	it('uses lower-case keys, as Shiki matches replacements case-insensitively by lower case', () => {
		for (const map of Object.values(CODE_COLOR_REPLACEMENTS)) {
			for (const key of Object.keys(map)) assert.equal(key, key.toLowerCase());
		}
	});
});
