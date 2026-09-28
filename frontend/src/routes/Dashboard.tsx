import { useQuery } from '@tanstack/react-query';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { PageHeader } from '../components/PageHeader';
import { Pill, type PillTone } from '../components/ui/Pill';
import { Button } from '../components/ui/Button';
import {
  AuthAPI,
  ApprovalsAPI,
  SessionsAPI,
  fetchReadiness,
  type AuthStatusEntry,
} from '../lib/api';
import { useUIStore } from '../state/store';
import {
  BackendOfflineBanner,
  EmptyState,
  ErrorCard,
  LoadingCard,
} from '../components/ui/State';

function authStateTone(state: string): PillTone {
  const s = state.toLowerCase();
  if (s === 'logged_in' || s === 'ready') return 'success';
  if (s === 'installed') return 'accent';
  if (s === 'logged_out' || s === 'not_installed') return 'warning';
  return 'neutral';
}

function CliCard({ entry }: { entry: AuthStatusEntry }) {
  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold text-fg font-mono">{entry.cli}</div>
          <Pill tone={authStateTone(entry.state)} dot>
            {entry.state}
          </Pill>
        </div>
        <div className="mt-2 text-2xs uppercase tracking-wide text-fg-subtle">run</div>
        <code className="mt-1 block bg-bg-subtle border border-border rounded-xs px-2 py-1.5 text-xs font-mono text-fg overflow-x-auto">
          {entry.recommended_command || '—'}
        </code>
        {entry.warnings && entry.warnings.length > 0 ? (
          <ul className="mt-2 text-2xs text-warning font-mono space-y-0.5">
            {entry.warnings.map((w, i) => (
              <li key={i}>! {w}</li>
            ))}
          </ul>
        ) : null}
      </CardBody>
    </Card>
  );
}

export function Dashboard() {
  const slug = useUIStore((s) => s.currentProject);

  const readiness = useQuery({
    queryKey: ['readiness'],
    queryFn: fetchReadiness,
    refetchInterval: 10_000,
  });
  const auth = useQuery({ queryKey: ['auth-status'], queryFn: AuthAPI.status });
  const approvals = useQuery({
    queryKey: ['approvals', 'pending'],
    queryFn: () => ApprovalsAPI.list('pending'),
    refetchInterval: 15_000,
  });
  const sessions = useQuery({
    queryKey: ['sessions', slug],
    queryFn: () => SessionsAPI.list(slug, 5),
    enabled: !!slug,
  });

  const readinessTone: PillTone =
    readiness.data === 'ok' ? 'success' : readiness.data === 'down' ? 'danger' : 'warning';

  const networkErr = auth.error ?? approvals.error ?? sessions.error ?? null;

  return (
    <div className="flex flex-col">
      <PageHeader
        breadcrumbs={[slug || 'no-project']}
        title="Dashboard"
        description="Operational overview of the Agentic OS control plane."
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              auth.refetch();
              approvals.refetch();
              sessions.refetch();
              readiness.refetch();
            }}
          >
            Refresh
          </Button>
        }
      />

      <BackendOfflineBanner error={networkErr} />

      <div className="p-6 grid gap-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card>
            <CardBody className="py-3">
              <div className="text-2xs uppercase tracking-wide text-fg-subtle">API health</div>
              <div className="mt-1.5 flex items-baseline gap-2">
                <span className="font-mono text-2xl font-semibold text-fg tabular-nums">
                  {readiness.data ?? '…'}
                </span>
                <Pill tone={readinessTone}>live</Pill>
              </div>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="py-3">
              <div className="text-2xs uppercase tracking-wide text-fg-subtle">
                Pending approvals
              </div>
              <div className="mt-1.5 flex items-baseline gap-2">
                <span className="font-mono text-2xl font-semibold text-fg tabular-nums">
                  {approvals.isLoading ? '…' : (approvals.data?.length ?? 0)}
                </span>
                {approvals.data && approvals.data.length > 0 ? (
                  <Pill tone="warning">action</Pill>
                ) : (
                  <Pill tone="neutral">clear</Pill>
                )}
              </div>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="py-3">
              <div className="text-2xs uppercase tracking-wide text-fg-subtle">
                Recent sessions
              </div>
              <div className="mt-1.5 flex items-baseline gap-2">
                <span className="font-mono text-2xl font-semibold text-fg tabular-nums">
                  {sessions.isLoading ? '…' : (sessions.data?.length ?? 0)}
                </span>
                <Pill tone="neutral">last 5</Pill>
              </div>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="py-3">
              <div className="text-2xs uppercase tracking-wide text-fg-subtle">Project</div>
              <div className="mt-1.5 flex items-baseline gap-2">
                <span className="font-mono text-lg font-semibold text-fg truncate">
                  {slug || '—'}
                </span>
              </div>
            </CardBody>
          </Card>
        </div>

        <div>
          <div className="text-2xs uppercase tracking-wide text-fg-subtle mb-2 font-mono">
            CLI auth status
          </div>
          {auth.isLoading ? (
            <LoadingCard />
          ) : auth.error ? (
            <ErrorCard error={auth.error} onRetry={() => auth.refetch()} />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {(auth.data?.clis ?? []).map((c) => (
                <CliCard key={c.cli} entry={c} />
              ))}
            </div>
          )}
        </div>

        <Card>
          <CardHeader title="Recent sessions" subtitle="Last 5 closed sessions" />
          <CardBody className="p-0">
            {sessions.isLoading ? (
              <div className="p-4">
                <LoadingCard />
              </div>
            ) : sessions.error ? (
              <div className="p-4">
                <ErrorCard error={sessions.error} onRetry={() => sessions.refetch()} />
              </div>
            ) : (sessions.data ?? []).length === 0 ? (
              <EmptyState
                title="No sessions yet"
                description="Run a session via your CLI; summaries land here."
              />
            ) : (
              <ul className="font-mono text-xs divide-y divide-border">
                {sessions.data!.map((s) => (
                  <li key={s.id} className="px-4 py-2 flex items-center gap-3">
                    <span className="text-fg-subtle tabular-nums">
                      {new Date(s.started_at).toLocaleString()}
                    </span>
                    <span className="text-accent">session#{s.id}</span>
                    <span className="text-fg-muted truncate">{s.summary || '—'}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
