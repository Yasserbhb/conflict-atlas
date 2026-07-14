// Role buckets shared by the map's ConflictOverlay (per-conflict arcs between a selected
// country and its conflicts) and the conflict relationship graph (cross-conflict edges) —
// single source of truth for "what kind of actor is this role," extracted so neither has to
// reinvent it.
export const AGGRESSOR_ROLES = new Set(['aggressor', 'occupier']);
export const DEFENDER_ROLES = new Set(['victim', 'defender', 'sanctioned']);
export const SUPPORT_ROLES = new Set(['funder', 'proxy', 'sanctioner']);
export const MEDIATOR_ROLES = new Set(['mediator']);

// Coarse classification used where a role needs to collapse to one bucket rather than the
// full role taxonomy — e.g. the relationship graph's binary hostile/support edge coloring.
export function classifyParty(role) {
  if (AGGRESSOR_ROLES.has(role) || DEFENDER_ROLES.has(role)) return 'hostile'; // active belligerent, either side
  if (SUPPORT_ROLES.has(role)) return 'support';
  if (MEDIATOR_ROLES.has(role)) return 'mediator';
  return null;
}
