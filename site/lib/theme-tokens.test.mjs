// SPDX-License-Identifier: MIT

// Contrast test for the light theme's `--primary` token (app/global.css).
//
// `--primary` colours active navigation text: the docs sidebar's active item
// sits on a 10% primary wash, and an active "On this page" entry can be inline
// code on the secondary surface. axe measured the earlier value (#007f51) at
// 4.40:1 and 4.37:1 there, under the 4.5:1 WCAG 1.4.3 requires. This test reads
// the token from the stylesheet and checks it on each surface. Run:
//
//   cd site && node --test lib/theme-tokens.test.mjs

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

/** Convert an OKLCH colour to sRGB hex (CSS Color 4 matrices). */
function oklchToHex(l, c, h) {
	const a = c * Math.cos((h * Math.PI) / 180);
	const b = c * Math.sin((h * Math.PI) / 180);
	const lms = [
		(l + 0.3963377774 * a + 0.2158037573 * b) ** 3,
		(l - 0.1055613458 * a - 0.0638541728 * b) ** 3,
		(l - 0.0894841775 * a - 1.291485548 * b) ** 3,
	];
	const linear = [
		4.0767416621 * lms[0] - 3.3077115913 * lms[1] + 0.2309699292 * lms[2],
		-1.2684380046 * lms[0] + 2.6097574011 * lms[1] - 0.3413193965 * lms[2],
		-0.0041960863 * lms[0] - 0.7034186147 * lms[1] + 1.707614701 * lms[2],
	];
	const encode = (x) => {
		const v = Math.min(Math.max(x, 0), 1);
		return v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055;
	};
	return `#${linear.map((x) => Math.round(encode(x) * 255).toString(16).padStart(2, '0')).join('')}`;
}

function channels(hex) {
	return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
}

function luminance(hex) {
	const [r, g, b] = channels(hex)
		.map((v) => v / 255)
		.map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a, b) {
	const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (hi + 0.05) / (lo + 0.05);
}

function mix(fg, bg, alpha) {
	const [f, b] = [channels(fg), channels(bg)];
	return `#${f.map((v, i) => Math.round(alpha * v + (1 - alpha) * b[i]).toString(16).padStart(2, '0')).join('')}`;
}

/** Read a light-theme token (the `:root` block) from app/global.css. */
function lightToken(name) {
	const css = readFileSync(new URL('../app/global.css', import.meta.url), 'utf8');
	const root = css.slice(css.indexOf(':root {'), css.indexOf('.dark {'));
	const match = root.match(new RegExp(`--${name}: oklch\\(([\\d.]+) ([\\d.]+) ([\\d.]+)\\)`));
	assert.ok(match, `--${name} not found in the light theme`);
	return oklchToHex(Number(match[1]), Number(match[2]), Number(match[3]));
}

describe('light theme --primary', () => {
	it('reaches 4.5:1 on the active-item wash, the secondary surface and the page', () => {
		const primary = lightToken('primary');
		const background = lightToken('background');
		const surfaces = {
			'10% primary wash': mix(primary, background, 0.1),
			secondary: lightToken('secondary'),
			background,
		};
		const failures = Object.entries(surfaces)
			.map(([name, surface]) => [name, contrast(primary, surface)])
			.filter(([, ratio]) => ratio < 4.5)
			.map(([name, ratio]) => `${primary} on ${name}: ${ratio.toFixed(2)}`);
		assert.deepEqual(failures, []);
	});

	it('keeps white button labels at 4.5:1', () => {
		assert.ok(contrast('#ffffff', lightToken('primary')) >= 4.5);
	});
});
