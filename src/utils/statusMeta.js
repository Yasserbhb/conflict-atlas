import { Activity, TrendingDown, Pause, Moon, CircleCheck, BadgeCheck } from 'lucide-react';

// Metadata for a conflict's lifecycle status (pipeline-populated; most conflicts predate this
// field and simply won't have one — see statusMeta()'s null return below).
export const STATUS_META = {
  active:    { label: 'Active',    Icon: Activity,     color: '#c17d3e' },
  easing:    { label: 'Easing',    Icon: TrendingDown,  color: '#82b8ab' },
  suspended: { label: 'Suspended', Icon: Pause,         color: '#3b82f6' },
  dormant:   { label: 'Dormant',   Icon: Moon,          color: '#6b7f8a' },
  ended:     { label: 'Ended',     Icon: CircleCheck,   color: '#94a3b8' },
  resolved:  { label: 'Resolved',  Icon: BadgeCheck,    color: '#56988a' },
};

// Unlike kindMeta() (which falls back to 'milestone' for an unknown kind), an unknown/absent
// status returns null — legacy conflicts with no status field should render nothing, not a
// fabricated default.
export function statusMeta(status) {
  return STATUS_META[status] || null;
}
