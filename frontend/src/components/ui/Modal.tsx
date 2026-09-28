import { useEffect, type ReactNode } from 'react';
import { cn } from '../../lib/cn';

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  width = 'md',
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: 'sm' | 'md' | 'lg' | 'xl';
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  const widths = {
    sm: 'max-w-md',
    md: 'max-w-xl',
    lg: 'max-w-3xl',
    xl: 'max-w-5xl',
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg/70 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className={cn(
          'w-full bg-bg-elevated border border-border rounded-md shadow-2xl flex flex-col max-h-[90vh]',
          widths[width],
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="text-sm font-semibold text-fg">{title}</div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-fg-subtle hover:text-fg text-lg leading-none px-1"
          >
            ×
          </button>
        </div>
        <div className="px-4 py-3 overflow-auto text-sm text-fg-muted flex-1">
          {children}
        </div>
        {footer ? (
          <div className="px-4 py-3 border-t border-border flex items-center justify-end gap-2">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
