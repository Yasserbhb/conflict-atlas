import { useEffect, useMemo, useRef, useState } from 'react';
import { X } from 'lucide-react';
import * as d3 from 'd3';
import { useApp } from '../../context/AppContext';
import { TYPE_COLORS, TYPE_LABELS } from '../../utils/conflictColors';
import { classifyParty } from '../../utils/conflictEdges';
import styles from './GraphView.module.css';

const W = 700;
const H = 500;

// Cross-conflict edge kinds, in render priority (an edge can qualify for more than one kind —
// the highest-priority one wins the line style, rather than stacking).
const EDGE_STYLE = {
  alias:                { stroke: '#d9a441', width: 2.2, dash: null,  opacity: 0.85 },
  'belligerent-hostile': { stroke: '#ef4444', width: 1.2, dash: null,  opacity: 0.55 },
  'belligerent-support': { stroke: '#64748b', width: 0.8, dash: '4 3', opacity: 0.4 },
  'time-overlap':        { stroke: '#334155', width: 0.4, dash: null,  opacity: 0.25 },
  'same-type':           { stroke: '#334155', width: 0.5, dash: '2 2', opacity: 0.25 },
};
const EDGE_PRIORITY = ['alias', 'belligerent-hostile', 'belligerent-support', 'time-overlap', 'same-type'];
const primaryKind = (kinds) => EDGE_PRIORITY.find((k) => kinds.has(k)) || 'belligerent-support';

// Nodes = conflicts, edges = real relationships between them (not just "both involve a
// country" naively — a shared aggressor reads differently from a shared mediator). See
// src/utils/conflictEdges.js for the role classification this reuses from the map overlay.
function buildConflictGraph(conflicts, { showTimeOverlap, showSameType }) {
  const edgeMap = new Map(); // "idA:idB" (sorted) -> { source, target, kinds: Set }
  const addEdge = (a, b, kind) => {
    if (!a || !b || a === b) return;
    const [x, y] = a < b ? [a, b] : [b, a];
    const key = `${x}:${y}`;
    if (!edgeMap.has(key)) edgeMap.set(key, { source: x, target: y, kinds: new Set() });
    edgeMap.get(key).kinds.add(kind);
  };

  // 1. Shared belligerent (always on) — two conflicts sharing a country. Hostile if that
  // country is an active belligerent (either side) in either conflict; otherwise support.
  const byCountry = new Map();
  for (const c of conflicts) {
    for (const p of c.parties || []) {
      if (!byCountry.has(p.countryId)) byCountry.set(p.countryId, []);
      byCountry.get(p.countryId).push({ conflictId: c.id, role: p.role });
    }
  }
  for (const entries of byCountry.values()) {
    for (let i = 0; i < entries.length; i++) {
      for (let j = i + 1; j < entries.length; j++) {
        const hostile = classifyParty(entries[i].role) === 'hostile' || classifyParty(entries[j].role) === 'hostile';
        addEdge(entries[i].conflictId, entries[j].conflictId, hostile ? 'belligerent-hostile' : 'belligerent-support');
      }
    }
  }

  // 4. Alias overlap (always on, rare/high-signal) — same name (title or an explicit alias)
  // shared across conflicts, e.g. two records of the same underlying war under different titles.
  const byName = new Map();
  for (const c of conflicts) {
    const names = new Set([c.title, ...(c.aliases || [])].map((s) => (s || '').trim().toLowerCase()).filter(Boolean));
    for (const n of names) {
      if (!byName.has(n)) byName.set(n, []);
      byName.get(n).push(c.id);
    }
  }
  for (const ids of byName.values()) {
    for (let i = 0; i < ids.length; i++)
      for (let j = i + 1; j < ids.length; j++)
        addEdge(ids[i], ids[j], 'alias');
  }

  // 2. Overlapping time span (opt-in — dense at ~240 conflicts, off by default)
  if (showTimeOverlap) {
    const spans = conflicts
      .map((c) => ({
        id: c.id,
        start: parseInt(String(c.startDate).slice(0, 4), 10),
        end: c.ongoing ? 2026 : parseInt(String(c.endDate || c.startDate).slice(0, 4), 10),
      }))
      .filter((s) => !isNaN(s.start) && !isNaN(s.end));
    for (let i = 0; i < spans.length; i++) {
      for (let j = i + 1; j < spans.length; j++) {
        const a = spans[i], b = spans[j];
        if (a.start <= b.end && b.start <= a.end) addEdge(a.id, b.id, 'time-overlap');
      }
    }
  }

  // 3. Same type (opt-in — dense, off by default)
  if (showSameType) {
    const byType = new Map();
    for (const c of conflicts) {
      if (!byType.has(c.type)) byType.set(c.type, []);
      byType.get(c.type).push(c.id);
    }
    for (const ids of byType.values()) {
      for (let i = 0; i < ids.length; i++)
        for (let j = i + 1; j < ids.length; j++)
          addEdge(ids[i], ids[j], 'same-type');
    }
  }

  const connected = new Set();
  for (const e of edgeMap.values()) { connected.add(e.source); connected.add(e.target); }
  const nodes = conflicts.filter((c) => connected.has(c.id)).map((c) => ({ id: c.id, title: c.title, type: c.type }));
  const edges = [...edgeMap.values()].map((e) => ({ ...e, kind: primaryKind(e.kinds) }));
  return { nodes, edges };
}

export default function GraphView() {
  const { state, dispatch } = useApp();
  const { selectedCountryId, conflicts, countries, graphMode, showGraphView } = state;
  const svgRef = useRef(null);
  const simRef = useRef(null);
  const [showTimeOverlap, setShowTimeOverlap] = useState(false);
  const [showSameType, setShowSameType] = useState(false);

  const countryNameMap = useMemo(() => {
    const m = {};
    for (const c of countries) m[c.id] = c.name;
    return m;
  }, [countries]);

  const isConflictMode = graphMode === 'conflicts';

  useEffect(() => {
    if (!showGraphView || !svgRef.current) return;
    if (!isConflictMode && !selectedCountryId) return;

    d3.select(svgRef.current).selectAll('*').remove();
    const svg = d3.select(svgRef.current).attr('viewBox', `0 0 ${W} ${H}`);
    const defs = svg.append('defs');
    const marker = defs.append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -4 8 8')
      .attr('refX', 18)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto');
    marker.append('path').attr('d', 'M0,-4L8,0L0,4').attr('fill', '#3f4d54');

    let nodes, edges, nodeRadius, nodeColor, nodeLabel, onNodeClick;

    if (isConflictMode) {
      const built = buildConflictGraph(conflicts, { showTimeOverlap, showSameType });
      nodes = built.nodes;
      edges = built.edges;
      nodeRadius = () => 8;
      nodeColor = (d) => TYPE_COLORS[d.type] || '#1e262b';
      nodeLabel = (d) => d.title;
      onNodeClick = (d) => {
        dispatch({ type: 'OPEN_CONFLICT', payload: d.id });
        dispatch({ type: 'HIDE_GRAPH' });
      };
    } else {
      // Country ego-network: nodes within 1 hop of selectedCountryId, edges = every pairwise
      // party in a shared conflict (naive — kept as-is, this mode is unchanged from before).
      const nodeIds = new Set([selectedCountryId]);
      const rawEdges = [];
      for (const conflict of conflicts) {
        const parties = conflict.involvedCountries || [];
        if (!parties.includes(selectedCountryId)) continue;
        for (const id of parties) nodeIds.add(id);
        for (let i = 0; i < parties.length; i++) {
          for (let j = i + 1; j < parties.length; j++) {
            rawEdges.push({ source: parties[i], target: parties[j], conflict, kind: 'country' });
          }
        }
      }
      nodes = [...nodeIds].map((id) => ({ id, name: countryNameMap[id] || id, isCenter: id === selectedCountryId }));
      edges = rawEdges;
      nodeRadius = (d) => (d.isCenter ? 20 : 12);
      nodeColor = (d) => (d.isCenter ? '#3a6ea5' : '#1e262b');
      nodeLabel = (d) => d.name;
      onNodeClick = (d) => {
        dispatch({ type: 'SELECT_COUNTRY', payload: d.id });
        dispatch({ type: 'HIDE_GRAPH' });
      };
    }

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id((d) => d.id).distance(isConflictMode ? 70 : 120).strength(0.5))
      .force('charge', d3.forceManyBody().strength(isConflictMode ? -120 : -300))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide(isConflictMode ? 16 : 32));
    simRef.current = sim;

    const link = svg.append('g').selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', (d) => isConflictMode ? EDGE_STYLE[d.kind].stroke : (TYPE_COLORS[d.conflict.type] || '#334155'))
      .attr('stroke-opacity', (d) => isConflictMode ? EDGE_STYLE[d.kind].opacity : 0.6)
      .attr('stroke-width', (d) => isConflictMode ? EDGE_STYLE[d.kind].width : Math.max(1, d.conflict.severity * 0.5))
      .attr('stroke-dasharray', (d) => isConflictMode ? EDGE_STYLE[d.kind].dash : null)
      .attr('marker-end', isConflictMode ? null : 'url(#arrow)');

    const node = svg.append('g').selectAll('g')
      .data(nodes)
      .join('g')
      .style('cursor', 'pointer')
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) sim.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d) => {
          if (!event.active) sim.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
      )
      .on('click', (_, d) => onNodeClick(d));

    node.append('circle')
      .attr('r', nodeRadius)
      .attr('fill', nodeColor)
      .attr('stroke', (d) => (!isConflictMode && d.isCenter) ? '#7fb0d6' : '#2f3d47')
      .attr('stroke-width', 1.5);

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('font-size', isConflictMode ? 7 : (d) => d.isCenter ? 10 : 8)
      .attr('font-family', 'system-ui, sans-serif')
      .attr('fill', '#e2e8f0')
      .attr('pointer-events', 'none')
      .text((d) => {
        const label = nodeLabel(d);
        const max = isConflictMode ? 16 : 12;
        return label.length > max ? label.substring(0, max - 1) + '…' : label;
      });

    node.append('title').text(nodeLabel);

    sim.on('tick', () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y);
      node.attr('transform', (d) => `translate(${d.x},${d.y})`);
    });

    return () => {
      sim.stop();
      sim.on('tick', null);
    };
  }, [showGraphView, isConflictMode, selectedCountryId, conflicts, countries, countryNameMap, showTimeOverlap, showSameType, dispatch]);

  if (!showGraphView) return null;
  if (!isConflictMode && !selectedCountryId) return null;

  const centerCountry = !isConflictMode && countries.find((c) => c.id === selectedCountryId);

  return (
    <div className={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) dispatch({ type: 'HIDE_GRAPH' }); }}>
      <div className={styles.modal}>
        <div className={styles.header}>
          <span className={styles.title}>
            {isConflictMode ? 'Conflict Relationships' : `Conflict Network — ${centerCountry?.name || selectedCountryId}`}
          </span>
          <span className={styles.hint}>Click a node to navigate · Drag to rearrange</span>
          <button className={styles.closeBtn} aria-label="Close" onClick={() => dispatch({ type: 'HIDE_GRAPH' })}><X size={16} strokeWidth={2.2} aria-hidden="true" /></button>
        </div>
        <svg ref={svgRef} className={styles.graph} />
        {isConflictMode ? (
          <>
            <div className={styles.toggles}>
              <label className={styles.toggle}>
                <input type="checkbox" checked={showTimeOverlap} onChange={(e) => setShowTimeOverlap(e.target.checked)} />
                Show overlapping-era links
              </label>
              <label className={styles.toggle}>
                <input type="checkbox" checked={showSameType} onChange={(e) => setShowSameType(e.target.checked)} />
                Show same-type links
              </label>
            </div>
            <div className={styles.legend}>
              <span className={styles.legendItem}><span className={styles.dot} style={{ background: EDGE_STYLE.alias.stroke }} />Same conflict, different name</span>
              <span className={styles.legendItem}><span className={styles.dot} style={{ background: EDGE_STYLE['belligerent-hostile'].stroke }} />Shared belligerent</span>
              <span className={styles.legendItem}><span className={styles.dot} style={{ background: EDGE_STYLE['belligerent-support'].stroke }} />Shared backer/mediator</span>
            </div>
          </>
        ) : (
          <div className={styles.legend}>
            {Object.entries(TYPE_COLORS).map(([type, color]) => (
              <span key={type} className={styles.legendItem}>
                <span className={styles.dot} style={{ background: color }} />
                {TYPE_LABELS[type]}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
