import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { useApp } from '../../context/AppContext';
import { TYPE_COLORS, TYPE_LABELS } from '../../utils/conflictColors';
import styles from './GraphView.module.css';

const W = 700;
const H = 500;

export default function GraphView() {
  const { state, dispatch } = useApp();
  const { selectedCountryId, conflicts, countries } = state;
  const svgRef = useRef(null);
  const simRef = useRef(null);

  const countryNameMap = {};
  for (const c of countries) countryNameMap[c.id] = c.name;

  useEffect(() => {
    if (!selectedCountryId || !svgRef.current) return;

    // Build graph: nodes within 1 hop of selectedCountryId
    const nodeIds = new Set([selectedCountryId]);
    const edges = [];

    for (const conflict of conflicts) {
      const parties = conflict.involvedCountries || [];
      if (!parties.includes(selectedCountryId)) continue;
      for (const id of parties) nodeIds.add(id);
      for (let i = 0; i < parties.length; i++) {
        for (let j = i + 1; j < parties.length; j++) {
          edges.push({
            source: parties[i],
            target: parties[j],
            conflict,
          });
        }
      }
    }

    const nodes = [...nodeIds].map((id) => ({
      id,
      name: countryNameMap[id] || id,
      isCenter: id === selectedCountryId,
    }));

    // Clean previous
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('viewBox', `0 0 ${W} ${H}`);

    // Arrow defs
    const defs = svg.append('defs');
    const marker = defs.append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -4 8 8')
      .attr('refX', 18)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto');
    marker.append('path').attr('d', 'M0,-4L8,0L0,4').attr('fill', '#334155');

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id((d) => d.id).distance(120).strength(0.6))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide(32));

    simRef.current = sim;

    const link = svg.append('g').selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', (d) => TYPE_COLORS[d.conflict.type] || '#334155')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', (d) => Math.max(1, d.conflict.severity * 0.5))
      .attr('marker-end', 'url(#arrow)');

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
      .on('click', (_, d) => {
        dispatch({ type: 'SELECT_COUNTRY', payload: d.id });
        dispatch({ type: 'HIDE_GRAPH' });
      });

    node.append('circle')
      .attr('r', (d) => d.isCenter ? 20 : 12)
      .attr('fill', (d) => d.isCenter ? '#3b82f6' : '#1e3a5f')
      .attr('stroke', (d) => d.isCenter ? '#93c5fd' : '#334155')
      .attr('stroke-width', 1.5);

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('font-size', (d) => d.isCenter ? 10 : 8)
      .attr('font-family', 'system-ui, sans-serif')
      .attr('fill', '#e2e8f0')
      .attr('pointer-events', 'none')
      .text((d) => d.name.length > 12 ? d.name.substring(0, 11) + '…' : d.name);

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
  }, [selectedCountryId, conflicts, countries]);

  if (!state.showGraphView || !selectedCountryId) return null;

  const centerCountry = countries.find((c) => c.id === selectedCountryId);

  return (
    <div className={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) dispatch({ type: 'HIDE_GRAPH' }); }}>
      <div className={styles.modal}>
        <div className={styles.header}>
          <span className={styles.title}>Conflict Network — {centerCountry?.name || selectedCountryId}</span>
          <span className={styles.hint}>Click a node to navigate · Drag to rearrange</span>
          <button className={styles.closeBtn} onClick={() => dispatch({ type: 'HIDE_GRAPH' })}>✕</button>
        </div>
        <svg ref={svgRef} className={styles.graph} />
        <div className={styles.legend}>
          {Object.entries(TYPE_COLORS).map(([type, color]) => (
            <span key={type} className={styles.legendItem}>
              <span className={styles.dot} style={{ background: color }} />
              {TYPE_LABELS[type]}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
