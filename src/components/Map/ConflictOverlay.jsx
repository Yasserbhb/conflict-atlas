import { useMemo } from 'react';
import { conflictColorForCountry } from '../../utils/conflictColors';
import { buildConflictEdges } from '../../utils/conflictEdges';

function quadraticArc(x1, y1, x2, y2, curvature = 0.36) {
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

      // Color by the selected country's role in this conflict.
      // Thin, semi-transparent threads (not bold pipes) for a calmer, mature look.
      const color = conflictColorForCountry(conflict, selectedCountryId);
      const opacity = 0.6;
      const width = Math.max(0.7, conflict.severity * 0.28);

      const edges = buildConflictEdges(conflict, centroids)
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
          strokeDasharray={kind === 'support' ? '5 4' : undefined}
        />
      ))}
    </g>
  );
}
