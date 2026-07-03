import {
  Crosshair, Swords, Skull, Users, Handshake, ScrollText,
  TrendingUp, Shield, Ban, Flag, Milestone,
} from 'lucide-react';

// Metadata for the kinds of events a conflict can contain.
// color stays within the sober palette; Icon is a lucide component reference.
export const KIND_META = {
  attack:       { label: 'Attack',       Icon: Crosshair,  color: '#b85a37' },
  battle:       { label: 'Battle',       Icon: Swords,     color: '#a83f39' },
  offensive:    { label: 'Offensive',    Icon: Swords,     color: '#a83f39' },
  atrocity:     { label: 'Atrocity',     Icon: Skull,      color: '#8f2f46' },
  displacement: { label: 'Displacement', Icon: Users,      color: '#c17d3e' },
  ceasefire:    { label: 'Ceasefire',    Icon: Handshake,  color: '#56988a' },
  treaty:       { label: 'Treaty',       Icon: ScrollText, color: '#3b82f6' },
  settlement:   { label: 'Settlement',   Icon: ScrollText, color: '#3b82f6' },
  escalation:   { label: 'Escalation',   Icon: TrendingUp, color: '#c17d3e' },
  intervention: { label: 'Intervention', Icon: Shield,     color: '#6b7f8a' },
  sanction:     { label: 'Sanction',     Icon: Ban,        color: '#3b82f6' },
  annexation:   { label: 'Annexation',   Icon: Flag,       color: '#dc2626' },
  milestone:    { label: 'Milestone',    Icon: Milestone,  color: '#82b8ab' },
};

export function kindMeta(kind) {
  return KIND_META[kind] || KIND_META.milestone;
}
