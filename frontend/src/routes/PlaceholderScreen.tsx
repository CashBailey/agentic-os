import type { ReactNode } from 'react';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { PageHeader } from '../components/PageHeader';
import { Pill, type PillTone } from '../components/ui/Pill';
import { Button } from '../components/ui/Button';

export interface MockRow {
  label: string;
  value: ReactNode;
  tone?: PillTone;
}

export function PlaceholderScreen({
  title,
  description,
  breadcrumbs,
  todo,
  mockTitle,
  mockSubtitle,
  rows,
}: {
  title: string;
  description: string;
  breadcrumbs: string[];
  todo: string;
  mockTitle: string;
  mockSubtitle?: string;
  rows: MockRow[];
}) {
  return (
    <div className="flex flex-col">
      <PageHeader
        breadcrumbs={breadcrumbs}
        title={title}
        description={description}
        actions={
          <>
            <Button variant="ghost" size="sm">
              Docs
            </Button>
            <Button variant="primary" size="sm">
              New
            </Button>
          </>
        }
      />
      <div className="p-6 grid gap-4 grid-cols-1 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title={mockTitle}
            subtitle={mockSubtitle}
            actions={<Pill tone="accent">preview</Pill>}
          />
          <CardBody className="p-0">
            <table className="w-full text-xs">
              <thead className="text-2xs uppercase tracking-wide text-fg-subtle">
                <tr className="border-b border-border">
                  <th className="text-left font-medium px-4 py-2">Field</th>
                  <th className="text-left font-medium px-4 py-2">Value</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {rows.map((r, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="px-4 py-2 text-fg-muted">{r.label}</td>
                    <td className="px-4 py-2 text-fg">
                      {r.tone ? <Pill tone={r.tone} dot>{r.value}</Pill> : r.value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="TODO" subtitle="Round 4 — Builder Contract" />
          <CardBody>
            <p className="text-xs text-fg-muted leading-relaxed">{todo}</p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
