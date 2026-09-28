import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

export type PillTone = 'neutral' | 'success' | 'warning' | 'danger' | 'accent';

const tones: Record<PillTone, string> = {
  neutral: 'text-fg-muted bg-bg-subtle border-border',
  success: 'text-success bg-success/10 border-success/30',
  warning: 'text-warning bg-warning/10 border-warning/30',
  danger: 'text-danger bg-danger/10 border-danger/30',
  accent: 'text-accent bg-accent/10 border-accent/30',
};

export function Pill({
  children,
  tone = 'neutral',
  dot,
  className,
}: {
  children: ReactNode;
  tone?: PillTone;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 h-6 text-2xs font-medium rounded-sm border tabular-nums',
        tones[tone],
        className,
      )}
    >
      {dot ? (
        <span
          className={cn(
            'inline-block h-1.5 w-1.5 rounded-full',
            tone === 'success' && 'bg-success',
            tone === 'warning' && 'bg-warning',
            tone === 'danger' && 'bg-danger',
            tone === 'accent' && 'bg-accent',
            tone === 'neutral' && 'bg-fg-muted',
          )}
        />
      ) : null}
      {children}
    </span>
  );
}
