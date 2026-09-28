import { useEffect } from 'react';
import { useUIStore } from '../state/store';
import { cn } from '../lib/cn';

const toneClass = {
  info: 'border-accent/30 text-accent bg-accent/10',
  success: 'border-success/30 text-success bg-success/10',
  warning: 'border-warning/30 text-warning bg-warning/10',
  error: 'border-danger/30 text-danger bg-danger/10',
};

export function Toaster() {
  const notifications = useUIStore((s) => s.notifications);
  const dismiss = useUIStore((s) => s.dismissNotification);

  // Auto-dismiss after 6s.
  useEffect(() => {
    const timers = notifications.map((n) =>
      setTimeout(() => dismiss(n.id), 6_000 - (Date.now() - n.ts)),
    );
    return () => timers.forEach(clearTimeout);
  }, [notifications, dismiss]);

  if (notifications.length === 0) return null;
  return (
    <div className="fixed bottom-3 right-3 z-50 flex flex-col gap-2 w-80 max-w-[90vw]">
      {notifications.slice(0, 5).map((n) => (
        <div
          key={n.id}
          className={cn(
            'border rounded-sm px-3 py-2 text-xs shadow-lg backdrop-blur',
            toneClass[n.kind],
          )}
        >
          <div className="flex items-start gap-2">
            <div className="flex-1 min-w-0">
              <div className="font-semibold">{n.title}</div>
              {n.detail ? (
                <div className="font-mono mt-0.5 text-fg-muted break-words">{n.detail}</div>
              ) : null}
            </div>
            <button
              onClick={() => dismiss(n.id)}
              className="text-fg-subtle hover:text-fg text-base leading-none"
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
