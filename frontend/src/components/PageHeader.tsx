import type { ReactNode } from 'react';

export function PageHeader({
  title,
  description,
  actions,
  breadcrumbs,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  breadcrumbs?: string[];
}) {
  return (
    <div className="px-6 pt-5 pb-4 border-b border-border bg-bg">
      {breadcrumbs && breadcrumbs.length > 0 ? (
        <div className="text-2xs font-mono text-fg-subtle mb-1.5 flex items-center gap-1.5">
          {breadcrumbs.map((b, i) => (
            <span key={i} className="flex items-center gap-1.5">
              {i > 0 ? <span className="text-fg-subtle/50">/</span> : null}
              {b}
            </span>
          ))}
        </div>
      ) : null}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold tracking-tight text-fg">{title}</h1>
          {description ? (
            <p className="text-xs text-fg-muted mt-1 max-w-2xl">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
    </div>
  );
}
