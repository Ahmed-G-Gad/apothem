// SPDX-License-Identifier: MIT

import { cn } from '@/lib/utils';

/**
 * The animated apothem mark for the landing hero. Each SVG in public/ carries
 * its own internal CSS animation (the emerald apothem drawing from the center
 * to the top edge, then the five quiet apothems fanning out) and a
 * `prefers-reduced-motion` guard that holds the static mark for visitors who
 * ask for reduced motion. The two files are colour-tuned per surface, as
 * BrandMark's are: logo-animated-light.svg for the light theme and
 * logo-animated.svg (light strokes) for the dark theme. CSS theme classes swap
 * them so the hexagon outline stays legible on either surface without a
 * runtime theme read. Next/Image rasterizes SVGs and strips that internal
 * animation, so the mark is rendered as plain <img> elements to keep the
 * motion intact while staying static-export friendly.
 */
export function AnimatedMark({
  size = 132,
  className,
}: {
  size?: number;
  className?: string;
}) {
  const style = { width: size, height: size };
  return (
    <span
      className={cn('relative inline-block', className)}
      style={style}
    >
      {/* Native <img> elements (not next/image) keep the animated SVGs
          static-export friendly and unproxied. */}
      <img
        src="/logo-animated-light.svg"
        alt=""
        width={size}
        height={size}
        className="block dark:hidden"
        style={style}
      />
      <img
        src="/logo-animated.svg"
        alt=""
        width={size}
        height={size}
        className="hidden dark:block"
        style={style}
      />
    </span>
  );
}
