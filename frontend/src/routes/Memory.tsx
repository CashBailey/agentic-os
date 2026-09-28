import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { Textarea } from '../components/ui/Textarea';
import { Table, TBody, TD, TH, THead, TR } from '../components/ui/Table';
import { MemoryAPI, type MemoryItem, type SemanticHit } from '../lib/api';
import { useUIStore } from '../state/store';
import {
  BackendOfflineBanner,
  EmptyState,
  ErrorCard,
  LoadingCard,
  Spinner,
} from '../components/ui/State';

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function Memory() {
  const slug = useUIStore((s) => s.currentProject);
  const pushNotification = useUIStore((s) => s.pushNotification);
  const qc = useQueryClient();

  const [q, setQ] = useState('');
  const [kind, setKind] = useState('');
  const debounced = useDebounced(q);

  const items = useQuery({
    queryKey: ['memory', slug, debounced, kind],
    queryFn: () =>
      MemoryAPI.list(slug, {
        q: debounced || undefined,
        kind: kind || undefined,
      }),
    enabled: !!slug,
  });

  const [semantic, setSemantic] = useState<SemanticHit[] | null>(null);
  const semanticMut = useMutation({
    mutationFn: () => MemoryAPI.semantic(slug, { query: q, top_k: 10 }),
    onSuccess: (hits) => setSemantic(hits),
    onError: (e) =>
      pushNotification({ kind: 'error', title: 'Semantic search failed', detail: String(e) }),
  });

  const allKinds = useMemo(() => {
    const s = new Set<string>();
    for (const m of items.data ?? []) s.add(m.kind);
    return Array.from(s).sort();
  }, [items.data]);

  const [showCreate, setShowCreate] = useState(false);
  const [draft, setDraft] = useState<{ kind: string; title: string; body: string }>({
    kind: 'note',
    title: '',
    body: '',
  });
  const create = useMutation({
    mutationFn: () => MemoryAPI.create(slug, draft),
    onSuccess: () => {
      pushNotification({ kind: 'success', title: 'Memory created' });
      setShowCreate(false);
      setDraft({ kind: 'note', title: '', body: '' });
      qc.invalidateQueries({ queryKey: ['memory', slug] });
    },
    onError: (e) =>
      pushNotification({ kind: 'error', title: 'Create failed', detail: String(e) }),
  });

  return (
    <div className="flex flex-col">
      <PageHeader
        breadcrumbs={[slug || 'no-project', 'memory']}
        title="Memory"
        description="Browse and search memory items. FTS by default; semantic search via pgvector."
        actions={
          <>
            <Button variant="ghost" size="sm" onClick={() => items.refetch()}>
              Refresh
            </Button>
            <Button variant="primary" size="sm" onClick={() => setShowCreate(true)}>
              New item
            </Button>
          </>
        }
      />

      <BackendOfflineBanner error={items.error} />

      <div className="p-6 grid gap-4">
        <Card>
          <CardBody>
            <div className="grid grid-cols-1 md:grid-cols-[1fr_12rem_auto] gap-2 items-center">
              <Input
                placeholder="Search (FTS) — title/body…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
              <select
                aria-label="Filter by memory kind"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
                className="bg-bg-subtle border border-border text-xs text-fg h-8 px-2 rounded-sm font-mono hover:border-border-strong focus:border-accent"
              >
                <option value="">all kinds</option>
                {allKinds.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
              <Button
                variant="secondary"
                size="md"
                disabled={!q || semanticMut.isPending}
                onClick={() => semanticMut.mutate()}
              >
                {semanticMut.isPending ? <Spinner /> : 'Semantic search'}
              </Button>
            </div>
          </CardBody>
        </Card>

        {semantic ? (
          <Card>
            <CardHeader
              title={`Semantic results (${semantic.length})`}
              actions={
                <Button variant="ghost" size="sm" onClick={() => setSemantic(null)}>
                  Clear
                </Button>
              }
            />
            <CardBody className="p-0">
              {semantic.length === 0 ? (
                <EmptyState title="No semantic matches" />
              ) : (
                <Table>
                  <THead>
                    <TR>
                      <TH>score</TH>
                      <TH>kind</TH>
                      <TH>title</TH>
                      <TH>body</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {semantic.map((h) => (
                      <TR key={h.id}>
                        <TD className="text-accent">{h.score.toFixed(3)}</TD>
                        <TD>
                          <Badge>{h.kind}</Badge>
                        </TD>
                        <TD>{h.title}</TD>
                        <TD className="text-fg-muted truncate max-w-md">{h.body}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              )}
            </CardBody>
          </Card>
        ) : null}

        <Card>
          <CardHeader
            title="Memory items"
            subtitle={items.data ? `${items.data.length} matches` : '…'}
          />
          <CardBody className="p-0">
            {items.isLoading ? (
              <div className="p-4">
                <LoadingCard />
              </div>
            ) : items.error ? (
              <div className="p-4">
                <ErrorCard error={items.error} onRetry={() => items.refetch()} />
              </div>
            ) : (items.data ?? []).length === 0 ? (
              <EmptyState title="No memory items" description="Adjust filters or add one." />
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>kind</TH>
                    <TH>title</TH>
                    <TH>body</TH>
                    <TH>tags</TH>
                    <TH>occurred_at</TH>
                  </TR>
                </THead>
                <TBody>
                  {items.data!.map((m: MemoryItem) => (
                    <TR key={m.id}>
                      <TD>
                        <Badge tone="accent">{m.kind}</Badge>
                      </TD>
                      <TD>{m.title}</TD>
                      <TD className="text-fg-muted truncate max-w-md">{m.body}</TD>
                      <TD className="text-fg-subtle">{(m.tags ?? []).join(', ')}</TD>
                      <TD className="text-fg-subtle tabular-nums">
                        {new Date(m.occurred_at).toLocaleString()}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </CardBody>
        </Card>
      </div>

      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title="New memory item"
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={!draft.title || create.isPending}
              onClick={() => create.mutate()}
            >
              {create.isPending ? 'Creating…' : 'Create'}
            </Button>
          </>
        }
      >
        <div className="grid gap-2">
          <label className="text-2xs uppercase tracking-wide text-fg-subtle">kind</label>
          <Input value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value })} />
          <label className="text-2xs uppercase tracking-wide text-fg-subtle">title</label>
          <Input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
          <label className="text-2xs uppercase tracking-wide text-fg-subtle">body</label>
          <Textarea
            value={draft.body}
            onChange={(e) => setDraft({ ...draft, body: e.target.value })}
            rows={8}
          />
        </div>
      </Modal>
    </div>
  );
}
