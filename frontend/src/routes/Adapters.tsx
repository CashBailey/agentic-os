import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { AdaptersAPI, type AdapterGeneration } from '../lib/api';
import { useUIStore } from '../state/store';
import {
  BackendOfflineBanner,
  EmptyState,
  ErrorCard,
  LoadingCard,
} from '../components/ui/State';

const CLIS = ['claude', 'gemini', 'codex'] as const;

function statusTone(s: string) {
  if (s === 'succeeded' || s === 'ready') return 'success' as const;
  if (s === 'running' || s === 'queued') return 'warning' as const;
  if (s === 'failed') return 'danger' as const;
  return 'neutral' as const;
}

export function Adapters() {
  const slug = useUIStore((s) => s.currentProject);
  const pushNotification = useUIStore((s) => s.pushNotification);
  const qc = useQueryClient();

  const gens = useQuery({
    queryKey: ['adapters', slug],
    queryFn: () => AdaptersAPI.list(slug),
    enabled: !!slug,
    refetchInterval: 10_000,
  });

  // Reduce to last generation per CLI.
  const lastByCli = useMemo(() => {
    const out: Record<string, AdapterGeneration | undefined> = {};
    for (const g of gens.data ?? []) {
      const prev = out[g.cli];
      if (!prev || new Date(g.created_at) > new Date(prev.created_at)) out[g.cli] = g;
    }
    return out;
  }, [gens.data]);

  const compile = useMutation({
    mutationFn: () => AdaptersAPI.compile(slug),
    onSuccess: (res) => {
      pushNotification({
        kind: 'info',
        title: 'Compile enqueued',
        detail: `task#${res.task_id}`,
      });
      setTimeout(() => qc.invalidateQueries({ queryKey: ['adapters', slug] }), 1500);
    },
    onError: (e) =>
      pushNotification({ kind: 'error', title: 'Compile failed', detail: String(e) }),
  });

  const [selectedCli, setSelectedCli] = useState<string | null>(null);
  const [target, setTarget] = useState('');

  const diff = useQuery({
    queryKey: ['adapter-diff', slug, selectedCli, target],
    queryFn: () => AdaptersAPI.diff(slug, selectedCli!, target),
    enabled: !!slug && !!selectedCli && target.length > 0,
  });

  return (
    <div className="flex flex-col">
      <PageHeader
        breadcrumbs={[slug || 'no-project', 'adapters']}
        title="Adapters"
        description="Per-CLI generated context bundles. Compile invokes the worker."
        actions={
          <Button
            variant="primary"
            size="sm"
            onClick={() => compile.mutate()}
            disabled={compile.isPending || !slug}
          >
            {compile.isPending ? 'Enqueuing…' : 'Compile now'}
          </Button>
        }
      />

      <BackendOfflineBanner error={gens.error} />

      <div className="p-6 grid gap-4">
        {gens.isLoading ? (
          <LoadingCard />
        ) : gens.error ? (
          <ErrorCard error={gens.error} onRetry={() => gens.refetch()} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {CLIS.map((cli) => {
              const g = lastByCli[cli];
              const isSelected = selectedCli === cli;
              return (
                <Card key={cli} className={isSelected ? 'border-accent' : undefined}>
                  <CardHeader
                    title={<span className="font-mono">{cli}</span>}
                    actions={
                      g ? (
                        <Badge tone={statusTone(g.status)}>{g.status}</Badge>
                      ) : (
                        <Badge>never</Badge>
                      )
                    }
                  />
                  <CardBody>
                    {g ? (
                      <dl className="text-2xs font-mono space-y-1">
                        <div className="flex justify-between gap-2">
                          <dt className="text-fg-subtle">hash</dt>
                          <dd className="text-fg truncate">{g.hash?.slice(0, 12)}</dd>
                        </div>
                        <div className="flex justify-between gap-2">
                          <dt className="text-fg-subtle">at</dt>
                          <dd className="text-fg">
                            {new Date(g.created_at).toLocaleString()}
                          </dd>
                        </div>
                        <div className="flex justify-between gap-2">
                          <dt className="text-fg-subtle">path</dt>
                          <dd className="text-fg truncate">{g.output_path}</dd>
                        </div>
                      </dl>
                    ) : (
                      <div className="text-xs text-fg-subtle">
                        No generation yet. Click <em>Compile now</em>.
                      </div>
                    )}
                    <div className="mt-3">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setSelectedCli(isSelected ? null : cli)}
                      >
                        {isSelected ? 'Hide diff' : 'Diff vs target'}
                      </Button>
                    </div>
                  </CardBody>
                </Card>
              );
            })}
          </div>
        )}

        {selectedCli ? (
          <Card>
            <CardHeader
              title={`Diff: ${selectedCli}`}
              subtitle="Compare generated output to a target path on disk"
            />
            <CardBody>
              <div className="flex gap-2 items-center mb-3">
                <Input
                  placeholder="/path/to/target/repo"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                />
                <Button variant="secondary" size="md" onClick={() => diff.refetch()}>
                  Diff
                </Button>
              </div>
              {!target ? (
                <div className="text-xs text-fg-subtle">Enter a target path to diff.</div>
              ) : diff.isLoading ? (
                <LoadingCard />
              ) : diff.error ? (
                <ErrorCard error={diff.error} onRetry={() => diff.refetch()} />
              ) : diff.data?.identical ? (
                <EmptyState title="Identical" description="Generated matches target byte-for-byte." />
              ) : (
                <pre className="bg-bg-subtle border border-border rounded-sm p-3 text-2xs font-mono text-fg-muted overflow-auto max-h-[40vh] whitespace-pre-wrap">
                  {diff.data?.diff || '(no diff payload)'}
                </pre>
              )}
            </CardBody>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
