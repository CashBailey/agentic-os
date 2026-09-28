import type { SVGProps } from 'react';

// Minimal hand-rolled icon set. Stroke-based, 1.5px, currentColor. Adding new
// glyphs here keeps the bundle small (no react-icons / lucide dependency).

type P = SVGProps<SVGSVGElement>;
const base = {
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

export const IconDashboard = (p: P) => (
  <svg {...base} {...p}>
    <rect x="3" y="3" width="7" height="9" rx="1" />
    <rect x="14" y="3" width="7" height="5" rx="1" />
    <rect x="14" y="12" width="7" height="9" rx="1" />
    <rect x="3" y="16" width="7" height="5" rx="1" />
  </svg>
);

export const IconContext = (p: P) => (
  <svg {...base} {...p}>
    <path d="M4 5h16M4 10h10M4 15h16M4 20h10" />
  </svg>
);

export const IconMemory = (p: P) => (
  <svg {...base} {...p}>
    <rect x="4" y="4" width="16" height="16" rx="2" />
    <path d="M8 4v16M16 4v16M4 8h16M4 16h16" />
  </svg>
);

export const IconAdapters = (p: P) => (
  <svg {...base} {...p}>
    <path d="M9 3v6a3 3 0 003 3 3 3 0 003-3V3" />
    <path d="M12 12v9" />
    <path d="M7 3h4M13 3h4" />
  </svg>
);

export const IconPolicies = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z" />
    <path d="M9 12l2 2 4-4" />
  </svg>
);

export const IconSkills = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" />
  </svg>
);

export const IconApprovals = (p: P) => (
  <svg {...base} {...p}>
    <path d="M5 12l4 4L19 6" />
    <path d="M19 14v5a2 2 0 01-2 2H7a2 2 0 01-2-2v-5" />
  </svg>
);

export const IconAudit = (p: P) => (
  <svg {...base} {...p}>
    <path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9z" />
    <path d="M14 3v6h6" />
    <path d="M8 13h8M8 17h5" />
  </svg>
);

export const IconSun = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);

export const IconMoon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M21 12.8A9 9 0 1111.2 3 7 7 0 0021 12.8z" />
  </svg>
);

export const IconChevronDown = (p: P) => (
  <svg {...base} {...p}>
    <path d="M6 9l6 6 6-6" />
  </svg>
);
