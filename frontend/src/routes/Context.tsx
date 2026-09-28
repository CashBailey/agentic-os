import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Textarea } from '../components/ui/Textarea';
import { ContextAPI, type ContextDocument } from '../lib/api';
import { useUIStore } from '../state/store';
import {
  BackendOfflineBanner,
  EmptyState,
  ErrorCard,
  LoadingCard,
} from '../components/ui/State';

export function Context() {
  const slug = useUIStore((s) => s.currentProject);
  const pushNotification = useUIStore((s) => s.pushNotification);
  const qc = useQueryClient();

  const docs = useQuery({
    queryKey: ['context', slug],
    queryFn: () => ContextAPI.list(slug),
    enabled: !!slug,
  });

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<string>('');

  const selected = useMemo<ContextDocument | undefined>(
    () => docs.data?.find((d) => d.id === selectedId),
    [docs.data, selectedId],
  );

  useEffect(() => {
    if (selectedId == null && docs.data && docs.data.length > 0) {
      setSelectedId(docs.data[0].id);
    }
  }, [docs.data, selectedId]);

  useEffect(() => {
    setDraft(selected?.content ?? '');
  }, [selected?.id, selected?.content]);

  const grouped = useMemo(() => {
    const out: Record<string, ContextDocument[]> = {};
    for (const d of docs.data ?? []) {
      const k = d.scope || 'unknown';
      (out[k] ||= []).push(d);
    }
    return out;
  }, [docs.data]);

  const save = useMutation({
    mutationFn: () => ContextAPI.update(slug, selectedId!, draft),
    onSuccess: () => {
      pushNotification({ kind: 'success', title: 'Saved', detail: selected?.path ?? '' });
      qc.invalidateQueries({ queryKey: ['context', slug] });
    },
    onError: (err) =>
      pushNotification({ kind: 'error', title: 'Save failed', detail: String(err) }),
  });

  const dirty = draft !== (selected?.content ?? '');

  return (
    <div className="flex flex-col">
      <PageHeader
        breadcrumbs={[slug || 'no-project', 'context']}
        title="Context"
        description="Canonical context documents handed to agents. Edits propagate via PUT."
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

      <BackendOfflineBanner error={docs.error} />

      <div className="p-6 grid gap-4 grid-cols-1 lg:grid-cols-[20rem_1fr]">
        <Card>
          <CardHeader
            title="Documents"
            subtitle={docs.data ? `${docs.data.length} total` : '…'}
          />
          <CardBody className="p-0">
            {docs.isLoading ? (
              <div className="p-3">
                <LoadingCard />
              </div>
            ) : docs.error ? (
              <div className="p-3">
                <ErrorCard error={docs.error} onRetry={() => docs.refetch()} />
              </div>
            ) : (docs.data ?? []).length === 0 ? (
              <EmptyState
                title="No context documents"
                description="Add docs under agent-os/ for this project."
              />
            ) : (
              <div className="divide-y divide-border">
                {Object.entries(grouped).map(([scope, items]) => (
                  <div key={scope}>
                    <div className="px-3 py-1.5 text-2xs uppercase tracking-wide text-fg-subtle bg-bg-subtle/50 font-mono">
                      {scope}
                    </div>
                    <ul>
                      {items.map((d) => (
                        <li key={d.id}>
                          <button
                            onClick={() => setSelectedId(d.id)}
                            className={
                              'w-full text-left px-3 py-2 text-xs font-mono flex items-center gap-2 hover:bg-bg-subtle ' +
                              (selectedId === d.id
                                ? 'bg-accent/10 text-fg'
                                : 'text-fg-muted')
                            }
                          >
                            <Badge tone="neutral">{d.kind}</Badge>
                            <span className="truncate flex-1">{d.path || `doc#${d.id}`}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title={selected?.path ?? 'No selection'}
            subtitle={
              selected
                ? `scope=${selected.scope} kind=${selected.kind}${selected.hash ? ` hash=${selected.hash.slice(0, 8)}` : ''}`
                : 'Pick a document on the left'
            }
            actions={dirty ? <Badge tone="warning">modified</Badge> : null}
          />
          <CardBody>
            {selected ? (
              <Textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={24}
                spellCheck={false}
              />
            ) : (
              <div className="text-xs text-fg-subtle">Select a document to edit.</div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
