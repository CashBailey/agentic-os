import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchReadiness, ProjectsAPI, API_BASE_URL } from '../lib/api';
import { useUIStore } from '../state/store';
import { useTheme } from '../state/theme';
import { Pill, type PillTone } from './ui/Pill';
import { Button } from './ui/Button';
import { IconChevronDown, IconMoon, IconSun } from './icons/Icons';

function readinessToTone(s: 'ok' | 'degraded' | 'down' | undefined): {
  tone: PillTone;
  label: string;
} {
  switch (s) {
    case 'ok':
      return { tone: 'success', label: 'API ready' };
    case 'degraded':
      return { tone: 'warning', label: 'API degraded' };
    case 'down':
      return { tone: 'danger', label: 'API offline' };
    default:
      return { tone: 'neutral', label: 'API checking' };
  }
}

const apiHost = API_BASE_URL.replace(/^https?:\/\//, '');

export function TopBar() {
  const { currentProject, setCurrentProject } = useUIStore();
  const { theme, toggle } = useTheme();

  const readiness = useQuery({
    queryKey: ['readiness'],
    queryFn: fetchReadiness,
    refetchInterval: 10_000,
  });

  const projects = useQuery({
    queryKey: ['projects'],
    queryFn: () => ProjectsAPI.list(),
    refetchInterval: 30_000,
  });

  // Auto-select first project once loaded, if none chosen or stored slug is stale.
  useEffect(() => {
    const list = projects.data;
    if (!list || list.length === 0) return;
    const slugs = list.map((p) => p.slug);
    if (!currentProject || !slugs.includes(currentProject)) {
      setCurrentProject(list[0].slug);
    }
  }, [projects.data, currentProject, setCurrentProject]);

  const { tone, label } = readinessToTone(readiness.data);
  const list = projects.data ?? [];

  return (
    <header className="h-12 shrink-0 border-b border-border bg-bg-elevated flex items-center px-3 gap-3">
      <div className="relative">
        <select
          aria-label="Project"
          value={currentProject}
          onChange={(e) => setCurrentProject(e.target.value)}
          disabled={list.length === 0}
          className="appearance-none bg-bg-subtle border border-border text-xs text-fg pl-2 pr-7 h-7 rounded-sm font-mono hover:border-border-strong focus:border-accent transition-colors disabled:opacity-50"
        >
          {list.length === 0 ? (
            <option value="">{projects.isLoading ? 'loading…' : 'no projects'}</option>
          ) : (
            list.map((p) => (
              <option key={p.slug} value={p.slug}>
                {p.slug}
              </option>
            ))
          )}
        </select>
        <IconChevronDown className="absolute right-1.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-fg-subtle pointer-events-none" />
      </div>

      <Pill tone={tone} dot>
        {label}
      </Pill>

      <div className="flex-1" />

      <div className="text-2xs text-fg-subtle font-mono hidden sm:block">{apiHost}</div>

      <Button
        variant="ghost"
        size="sm"
        aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
        onClick={toggle}
        title={`Theme: ${theme}`}
      >
        {theme === 'dark' ? (
          <IconSun className="h-4 w-4" />
        ) : (
          <IconMoon className="h-4 w-4" />
        )}
      </Button>
    </header>
  );
}
