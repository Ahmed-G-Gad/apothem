// SPDX-License-Identifier: MIT

'use client';

import * as React from 'react';
import { useTheme } from 'next-themes';
import { Moon, Sun } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Light/dark theme toggle shared by the marketing landing nav and the docs
 * header, so the control sits in one consistent top-right location across every
 * surface. It flips the `next-themes` theme that fumadocs' RootProvider drives.
 * Renders a stable placeholder until mounted so the button does not flash the
 * wrong icon during hydration (the theme is only known client-side).
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = resolvedTheme === 'dark';

  return (
    <button
      type="button"
      aria-label={
        mounted
          ? `Switch to ${isDark ? 'light' : 'dark'} theme`
          : 'Toggle theme'
      }
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      className={cn(
        'inline-flex size-9 items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)]',
        className,
      )}
    >
      {/* Until mounted, render the dark-default icon (the site defaults to
          dark) to avoid a hydration mismatch on the icon. */}
      {mounted && !isDark ? (
        <Sun className="size-5" aria-hidden />
      ) : (
        <Moon className="size-5" aria-hidden />
      )}
    </button>
  );
}
