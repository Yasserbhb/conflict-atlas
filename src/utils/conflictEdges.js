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

// Build the directed edges for one conflict, given a lookup of which country ids have a
// known location (map centroids, globe lon/lat — anything truthy per id works). Core rule:
// countries on the SAME side never connect to each other (two funders, two victims).
// Everyone connects through the conflict's center — the battleground (a defender) or the
// main belligerent. Shared by the map's ConflictOverlay (2D arcs) and the 3D globe (arcs).
//
// IMPORTANT: only parties that actually have a known location are used. Some territories
// (Western Sahara, Palestine) aren't separate shapes in the base map, so they have no
// centroid — routing through them would make every arc vanish. We drop them and connect
// the remaining real countries instead.
export function buildConflictEdges(conflict, locations) {
  const id = (p) => p.countryId;
  const parties = (conflict.parties || []).filter((p) => locations[p.countryId]);
  if (parties.length < 2) return [];

  const aggressors = parties.filter((p) => AGGRESSOR_ROLES.has(p.role)).map(id);
  const defenders  = parties.filter((p) => DEFENDER_ROLES.has(p.role)).map(id);
  const supporters = parties.filter((p) => SUPPORT_ROLES.has(p.role)).map(id);
  const mediators  = parties.filter((p) => MEDIATOR_ROLES.has(p.role)).map(id);

  const edges = [];
  // kind: 'hostility' = X attacks/harms Y (solid line)
  //       'support'   = X backs / is merely involved with Y (dashed line)
  const push = (from, to, kind) => { if (from && to && from !== to) edges.push({ from, to, kind }); };

  // 1. Direct hostility: every aggressor → every defender (solid)
  for (const a of aggressors) for (const d of defenders) push(a, d, 'hostility');

  // The conflict's "center" — used only when there are no defenders.
  const hub = defenders[0] || aggressors[0] || parties[0].countryId;

  // 2. Outsiders (funders, mediators) are INVOLVED with every target — dashed,
  //    because they're backing/mediating, not directly attacking. e.g. Russia &
  //    France each tie to all three Sahel states. Never to each other.
  const externals = [...supporters, ...mediators];
  if (defenders.length > 0) {
    for (const e of externals) for (const d of defenders) push(e, d, 'support');
  } else {
    for (const e of externals) push(e, hub, 'support');
  }

  // 3. Multi-belligerent contesting a place with no defenders (e.g. disputed
  //    territory): the contenders are in hostility with the holder.
  if (defenders.length === 0) {
    for (const a of aggressors) push(a, hub, 'hostility');
  }

  // 4. Safety net: 2+ real parties but nothing connected (all same role).
  //    Connect them in a star as involvement so the conflict is never invisible.
  if (edges.length === 0) {
    const center = parties[0].countryId;
    for (let i = 1; i < parties.length; i++) push(parties[i].countryId, center, 'support');
  }

  return edges;
}
