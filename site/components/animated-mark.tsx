// SPDX-License-Identifier: MIT

import { cn } from '@/lib/utils';

/**
 * The animated "Radiant Apothem" mark for the landing hero. The SVG at
 * public/logo-animated.svg carries its own internal CSS animation (the emerald
 * apothem drawing from center to each edge) and a `prefers-reduced-motion`
 * guard that holds the static radiant mark for visitors who ask for reduced
 * motion. Next/Image rasterizes SVGs and strips that internal animation, so
 * the mark is rendered as a plain <img> to keep the motion intact while
 * staying static-export friendly.
 */
export function AnimatedMark({
  size = 132,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    // A native <img> (not next/image) keeps the animated SVG static-export
    // friendly and unproxied.
    <img
      src="/logo-animated.svg"
      alt=""
      width={size}
      height={size}
      className={cn('block', className)}
      style={{ width: size, height: size }}
    />
  );
}
