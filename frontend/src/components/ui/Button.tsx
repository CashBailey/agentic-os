import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '../../lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const base =
  'inline-flex items-center justify-center gap-1.5 font-medium rounded-sm border transition-colors ' +
  'disabled:opacity-50 disabled:cursor-not-allowed select-none';

const sizes: Record<Size, string> = {
  sm: 'text-xs px-2 h-7',
  md: 'text-sm px-3 h-8',
};

const variants: Record<Variant, string> = {
  primary:
    'bg-accent text-accent-fg border-accent hover:bg-accent/90 active:bg-accent/80',
  secondary:
    'bg-bg-elevated text-fg border-border hover:border-border-strong hover:bg-bg-subtle',
  ghost:
    'bg-transparent text-fg-muted border-transparent hover:bg-bg-subtle hover:text-fg',
  danger:
    'bg-transparent text-danger border-border hover:bg-danger/10 hover:border-danger',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = 'secondary', size = 'md', type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(base, sizes[size], variants[variant], className)}
      {...rest}
    />
  );
});
