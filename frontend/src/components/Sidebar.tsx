import type { ReactElement } from 'react';
import { NavLink } from 'react-router-dom';
import {
  IconAdapters,
  IconApprovals,
  IconAudit,
  IconContext,
  IconDashboard,
  IconMemory,
  IconPolicies,
  IconSkills,
} from './icons/Icons';
import { cn } from '../lib/cn';

type Item = {
  to: string;
  label: string;
  icon: (p: { className?: string }) => ReactElement;
};

const NAV: Item[] = [
  { to: '/', label: 'Dashboard', icon: IconDashboard },
  { to: '/context', label: 'Context', icon: IconContext },
  { to: '/memory', label: 'Memory', icon: IconMemory },
  { to: '/adapters', label: 'Adapters', icon: IconAdapters },
  { to: '/policies', label: 'Policies', icon: IconPolicies },
  { to: '/skills', label: 'Skills & Workflows', icon: IconSkills },
  { to: '/approvals', label: 'Approvals', icon: IconApprovals },
  { to: '/audit', label: 'Audit', icon: IconAudit },
];

export function Sidebar() {
  return (
    <aside className="w-56 shrink-0 border-r border-border bg-bg-elevated flex flex-col">
      <div className="h-12 flex items-center gap-2 px-3 border-b border-border">
        <div className="h-5 w-5 rounded-xs bg-accent grid place-items-center">
          <span className="text-2xs font-mono font-bold text-accent-fg">A</span>
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-xs font-semibold text-fg">Agentic OS</span>
          <span className="text-2xs text-fg-subtle font-mono">v0.1.0</span>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-2 px-2 flex flex-col gap-0.5">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'group flex items-center gap-2 px-2 h-8 rounded-sm text-xs transition-colors',
                isActive
                  ? 'bg-bg-subtle text-fg'
                  : 'text-fg-muted hover:bg-bg-subtle hover:text-fg',
              )
            }
          >
            {({ isActive }) => (
              <>
                <item.icon
                  className={cn(
                    'h-4 w-4 shrink-0',
                    isActive ? 'text-accent' : 'text-fg-subtle group-hover:text-fg-muted',
                  )}
                />
                <span className="truncate">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-2 border-t border-border text-2xs text-fg-subtle font-mono">
        control plane
      </div>
    </aside>
  );
}
