import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge, type BadgeTone } from '../components/ui/Badge';
import { Tabs } from '../components/ui/Tabs';
import { Pill } from '../components/ui/Pill';
import { Table, TBody, TD, TH, THead, TR } from '../components/ui/Table';
import { ApprovalsAPI, type Approval } from '../lib/api';
import { useUIStore } from '../state/store';
import { useEventStream } from '../lib/useEventStream';
import {
  BackendOfflineBanner,
  EmptyState,
  ErrorCard,
  LoadingCard,
} from '../components/ui/State';

type StatusFilter = 'pending' | 'approved' | 'denied' | 'expired' | 'all';

function statusTone(s: string): BadgeTone {
  if (s === 'approved' || s === 'released' || s === 'executed') return 'success';
  if (s === 'denied') return 'danger';
  if (s === 'pending') return 'warning';
  if (s === 'expired') return 'neutral';
  return 'accent';
}

function riskTone(r: string): BadgeTone {
  if (r === 'high') return 'danger';
  if (r === 'medium') return 'warning';
  return 'neutral';
}

export function Approvals() {
  const qc = useQueryClient();
  const slug = useUIStore((s) => s.currentProject);
  const pushNotification = useUIStore((s) => s.pushNotification);

  const [filter, setFilter] = useState<StatusFilter>('pending');

  const q = useQuery({
    queryKey: ['approvals', filter],
    queryFn: () => ApprovalsAPI.list(filter === 'all' ? undefined : filter),
    refetchInterval: 15_000,
  });

  // SSE — invalidate on approval.pending, toast new pending items.
  const sse = useEventStream({
    types: ['approval.pending', 'audit'],
    project: slug || undefined,
    onMessage: (msg) => {
      if (msg.type === 'approval.pending') {
        const d = msg.data as { id?: number; tool?: string; action?: string } | undefined;
        pushNotification({
          kind: 'warning',
          title: 'New approval requested',
          detail: d ? `#${d.id ?? '?'} ${d.tool ?? ''} ${d.action ?? ''}` : undefined,
        });
        qc.invalidateQueries({ queryKey: ['approvals'] });
      }
    },
  });

  const decide = useMutation({
    mutationFn: (args: { id: number; decision: 'approved' | 'denied' }) =>
      ApprovalsAPI.decide(args.id, { decision: args.decision }),
    onSuccess: (_a, vars) => {
      pushNotification({
        kind: vars.decision === 'approved' ? 'success' : 'info',
        title: `Approval ${vars.decision}`,
        detail: `#${vars.id}`,
      });
      qc.invalidateQueries({ queryKey: ['approvals'] });
    },
    onError: (e) =>
      pushNotification({ kind: 'error', title: 'Decide failed', detail: String(e) }),
  });

  return (
    <div className="flex flex-col">
      <PageHeader
        breadcrumbs={['approvals']}
        title="Approvals"
        description="Human-in-the-loop approval queue."
        actions={
          <Pill tone={sse.status === 'open' ? 'success' : 'neutral'} dot>
            sse {sse.status}
          </Pill>
        }
      />

      <BackendOfflineBanner error={q.error} />

      <div className="px-6 pt-4">
        <Tabs<StatusFilter>
          items={[
            { id: 'pending', label: 'Pending' },
            { id: 'approved', label: 'Approved' },
            { id: 'denied', label: 'Denied' },
            { id: 'expired', label: 'Expired' },
            { id: 'all', label: 'All' },
          ]}
          value={filter}
          onChange={setFilter}
        />
      </div>

      <div className="p-6">
        <Card>
          <CardHeader title={`Requests · ${filter}`} subtitle={`${q.data?.length ?? 0} rows`} />
          <CardBody className="p-0">
            {q.isLoading ? (
              <div className="p-4">
                <LoadingCard />
              </div>
            ) : q.error ? (
              <div className="p-4">
                <ErrorCard error={q.error} onRetry={() => q.refetch()} />
              </div>
            ) : (q.data ?? []).length === 0 ? (
              <EmptyState title="Empty" description={`No ${filter} approvals.`} />
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>id</TH>
                    <TH>tool</TH>
                    <TH>action</TH>
                    <TH>risk</TH>
                    <TH>status</TH>
                    <TH>input</TH>
                    <TH>expires</TH>
                    <TH>actions</TH>
                  </TR>
                </THead>
                <TBody>
                  {q.data!.map((a: Approval) => (
                    <TR key={a.id}>
                      <TD className="text-fg-subtle tabular-nums">#{a.id}</TD>
                      <TD>{a.tool}</TD>
                      <TD>{a.action}</TD>
                      <TD>
                        <Badge tone={riskTone(a.risk)}>{a.risk}</Badge>
                      </TD>
                      <TD>
                        <Badge tone={statusTone(a.status)}>{a.status}</Badge>
                      </TD>
                      <TD className="text-fg-muted truncate max-w-xs">
                        <code className="text-2xs">{JSON.stringify(a.raw_input)}</code>
                      </TD>
                      <TD className="text-fg-subtle tabular-nums text-2xs">
                        {a.expires_at ? new Date(a.expires_at).toLocaleString() : '—'}
                      </TD>
                      <TD>
                        {a.status === 'pending' ? (
                          <div className="flex gap-1">
                            <Button
                              size="sm"
                              variant="primary"
                              disabled={decide.isPending}
                              onClick={() =>
                                decide.mutate({ id: a.id, decision: 'approved' })
                              }
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="danger"
                              disabled={decide.isPending}
                              onClick={() =>
                                decide.mutate({ id: a.id, decision: 'denied' })
                              }
                            >
                              Deny
                            </Button>
                          </div>
                        ) : (
                          <span className="text-2xs text-fg-subtle">—</span>
                        )}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
