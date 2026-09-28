import { cn } from '../../lib/cn';

export interface TabItem<T extends string = string> {
  id: T;
  label: string;
}

export function Tabs<T extends string>({
  items,
  value,
  onChange,
  className,
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (id: T) => void;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center gap-0 border-b border-border', className)} role="tablist">
      {items.map((it) => {
        const active = it.id === value;
        return (
          <button
            key={it.id}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(it.id)}
            className={cn(
              'relative px-3 h-9 text-xs font-medium transition-colors -mb-px border-b-2',
              active
                ? 'text-fg border-accent'
                : 'text-fg-muted border-transparent hover:text-fg',
            )}
          >
            {it.label}
          </button>
        );
      })}
    </div>
  );
}
