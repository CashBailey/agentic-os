import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'accent';

const tones: Record<BadgeTone, string> = {
  neutral: 'text-fg-muted bg-bg-subtle border-border',
  success: 'text-success bg-success/10 border-success/30',
  warning: 'text-warning bg-warning/10 border-warning/30',
  danger: 'text-danger bg-danger/10 border-danger/30',
  accent: 'text-accent bg-accent/10 border-accent/30',
};

/** Smaller, label-style sibling of Pill (no dot, fits in tables). */
export function Badge({
  children,
  tone = 'neutral',
  className,
}: {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-1.5 h-5 text-2xs font-mono rounded-xs border tabular-nums',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
