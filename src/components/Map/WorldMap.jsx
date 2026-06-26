import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import * as topojson from 'topojson-client';
import { useApp } from '../../context/AppContext';
import { useCountrySeverity, useConflictFilter } from '../../hooks/useConflictFilter';
import { numericToAlpha3 } from '../../utils/isoLookup';
import { severityColor, roleColor } from '../../utils/conflictColors';
import ConflictOverlay from './ConflictOverlay';
import MapLegend from './MapLegend';
import styles from './WorldMap.module.css';

const WIDTH = 960;
const HEIGHT = 500;

// Countries whose d3.geoCentroid() is pulled far from their mainland
// by overseas territories — [longitude, latitude]
const CENTROID_OVERRIDES = {
  FRA: [2.35, 46.2],
  USA: [-98.0, 39.5],
  DNK: [10.0, 56.0],
  NOR: [15.5, 65.0],
  NLD: [5.3, 52.3],
  GBR: [-1.5, 52.5],
  PRT: [-8.2, 39.5],
  ESP: [-3.7, 40.4],
  RUS: [60.0, 61.0],
  AUS: [134.5, -25.5],
  CAN: [-96.0, 60.0],
  NZL: [172.5, -41.5],
};

export default function WorldMap() {
  const { state, dispatch } = useApp();
  const { conflicts, timelineYear, selectedCountryId } = state;

  const [countryPaths, setCountryPaths] = useState([]);
  const [centroids, setCentroids] = useState({});
  const [tooltip, setTooltip] = useState(null);
  const [transform, setTransform] = useState({ k: 1, x: 0, y: 0 });
  const svgRef = useRef(null);
  const zoomRef = useRef(null);
  const worldRef = useRef(null);

  const projection = d3.geoNaturalEarth1()
    .scale(153)
    .translate([WIDTH / 2, HEIGHT / 2]);
  const pathGen = d3.geoPath().projection(projection);

  const { focusedConflictId } = state;
  const activeConflicts = useConflictFilter(conflicts, timelineYear);
  const severityMap = useCountrySeverity(conflicts, timelineYear);

  const relatedIds = (() => {
    if (!selectedCountryId) return new Set();
    const set = new Set();
    for (const c of activeConflicts) {
      const ids = c.involvedCountries || [];
      if (!ids.includes(selectedCountryId)) continue;
      for (const id of ids) if (id !== selectedCountryId) set.add(id);
    }
    return set;
  })();

  const focusedConflict = focusedConflictId
    ? conflicts.find((c) => c.id === focusedConflictId)
    : null;
  const roleFillMap = {};
  if (focusedConflict) {
    for (const p of focusedConflict.parties || []) {
      roleFillMap[p.countryId] = roleColor(p.role);
    }
  }

  // Load the higher-resolution 50m map for sharper small countries
  useEffect(() => {
    d3.json('/data/countries-50m.json').then((world) => {
      worldRef.current = world;
      const geo = topojson.feature(world, world.objects.countries);
      const paths = [];
      const cents = {};
      for (const feature of geo.features) {
        const numId = parseInt(feature.id);
        const alpha3 = numericToAlpha3(numId);
        const d = pathGen(feature);
        if (d) paths.push({ numId, alpha3, d });
        if (alpha3) {
          const override = CENTROID_OVERRIDES[alpha3];
          const lonLat = override || d3.geoCentroid(feature);
          const proj = projection(lonLat);
          if (proj) cents[alpha3] = proj;
        }
      }
      setCountryPaths(paths);
      setCentroids(cents);
    });
  }, []);

  // Zoom / pan behaviour
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    const zoom = d3.zoom()
      .scaleExtent([1, 18])
      .translateExtent([[0, 0], [WIDTH, HEIGHT]])
      .on('zoom', (e) => setTransform(e.transform));
    zoomRef.current = zoom;
    svg.call(zoom);
    return () => svg.on('.zoom', null);
  }, []);

  function resetZoom() {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(400)
        .call(zoomRef.current.transform, d3.zoomIdentity);
    }
  }

  const { countries } = state;
  const countryNameMap = {};
  for (const c of countries) countryNameMap[c.id] = c.name;

  function handleCountryClick(alpha3) {
    if (!alpha3) return;
    if (selectedCountryId === alpha3) dispatch({ type: 'CLEAR_SELECTION' });
    else dispatch({ type: 'SELECT_COUNTRY', payload: alpha3 });
  }

  function setTip(e, alpha3) {
    const name = countryNameMap[alpha3] || alpha3 || null;
    if (!name) return;
    const rect = e.currentTarget.ownerSVGElement.getBoundingClientRect();
    // Convert pointer pixels → viewBox units so the tooltip sits at the cursor
    const x = ((e.clientX - rect.left) / rect.width) * WIDTH;
    const y = ((e.clientY - rect.top) / rect.height) * HEIGHT;
    setTooltip({ name, x, y });
  }

  const gTransform = `translate(${transform.x},${transform.y}) scale(${transform.k})`;

  return (
    <div className={styles.mapContainer}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className={styles.mapSvg}
        preserveAspectRatio="xMidYMid meet"
      >
        <rect width={WIDTH} height={HEIGHT} fill="#0f172a" />
        {/* Everything that should zoom/pan together */}
        <g transform={gTransform}>
          {countryPaths.map(({ numId, alpha3, d }) => {
            const severity = severityMap[alpha3] || 0;
            const isSelected = alpha3 === selectedCountryId;
            const isRelated = relatedIds.has(alpha3);
            const hasSev = severity > 0;
            const roleFill = roleFillMap[alpha3];

            let fill, stroke, strokeWidth;
            if (focusedConflict) {
              if (roleFill) {
                fill = roleFill;
                stroke = isSelected ? '#ffffff' : '#0b1220';
                strokeWidth = isSelected ? 1.6 : 0.6;
              } else {
                fill = '#172033';
                stroke = '#0f172a';
                strokeWidth = 0.4;
              }
            } else if (isSelected) {
              fill = '#3b82f6';
              stroke = '#93c5fd';
              strokeWidth = 1.4;
            } else if (isRelated) {
              fill = hasSev ? severityColor(severity) : '#253347';
              stroke = '#facc15';
              strokeWidth = 1.2;
            } else {
              fill = hasSev ? severityColor(severity) : '#253347';
              stroke = '#0f172a';
              strokeWidth = 0.4;
            }

            return (
              <path
                key={numId}
                d={d}
                fill={fill}
                stroke={stroke}
                strokeWidth={strokeWidth}
                vectorEffect="non-scaling-stroke"
                style={{ cursor: 'pointer', transition: 'fill 0.3s, stroke 0.2s' }}
                onClick={() => handleCountryClick(alpha3)}
                onMouseEnter={(e) => setTip(e, alpha3)}
                onMouseMove={(e) => setTip(e, alpha3)}
                onMouseLeave={() => setTooltip(null)}
              />
            );
          })}
          {selectedCountryId && !focusedConflict && (
            <ConflictOverlay
              activeConflicts={activeConflicts}
              centroids={centroids}
              selectedCountryId={selectedCountryId}
            />
          )}
        </g>

        {/* Tooltip sits outside the zoom group so it stays crisp and unscaled */}
        {tooltip && tooltip.name && (
          <g pointerEvents="none">
            <rect
              x={tooltip.x + 8}
              y={tooltip.y - 22}
              width={Math.min(tooltip.name.length * 7 + 16, 220)}
              height={22}
              rx={4}
              fill="#1e293b"
              opacity={0.92}
            />
            <text x={tooltip.x + 16} y={tooltip.y - 6} fill="#f1f5f9" fontSize={12} fontFamily="system-ui, sans-serif">
              {tooltip.name}
            </text>
          </g>
        )}
      </svg>

      <div className={styles.zoomControls}>
        <span className={styles.zoomHint}>scroll to zoom · drag to pan</span>
        {transform.k > 1.01 && (
          <button className={styles.resetBtn} onClick={resetZoom}>Reset view</button>
        )}
      </div>
      <div className={styles.bordersNote}>Modern borders shown — historical events are mapped to today's countries</div>
      <MapLegend />
    </div>
  );
}
