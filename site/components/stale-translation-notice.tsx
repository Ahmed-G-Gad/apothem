// SPDX-License-Identifier: MIT

/**
 * The staleness marker on a translated docs page whose English source changed
 * after the translation was made (see `lib/translation-status.ts`). It is a
 * one-line note, not a banner: it states the fact and links the English page,
 * which is authoritative. The site has no translation dictionary for chrome,
 * so the note is English and carries `lang="en"` and `dir="ltr"` (WCAG 3.1.2),
 * including inside right-to-left pages.
 */
export function StaleTranslationNotice({ englishUrl }: { englishUrl: string }) {
  return (
    <p
      role="note"
      lang="en"
      dir="ltr"
      data-translation-stale=""
      className="not-prose rounded-lg border border-fd-border bg-fd-card px-3 py-2 text-sm text-fd-muted-foreground"
    >
      The English page has changed since this translation was made.{' '}
      <a
        href={englishUrl}
        className="font-medium text-fd-foreground underline underline-offset-4"
      >
        Read the English page
      </a>
      .
    </p>
  );
}
