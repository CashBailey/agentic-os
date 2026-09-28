import { useCallback, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Pill } from '../components/ui/Pill';
import { Table, TBody, TD, TH, THead, TR } from '../components/ui/Table';
import { AuditAPI, type AuditEvent } from '../lib/api';
import { useUIStore } from '../state/store';
import { useEventStream } from '../lib/useEventStream';
import {
  BackendOfflineBanner,
  EmptyState,
  ErrorCard,
  LoadingCard,
} from '../components/ui/State';

function PayloadCell({ payload }: { payload: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  const compact = JSON.stringify(payload);
  return (
    <div className="max-w-xl">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-2xs text-accent hover:underline font-mono"
      >
        {open ? 'hide' : 'show'} ({compact.length}b)
      </button>
      {open ? (
        <pre className="mt-1 bg-bg-subtle border border-border rounded-xs p-2 text-2xs font-mono text-fg-muted overflow-auto max-h-64 whitespace-pre-wrap">
          {JSON.stringify(payload, null, 2)}
        </pre>
      ) : (
        <span className="ml-2 text-2xs text-fg-subtle truncate font-mono">{compact}</span>
      )}
    </div>
  );
}

export function Audit() {
  const qc = useQueryClient();
  const slug = useUIStore((s) => s.currentProject);
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [live, setLive] = useState(true);

  const q = useQuery({
    queryKey: ['audit', cursor, slug],
    queryFn: () => AuditAPI.page({ cursor, project: slug || undefined }),
  });

  const sse = useEventStream({
    enabled: live,
    types: ['audit'],
    project: slug || undefined,
    onMessage: (msg) => {
      if (msg.type === 'audit') {
        qc.invalidateQueries({ queryKey: ['audit'] });
      }
    },
  });

  const next = useCallback(() => {
    if (q.data?.next_cursor) setCursor(q.data.next_cursor);
  }, [q.data]);

  const events = q.data?.items ?? [];

  return (
    <div className="flex flex-col">
      <PageHeader
        breadcrumbs={['audit']}
        title="Audit"
        description="Append-only event log. Cursor pagination + optional SSE live-tail."
        actions={
          <>
            <Pill tone={live && sse.status === 'open' ? 'success' : 'neutral'} dot>
              {live ? `sse ${sse.status}` : 'sse off'}
            </Pill>
            <Button variant="secondary" size="sm" onClick={() => setLive((v) => !v)}>
              {live ? 'Pause live-tail' : 'Resume live-tail'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setCursor(undefined);
                q.refetch();
              }}
            >
              Refresh
            </Button>
          </>
        }
      />

      <BackendOfflineBanner error={q.error} />

      <div className="p-6">
        <Card>
          <CardHeader title="Events" subtitle={`${events.length} on this page`} />
          <CardBody className="p-0">
            {q.isLoading ? (
              <div className="p-4">
                <LoadingCard />
              </div>
            ) : q.error ? (
              <div className="p-4">
                <ErrorCard error={q.error} onRetry={() => q.refetch()} />
              </div>
            ) : events.length === 0 ? (
              <EmptyState
                title="No events"
                description="Audit log is empty for the current filter."
              />
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>ts</TH>
                    <TH>event</TH>
                    <TH>actor</TH>
                    <TH>payload</TH>
                  </TR>
                </THead>
                <TBody>
                  {events.map((e: AuditEvent) => {
                    const ts = e.ts ?? e.created_at ?? '';
                    return (
                      <TR key={e.id}>
                        <TD className="text-fg-subtle tabular-nums text-2xs">
                          {ts ? new Date(ts).toLocaleString() : '—'}
                        </TD>
                        <TD>
                          <Badge tone="accent">{e.event_type}</Badge>
                        </TD>
                        <TD className="font-mono text-2xs">{e.actor ?? '—'}</TD>
                        <TD>
                          <PayloadCell payload={e.payload ?? {}} />
                        </TD>
                      </TR>
                    );
                  })}
                </TBody>
              </Table>
            )}
          </CardBody>
        </Card>

        <div className="flex justify-between items-center mt-3">
          <div className="text-2xs text-fg-subtle font-mono">
            {cursor ? `cursor: ${cursor}` : 'first page'}
          </div>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              disabled={!cursor}
              onClick={() => setCursor(undefined)}
            >
              First page
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={!q.data?.next_cursor}
              onClick={next}
            >
              Next page →
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
