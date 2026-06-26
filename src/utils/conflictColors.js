export const TYPE_COLORS = {
  war: '#ef4444',
  civil_war: '#f97316',
  genocide: '#7c3aed',
  occupation: '#dc2626',
  proxy_war: '#f59e0b',
  sanctions: '#3b82f6',
  funding: '#22d3ee',
  disputed_territory: '#84cc16',
};

export const TYPE_LABELS = {
  war: 'War',
  civil_war: 'Civil War',
  genocide: 'Genocide',
  occupation: 'Occupation',
  proxy_war: 'Proxy War',
  sanctions: 'Sanctions',
  funding: 'Foreign Funding',
  disputed_territory: 'Disputed Territory',
};

export const ROLE_LABELS = {
  aggressor: 'Aggressor',
  defender: 'Defender',
  victim: 'Victim',
  funder: 'Funder',
  proxy: 'Proxy',
  occupier: 'Occupier',
  mediator: 'Mediator',
  sanctioner: 'Sanctioner',
  sanctioned: 'Sanctioned',
};

export const SEVERITY_COLORS = [
  '#374151', // 0 = none
  '#eab308', // 1 = low tension      (yellow)
  '#f59e0b', // 2 = serious          (amber)
  '#f97316', // 3 = armed conflict   (orange)
  '#dc2626', // 4 = mass atrocity    (red)
  '#9f1239', // 5 = catastrophic     (deep crimson)
];

export function severityColor(severity) {
  return SEVERITY_COLORS[Math.min(Math.max(0, severity), 5)];
}

// When a country is selected, arcs and cards are colored by the country's ROLE
// in that specific conflict — not the conflict's generic type
export const ROLE_COLORS = {
  aggressor:  '#ef4444', // red    — you started it
  occupier:   '#dc2626', // dark red — you hold territory
  funder:     '#f59e0b', // amber  — you paid for it
  proxy:      '#f97316', // orange — you fought for someone else
  sanctioner: '#3b82f6', // blue   — you applied pressure
  sanctioned: '#8b5cf6', // purple — pressure applied to you
  defender:   '#22c55e', // green  — you fought back
  victim:     '#86efac', // light green — you suffered
  mediator:   '#64748b', // gray   — you tried to stop it
};

export function roleColor(role) {
  return ROLE_COLORS[role] || '#94a3b8';
}

// Get the selected country's role in a conflict, return its color
export function conflictColorForCountry(conflict, countryId) {
  if (!countryId) return TYPE_COLORS[conflict.type] || '#94a3b8';
  const party = conflict.parties?.find((p) => p.countryId === countryId);
  if (!party) return TYPE_COLORS[conflict.type] || '#94a3b8';
  return roleColor(party.role);
}

export const CONFLICT_TYPES = Object.keys(TYPE_COLORS);
export const ROLE_TYPES = Object.keys(ROLE_LABELS);
