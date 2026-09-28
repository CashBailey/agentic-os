import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Textarea } from '../components/ui/Textarea';
import { Badge } from '../components/ui/Badge';
import { PoliciesAPI, type PolicyFile, type PolicySimulationResult } from '../lib/api';
import { useUIStore } from '../state/store';
import {
  BackendOfflineBanner,
  EmptyState,
  ErrorCard,
  LoadingCard,
} from '../components/ui/State';

function decisionTone(d: string) {
  if (d === 'allow') return 'success' as const;
  if (d === 'deny') return 'danger' as const;
  if (d === 'prompt') return 'warning' as const;
  return 'neutral' as const;
}

export function Policies() {
  const slug = useUIStore((s) => s.currentProject);
  const pushNotification = useUIStore((s) => s.pushNotification);
  const qc = useQueryClient();

  const list = useQuery({
    queryKey: ['policies', slug],
    queryFn: () => PoliciesAPI.list(slug),
    enabled: !!slug,
  });

  const [selectedKind, setSelectedKind] = useState<string | null>(null);
  const [draft, setDraft] = useState('');

  const selected: PolicyFile | undefined = useMemo(
    () => list.data?.find((p) => p.kind === selectedKind),
    [list.data, selectedKind],
  );

  useEffect(() => {
    if (selectedKind == null && list.data && list.data.length > 0) {
      setSelectedKind(list.data[0].kind);
    }
  }, [list.data, selectedKind]);

  useEffect(() => {
    setDraft(selected?.content ?? '');
  }, [selected?.kind, selected?.content]);

  const save = useMutation({
    mutationFn: () => PoliciesAPI.update(slug, selectedKind!, draft),
    onSuccess: () => {
      pushNotification({ kind: 'success', title: 'Policy saved' });
      qc.invalidateQueries({ queryKey: ['policies', slug] });
    },
    onError: (e) =>
      pushNotification({ kind: 'error', title: 'Save failed', detail: String(e) }),
  });

  // Simulator
  const [simTool, setSimTool] = useState('bash');
  const [simAction, setSimAction] = useState('shell');
  const [simArgs, setSimArgs] = useState('{"args": ["git", "status"]}');
  const [simResult, setSimResult] = useState<PolicySimulationResult | null>(null);

  const simulate = useMutation({
    mutationFn: () => {
      let args: Record<string, unknown> = {};
      try {
        args = JSON.parse(simArgs);
      } catch {
        throw new Error('args must be valid JSON');
      }
      return PoliciesAPI.simulate(slug, { tool: simTool, action: simAction, args });
    },
    onSuccess: (r) => setSimResult(r),
    onError: (e) => {
      setSimResult(null);
      pushNotification({ kind: 'error', title: 'Simulate failed', detail: String(e) });
    },
  });

  const dirty = draft !== (selected?.content ?? '');

  return (
    <div className="flex flex-col">
      <PageHeader
        breadcrumbs={[slug || 'no-project', 'policies']}
        title="Policies"
        description="Edit policy YAML and simulate decisions against the rule engine."
        actions={
          <Button
            variant="primary"
            size="sm"
            disabled={!dirty || !selected || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? 'Saving…' : 'Save'}
          </Button>
        }
      />

      <BackendOfflineBanner error={list.error} />

      <div className="p-6 grid gap-4 grid-cols-1 lg:grid-cols-[16rem_1fr]">
        <Card>
          <CardHeader title="Policy files" subtitle={`${list.data?.length ?? 0} files`} />
          <CardBody className="p-0">
            {list.isLoading ? (
              <div className="p-3">
                <LoadingCard />
              </div>
            ) : list.error ? (
              <div className="p-3">
                <ErrorCard error={list.error} onRetry={() => list.refetch()} />
              </div>
            ) : (list.data ?? []).length === 0 ? (
              <EmptyState title="No policy files" />
            ) : (
              <ul className="divide-y divide-border">
                {list.data!.map((p) => (
                  <li key={p.kind}>
                    <button
                      onClick={() => setSelectedKind(p.kind)}
                      className={
                        'w-full text-left px-3 py-2 text-xs font-mono flex items-center gap-2 hover:bg-bg-subtle ' +
                        (selectedKind === p.kind ? 'bg-accent/10 text-fg' : 'text-fg-muted')
                      }
                    >
                      <Badge tone={p.parse_ok === false ? 'danger' : 'accent'}>{p.kind}</Badge>
                      <span className="truncate flex-1">{p.path.split('/').pop()}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <div className="flex flex-col gap-4 min-w-0">
          <Card>
            <CardHeader
              title={selected?.path ?? 'No policy selected'}
              subtitle={selected ? `kind=${selected.kind}` : undefined}
              actions={
                dirty ? (
                  <Badge tone="warning">modified</Badge>
                ) : selected?.parse_ok === false ? (
                  <Badge tone="danger">parse error</Badge>
                ) : null
              }
            />
            <CardBody>
              {selected ? (
                <>
                  <Textarea
                    aria-label="Policy YAML editor"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    rows={18}
                    spellCheck={false}
                  />
                  {selected.parse_error ? (
                    <div className="mt-2 text-2xs font-mono text-danger">
                      {selected.parse_error}
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="text-xs text-fg-subtle">Select a policy file to edit.</div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Simulate decision" subtitle="POST /policies/simulate" />
            <CardBody>
              <div className="grid grid-cols-1 md:grid-cols-[8rem_8rem_1fr_auto] gap-2 items-end">
                <div>
                  <label className="text-2xs uppercase tracking-wide text-fg-subtle">
                    tool
                  </label>
                  <Input aria-label="Simulate: tool" value={simTool} onChange={(e) => setSimTool(e.target.value)} />
                </div>
                <div>
                  <label className="text-2xs uppercase tracking-wide text-fg-subtle">
                    action
                  </label>
                  <Input aria-label="Simulate: action" value={simAction} onChange={(e) => setSimAction(e.target.value)} />
                </div>
                <div>
                  <label className="text-2xs uppercase tracking-wide text-fg-subtle">
                    args (JSON)
                  </label>
                  <Input aria-label="Simulate: args (JSON)" value={simArgs} onChange={(e) => setSimArgs(e.target.value)} />
                </div>
                <Button
                  variant="secondary"
                  size="md"
                  onClick={() => simulate.mutate()}
                  disabled={simulate.isPending}
                >
                  {simulate.isPending ? 'Simulating…' : 'Simulate'}
                </Button>
              </div>

              {simResult ? (
                <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="border border-border rounded-sm p-3">
                    <div className="text-2xs uppercase tracking-wide text-fg-subtle">
                      decision
                    </div>
                    <div className="mt-1">
                      <Badge tone={decisionTone(simResult.decision)}>
                        {simResult.decision}
                      </Badge>
                    </div>
                  </div>
                  <div className="border border-border rounded-sm p-3">
                    <div className="text-2xs uppercase tracking-wide text-fg-subtle">
                      matched_rule
                    </div>
                    <div className="mt-1 font-mono text-xs text-fg break-words">
                      {simResult.matched_rule ?? '(none)'}
                    </div>
                    {simResult.reason ? (
                      <div className="mt-1 font-mono text-2xs text-fg-muted">
                        {simResult.reason}
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
