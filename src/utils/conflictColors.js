// Pigments, not screen primaries. These used to be raw Tailwind defaults (red-500,
// orange-500, violet-600…), which fought the hand-tuned severity ramp below — two
// palettes in one view. They now share its DNA: earthy, desaturated, ink-like, and
// spread widely enough in hue to stay tellable apart on a dark map.
export const TYPE_COLORS = {
  war: '#b5503c',                 // rust — the archetype
  civil_war: '#a06d2e',           // bronze — turned inward
  genocide: '#7a3050',            // oxblood — the gravest, so the deepest
  occupation: '#4d7a80',          // verdigris — territorial, static, held
  proxy_war: '#8f8850',           // brass — fought at a remove
  sanctions: '#55749c',           // steel — pressure without arms
  disputed_territory: '#7b9470',  // lichen — contested, unresolved
};

export const TYPE_LABELS = {
  war: 'War',
  civil_war: 'Civil War',
  genocide: 'Genocide',
  occupation: 'Occupation',
  proxy_war: 'Proxy War',
  sanctions: 'Sanctions',
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

// A sequential ramp should get DARKER as it gets graver — the old top step (#8f2f46) sat at
// hue 345° and read as magenta, making "catastrophic" the brightest thing on a dark map
// instead of the heaviest. Re-tuned to fall toward oxblood: lightness drops monotonically,
// hue swings off pink toward true red.
export const SEVERITY_COLORS = [
  '#37413a', // 0 = none
  '#b8935a', // 1 = low tension      (pale ochre)
  '#b57a42', // 2 = serious          (burnt amber)
  '#a85c3c', // 3 = armed conflict   (terracotta)
  '#8f4038', // 4 = mass atrocity    (brick)
  '#6e2a30', // 5 = catastrophic     (oxblood)
];

export function severityColor(severity) {
  return SEVERITY_COLORS[Math.min(Math.max(0, severity), 5)];
}

// When a country is selected, arcs and cards are colored by the country's ROLE
// in that specific conflict — not the conflict's generic type
// Same pigment family as TYPE_COLORS, grouped so the semantics read at a glance:
// rusts act, brasses bankroll, steels pressure, greens are acted upon, slate stands aside.
export const ROLE_COLORS = {
  aggressor:  '#b5503c', // rust        — you started it
  occupier:   '#8f4436', // deeper rust — you hold territory
  funder:     '#a67c34', // brass       — you paid for it
  proxy:      '#99713f', // bronze      — you fought for someone else
  sanctioner: '#55749c', // steel       — you applied pressure
  sanctioned: '#6d5b8f', // iris        — pressure applied to you
  defender:   '#5d8a72', // green       — you fought back
  victim:     '#8fae94', // pale sage   — you suffered
  mediator:   '#7e8c93', // slate       — you tried to stop it
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
