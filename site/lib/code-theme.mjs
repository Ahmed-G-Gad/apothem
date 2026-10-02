// SPDX-License-Identifier: MIT

/**
 * Colour replacements for the code-block syntax themes.
 *
 * The docs highlight code with Shiki's github-light and github-dark themes (the
 * Fumadocs defaults). Several of their token colours fail WCAG 1.4.3 (4.5:1)
 * on the surfaces a code block sits on: the dark comment colour #6a737d
 * measured 3.65:1, and github-light's comment, keyword, variable and tag
 * colours fall under 4.5:1 on the light card and tab surfaces. Each
 * replacement keeps the token's hue family and clears 4.5:1 on every code
 * surface; `code-theme.test.mjs` checks every token colour of both themes.
 *
 * `source.config.ts` passes this map to Shiki's `colorReplacements` option,
 * keyed by theme name. Keys are lower case because Shiki looks colours up in
 * lower case.
 */
export const CODE_COLOR_REPLACEMENTS = {
	'github-light': {
		'#6a737d': '#57606a', // comments
		'#d73a49': '#c9252f', // keywords, storage
		'#e36209': '#a04100', // variables
		'#22863a': '#1b7c38', // tags, regexp escapes, quotes
	},
	'github-dark': {
		'#6a737d': '#8b949e', // comments
	},
};
