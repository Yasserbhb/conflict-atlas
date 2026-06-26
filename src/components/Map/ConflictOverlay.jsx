import { useMemo } from 'react';
import { conflictColorForCountry } from '../../utils/conflictColors';

// The aggressors / occupiers — the hostile actors
const AGGRESSOR_ROLES = new Set(['aggressor', 'occupier']);
// The ones on the receiving end — the battleground / targets
const DEFENDER_ROLES = new Set(['victim', 'defender', 'sanctioned']);
// External backers — they're INVOLVED but don't fight each other
const SUPPORT_ROLES = new Set(['funder', 'proxy', 'sanctioner']);
const MEDIATOR_ROLES = new Set(['mediator']);

function quadraticArc(x1, y1, x2, y2, curvature = 0.3) {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.sqrt(dx * dx + dy * dy);
  if (len === 0) return null;
  const offset = Math.min(len * curvature, 80);
  const cx = mx - (dy / len) * offset;
  const cy = my + (dx / len) * offset;
  return `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
}

// Build the arcs for one conflict. Core rule: countries on the SAME side never
// connect to each other (two funders, two victims). Everyone connects through
// the conflict's center — the battleground (a defender) or the main belligerent.
//
// IMPORTANT: only parties that actually have a location on the map are used.
// Some territories (Western Sahara, Palestine) aren't separate shapes in the
// base map, so they have no centroid — routing through them would make every
// arc vanish. We drop them and connect the remaining real countries instead.
function buildDirectedEdges(conflict, centroids) {
  const id = (p) => p.countryId;
  const parties = (conflict.parties || []).filter((p) => centroids[p.countryId]);
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

export default function ConflictOverlay({ activeConflicts, centroids, selectedCountryId }) {
  const arcs = useMemo(() => {
    const drawn = new Set();
    const result = [];

    // This overlay is "reach" mode: it only renders when a country is selected,
    // and shows only the arcs that touch THAT country across its conflicts.
    if (!selectedCountryId) return result;

    for (const conflict of activeConflicts) {
      const involvedIds = conflict.involvedCountries || [];
      if (!involvedIds.includes(selectedCountryId)) continue;

      // Color by the selected country's role in this conflict
      const color = conflictColorForCountry(conflict, selectedCountryId);
      const opacity = 0.85;
      const width = Math.max(0.7, conflict.severity * 0.3);

      const edges = buildDirectedEdges(conflict, centroids)
        .filter((e) => e.from === selectedCountryId || e.to === selectedCountryId);

      for (const { from, to, kind } of edges) {
        const key = `${conflict.id}:${from}:${to}`;
        if (drawn.has(key)) continue;
        drawn.add(key);

        const c1 = centroids[from];
        const c2 = centroids[to];
        if (!c1 || !c2) continue;

        const d = quadraticArc(c1[0], c1[1], c2[0], c2[1]);
        if (!d) continue;

        result.push({ key, d, color, opacity, width, kind });
      }
    }
    return result;
  }, [activeConflicts, centroids, selectedCountryId]);

  return (
    <g className="conflict-overlay" style={{ pointerEvents: 'none' }}>
      {arcs.map(({ key, d, color, opacity, width, kind }) => (
        <path
          key={key}
          d={d}
          fill="none"
          stroke={color}
          strokeWidth={width}
          opacity={opacity}
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          strokeDasharray={kind === 'support' ? `${width * 3} ${width * 2.5}` : undefined}
        />
      ))}
    </g>
  );
}
