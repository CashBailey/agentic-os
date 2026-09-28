import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '../../lib/cn';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  inputSize?: 'sm' | 'md';
}

const sizes = {
  sm: 'text-xs h-7 px-2',
  md: 'text-sm h-8 px-2.5',
};

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, inputSize = 'md', type = 'text', ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      type={type}
      className={cn(
        'w-full bg-bg-subtle border border-border text-fg rounded-sm font-mono',
        'placeholder:text-fg-subtle',
        'hover:border-border-strong focus:border-accent focus:outline-none',
        'disabled:opacity-50 disabled:cursor-not-allowed transition-colors',
        sizes[inputSize],
        className,
      )}
      {...rest}
    />
  );
});
