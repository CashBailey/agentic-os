import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Tabs } from '../components/ui/Tabs';
import { Badge } from '../components/ui/Badge';
import { SkillsAPI, WorkflowsAPI } from '../lib/api';
import {
  BackendOfflineBanner,
  EmptyState,
  ErrorCard,
  LoadingCard,
} from '../components/ui/State';

type Tab = 'skills' | 'workflows';

export function Skills() {
  const [tab, setTab] = useState<Tab>('skills');

  const skills = useQuery({ queryKey: ['skills'], queryFn: SkillsAPI.list });
  const workflows = useQuery({ queryKey: ['workflows'], queryFn: WorkflowsAPI.list });

  const error = tab === 'skills' ? skills.error : workflows.error;

  return (
    <div className="flex flex-col">
      <PageHeader
        breadcrumbs={['skills']}
        title="Skills & Workflows"
        description="Registered skills and multi-step workflows discovered under agent-os/."
      />

      <BackendOfflineBanner error={error} />

      <div className="px-6 pt-4">
        <Tabs
          items={[
            { id: 'skills' as Tab, label: `Skills (${skills.data?.length ?? 0})` },
            { id: 'workflows' as Tab, label: `Workflows (${workflows.data?.length ?? 0})` },
          ]}
          value={tab}
          onChange={setTab}
        />
      </div>

      <div className="p-6 grid gap-3 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
        {tab === 'skills' ? (
          skills.isLoading ? (
            <LoadingCard />
          ) : skills.error ? (
            <ErrorCard error={skills.error} onRetry={() => skills.refetch()} />
          ) : (skills.data ?? []).length === 0 ? (
            <EmptyState title="No skills registered" />
          ) : (
            skills.data!.map((s) => (
              <Card key={s.name}>
                <CardHeader
                  title={<span className="font-mono">{s.name}</span>}
                  subtitle={s.path}
                  actions={<Badge tone="accent">skill</Badge>}
                />
                <CardBody>
                  {s.description ? (
                    <p className="text-xs text-fg-muted leading-relaxed">{s.description}</p>
                  ) : null}
                  {s.when_to_use && s.when_to_use.length > 0 ? (
                    <>
                      <div className="mt-2 text-2xs uppercase tracking-wide text-fg-subtle">
                        when_to_use
                      </div>
                      <ul className="mt-1 text-2xs font-mono text-fg-muted list-disc pl-4 space-y-0.5">
                        {s.when_to_use.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </>
                  ) : null}
                  {s.safety && s.safety.length > 0 ? (
                    <>
                      <div className="mt-2 text-2xs uppercase tracking-wide text-fg-subtle">
                        safety
                      </div>
                      <ul className="mt-1 text-2xs font-mono text-warning list-disc pl-4 space-y-0.5">
                        {s.safety.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </>
                  ) : null}
                </CardBody>
              </Card>
            ))
          )
        ) : workflows.isLoading ? (
          <LoadingCard />
        ) : workflows.error ? (
          <ErrorCard error={workflows.error} onRetry={() => workflows.refetch()} />
        ) : (workflows.data ?? []).length === 0 ? (
          <EmptyState title="No workflows registered" />
        ) : (
          workflows.data!.map((w) => (
            <Card key={w.name}>
              <CardHeader
                title={<span className="font-mono">{w.name}</span>}
                subtitle={w.path}
                actions={<Badge tone="success">workflow</Badge>}
              />
              <CardBody>
                {w.description ? (
                  <p className="text-xs text-fg-muted leading-relaxed">{w.description}</p>
                ) : null}
                {w.steps && w.steps.length > 0 ? (
                  <>
                    <div className="mt-2 text-2xs uppercase tracking-wide text-fg-subtle">
                      steps
                    </div>
                    <ol className="mt-1 text-2xs font-mono text-fg-muted list-decimal pl-4 space-y-0.5">
                      {w.steps.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ol>
                  </>
                ) : null}
                {w.applies_to && w.applies_to.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {w.applies_to.map((a) => (
                      <Badge key={a}>{a}</Badge>
                    ))}
                  </div>
                ) : null}
              </CardBody>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
