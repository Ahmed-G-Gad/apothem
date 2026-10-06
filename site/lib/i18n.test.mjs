// SPDX-License-Identifier: MIT

// Unit test for the URL-path locale lookup. Client components that render
// above the per-locale I18nProvider (the search dialog, mounted by the root
// provider) cannot read the locale from context, so they derive it from the
// pathname. Run:
//
//   cd site && node --test --experimental-strip-types lib/i18n.test.mjs

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { DEFAULT_LOCALE, ROUTED_NON_DEFAULT_LOCALES, localeFromPathname } from './i18n.ts';

describe('localeFromPathname', () => {
	it('returns the routed locale named by the first path segment', () => {
		assert.equal(localeFromPathname('/ja/docs/install'), 'ja');
		assert.equal(localeFromPathname('/zh-cn/docs'), 'zh-cn');
		assert.equal(localeFromPathname('/ar'), 'ar');
		assert.equal(localeFromPathname('/pt-br/'), 'pt-br');
	});

	it('returns the default locale for English paths at the root', () => {
		assert.equal(localeFromPathname('/'), DEFAULT_LOCALE);
		assert.equal(localeFromPathname('/docs/install'), DEFAULT_LOCALE);
		assert.equal(localeFromPathname(''), DEFAULT_LOCALE);
	});

	it('does not treat a non-locale segment as a locale', () => {
		assert.equal(localeFromPathname('/en/docs'), DEFAULT_LOCALE);
		assert.equal(localeFromPathname('/docs/ja'), DEFAULT_LOCALE);
	});

	it('resolves every routed non-default locale', () => {
		for (const locale of ROUTED_NON_DEFAULT_LOCALES) {
			assert.equal(localeFromPathname(`/${locale}/docs`), locale);
		}
	});
});
