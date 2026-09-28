import type { ReactNode } from 'react';
import { Card, CardBody } from './Card';
import { describeError, isNetworkError } from '../../lib/api';
import { Button } from './Button';

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-fg-subtle font-mono">
      <span className="inline-block h-3 w-3 rounded-full border-2 border-border border-t-accent animate-spin" />
      {label ?? 'loading…'}
    </div>
  );
}

export function LoadingCard({ label }: { label?: string }) {
  return (
    <Card>
      <CardBody className="py-6 flex items-center justify-center">
        <Spinner label={label} />
      </CardBody>
    </Card>
  );
}

export function ErrorCard({
  error,
  onRetry,
  title = 'Failed to load',
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <Card className="border-danger/40">
      <CardBody className="py-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-danger">{title}</div>
            <div className="text-xs text-fg-muted mt-1 font-mono break-words">
              {describeError(error)}
            </div>
          </div>
          {onRetry ? (
            <Button size="sm" variant="secondary" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      </CardBody>
    </Card>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <Card>
      <CardBody className="py-10 text-center">
        <div className="text-sm font-semibold text-fg">{title}</div>
        {description ? (
          <div className="text-xs text-fg-muted mt-1 max-w-md mx-auto">{description}</div>
        ) : null}
        {action ? <div className="mt-3">{action}</div> : null}
      </CardBody>
    </Card>
  );
}

export function BackendOfflineBanner({ error }: { error: unknown }) {
  if (!isNetworkError(error)) return null;
  return (
    <div className="mx-6 mt-4 border border-danger/40 bg-danger/10 text-danger rounded-sm px-3 py-2 text-xs font-mono">
      Backend offline. Start with:{' '}
      <span className="text-fg">cd backend &amp;&amp; uvicorn app.main:app</span>
    </div>
  );
}
