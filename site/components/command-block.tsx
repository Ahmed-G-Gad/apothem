// SPDX-License-Identifier: MIT

'use client';

import * as React from 'react';
import { Check, Copy } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * A terminal-styled command block for the landing Quick Start. Renders a row
 * of window dots and a monospace command body in the field/polygon palette.
 *
 * Each command line carries a keyboard-accessible copy-to-clipboard button
 * that writes the command (not its preceding comment) via
 * `navigator.clipboard` and shows a transient Check confirmation for ~2s.
 */
export function CommandBlock({
  lines,
  className,
}: {
  lines: { comment?: string; cmd: string }[];
  className?: string;
}) {
  return (
    <div
      className={cn(
        'overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] text-start shadow-sm',
        className
      )}
    >
      <div className="flex items-center gap-1.5 border-b border-[var(--border)] bg-[var(--muted)]/40 px-4 py-2.5">
        <span className="size-2.5 rounded-full bg-[var(--border)]" />
        <span className="size-2.5 rounded-full bg-[var(--border)]" />
        <span className="size-2.5 rounded-full bg-[color-mix(in_oklch,var(--primary)_60%,transparent)]" />
        <span className="ms-2 font-mono text-xs text-[var(--muted-foreground)]">
          install
        </span>
      </div>
      <div className="font-mono text-[0.8125rem] leading-relaxed">
        {lines.map((line, i) => (
          <div
            key={i}
            className={cn(
              'group flex items-start gap-2 px-4 py-3',
              i < lines.length - 1 && 'border-b border-[var(--border)]/60'
            )}
          >
            <pre className="min-w-0 flex-1 overflow-x-auto">
              <code>
                {line.comment ? (
                  <span className="block text-[var(--muted-foreground)]">
                    {line.comment}
                  </span>
                ) : null}
                <span className="block">
                  <span className="select-none text-[var(--primary)]">$ </span>
                  <span className="text-[var(--foreground)]">{line.cmd}</span>
                </span>
              </code>
            </pre>
            <CopyButton value={line.cmd} />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Copy-to-clipboard control for a single command line. Writes `value` to the
 * clipboard and swaps the Copy icon for a Check icon for ~2s as confirmation.
 */
function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = React.useState(false);
  const timeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(
    () => () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    },
    []
  );

  const onCopy = React.useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard write can reject (permissions, insecure context); fail quietly
      // and leave the button in its idle state rather than throwing.
    }
  }, [value]);

  return (
    <button
      type="button"
      onClick={onCopy}
      aria-label={copied ? 'Copied command' : 'Copy command'}
      title={copied ? 'Copied' : 'Copy command'}
      className="inline-flex size-7 shrink-0 items-center justify-center rounded-md text-[var(--muted-foreground)] opacity-70 transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)] focus-visible:opacity-100 group-hover:opacity-100"
    >
      {copied ? (
        <Check className="size-4 text-[var(--primary)]" aria-hidden />
      ) : (
        <Copy className="size-4" aria-hidden />
      )}
    </button>
  );
}
