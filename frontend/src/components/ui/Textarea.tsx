import { forwardRef, type TextareaHTMLAttributes } from 'react';
import { cn } from '../../lib/cn';

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, ...rest },
  ref,
) {
  return (
    <textarea
      ref={ref}
      className={cn(
        'w-full bg-bg-subtle border border-border text-fg rounded-sm',
        'font-mono text-xs leading-relaxed p-2',
        'placeholder:text-fg-subtle',
        'hover:border-border-strong focus:border-accent focus:outline-none',
        'disabled:opacity-50 disabled:cursor-not-allowed transition-colors',
        'resize-y min-h-[8rem]',
        className,
      )}
      {...rest}
    />
  );
});
