// SPDX-License-Identifier: MIT

// Unit test for the URL-path locale lookup. Client components that render
// above the per-locale I18nProvider (the search dialog, mounted by the root
// provider) cannot read the locale from context, so they derive it from the
// pathname. Run:
//
//   cd site && node --test --experimental-strip-types lib/i18n.test.mjs

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
	COHORT_LOCALES,
	DEFAULT_LOCALE,
	ROUTED_NON_DEFAULT_LOCALES,
	documentLocaleFromPathname,
	localeFromPathname,
} from './i18n.ts';

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

describe('documentLocaleFromPathname', () => {
	it('gives the language tag and direction of the routed locale', () => {
		assert.deepEqual(documentLocaleFromPathname('/ar/docs/install'), { lang: 'ar', dir: 'rtl' });
		assert.deepEqual(documentLocaleFromPathname('/zh-cn/docs'), { lang: 'zh-CN', dir: 'ltr' });
		assert.deepEqual(documentLocaleFromPathname('/pt-br/'), { lang: 'pt-BR', dir: 'ltr' });
	});

	it('gives English, left to right, for root and non-locale paths', () => {
		for (const pathname of ['/', '', '/docs/install', '/en/docs', '/docs/ar']) {
			assert.deepEqual(documentLocaleFromPathname(pathname), { lang: DEFAULT_LOCALE, dir: 'ltr' });
		}
	});

	it('matches the cohort table for every locale', () => {
		for (const locale of COHORT_LOCALES) {
			const pathname = locale.path ? `/${locale.path}/docs` : '/docs';
			assert.deepEqual(documentLocaleFromPathname(pathname), { lang: locale.code, dir: locale.dir });
		}
	});
});
