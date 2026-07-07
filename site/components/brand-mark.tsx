// SPDX-License-Identifier: MIT

import Image from 'next/image';
import { cn } from '@/lib/utils';

/**
 * The apothem brand mark — the existing hexagon-with-apothem logo at
 * public/logo.svg. Both light- and dark-tuned files ship in public/; CSS
 * theme classes swap them so the mark stays legible on either surface
 * without a runtime theme read.
 */
export function BrandMark({
  size = 96,
  className,
  decorative = false,
}: {
  size?: number;
  className?: string;
  /**
   * When the mark sits beside a visible "Apothem" text label (nav, footer),
   * the image is decorative and carries an empty alt so screen readers do not
   * announce the brand name twice (WCAG 1.1.1). Standalone uses (the hero)
   * leave this false so the mark carries its own meaningful alt.
   */
  decorative?: boolean;
}) {
  const alt = decorative ? '' : 'Apothem';
  return (
    <span
      className={cn('relative inline-block', className)}
      style={{ width: size, height: size }}
    >
      <Image
        src="/logo.svg"
        alt={alt}
        width={size}
        height={size}
        priority
        className="block dark:hidden"
      />
      <Image
        src="/logo-dark.svg"
        alt={alt}
        width={size}
        height={size}
        priority
        className="hidden dark:block"
      />
    </span>
  );
}
