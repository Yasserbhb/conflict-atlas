import { useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import * as echarts from 'echarts/core';
import { GlobeComponent } from 'echarts-gl/components';
import { Lines3DChart } from 'echarts-gl/charts';
import { CanvasRenderer } from 'echarts/renderers';
import Ray from 'claygl/src/math/Ray';
import { useApp } from '../../context/AppContext';
import { useConflictFilter, useCountrySeverity } from '../../hooks/useConflictFilter';
import { applyConflictFilters } from '../../utils/dateUtils';
import { buildConflictEdges } from '../../utils/conflictEdges';
import { loadCountryGeo, renderCountryTexture } from '../../utils/countryGeo';
import { severityColor, conflictColorForCountry } from '../../utils/conflictColors';
import styles from './GlobeView.module.css';

echarts.use([GlobeComponent, Lines3DChart, CanvasRenderer]);

function hexToRgb(hex) {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function fade(hex, alpha) {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// The origin, as a claygl Vector3-shaped object — echarts-gl's Ray.intersectSphere
// only reads `.array`, so this avoids pulling in claygl just for that.
const GLOBE_CENTER = { array: [0, 0, 0] };

export default function GlobeView() {
  const { state, dispatch } = useApp();
  const { conflicts, timelineYear, selectedCountryId } = state;

  const containerRef = useRef(null);
  const chartRef = useRef(null);
  // The click handler is attached once when the chart is created, so it needs refs
  // (not React state bindings) to read the latest selection/geometry at click time.
  const selectedCountryIdRef = useRef(null);
  useEffect(() => { selectedCountryIdRef.current = selectedCountryId; }, [selectedCountryId]);
  const featuresRef = useRef(null);

  const [lonLat, setLonLat] = useState(null);
  const [features, setFeatures] = useState(null);
  // Mirrors the 2D map's "reach" mode: arcs stay hidden until a country is
  // selected, unless the viewer explicitly asks to see every conflict at once.
  const [showAllConflicts, setShowAllConflicts] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadCountryGeo().then((geo) => {
      if (cancelled) return;
      setLonLat(geo.lonLat);
      setFeatures(geo.features);
      featuresRef.current = geo.features;
    });
    return () => { cancelled = true; };
  }, []);

  const filteredConflicts = useMemo(
    () => applyConflictFilters(conflicts, state.mapFilters),
    [conflicts, state.mapFilters]
  );
  const activeConflicts = useConflictFilter(filteredConflicts, timelineYear);
  const severityMap = useCountrySeverity(filteredConflicts, timelineYear);

  // Countries sharing an active conflict with the selection — the map's "spotlight":
  // selected + related stay bright, everyone else fades back.
  const relatedIds = useMemo(() => {
    const set = new Set();
    if (!selectedCountryId) return set;
    for (const c of activeConflicts) {
      const ids = c.involvedCountries || [];
      if (!ids.includes(selectedCountryId)) continue;
      for (const id of ids) if (id !== selectedCountryId) set.add(id);
    }
    return set;
  }, [activeConflicts, selectedCountryId]);

  // The globe's choropleth: countries painted by severity directly into the sphere's
  // texture, same rule as the 2D map's land fill ("Fill = severity"), same spotlight
  // fade when a country is selected.
  const texture = useMemo(() => {
    if (!features) return null;
    return renderCountryTexture(features, (alpha3) => {
      const severity = severityMap[alpha3] || 0;
      const base = severity > 0 ? severityColor(severity) : '#1b2328';
      const involved = !selectedCountryId || alpha3 === selectedCountryId || relatedIds.has(alpha3);
      return involved ? base : fade(base, 0.35);
    }, selectedCountryId);
  }, [features, severityMap, selectedCountryId, relatedIds]);

  // Arcs between conflict parties — same aggressor/defender/support logic and role
  // coloring as the 2D map's ConflictOverlay. Hidden by default; either a selected
  // country (reach mode, like the map) or "show all conflicts" reveals them.
  const arcs = useMemo(() => {
    if (!lonLat) return [];
    if (!showAllConflicts && !selectedCountryId) return [];

    const drawn = new Set();
    const result = [];
    for (const conflict of activeConflicts) {
      if (!showAllConflicts && !(conflict.involvedCountries || []).includes(selectedCountryId)) continue;

      const color = conflictColorForCountry(conflict, showAllConflicts ? null : selectedCountryId);
      let edges = buildConflictEdges(conflict, lonLat);
      if (!showAllConflicts) {
        edges = edges.filter((e) => e.from === selectedCountryId || e.to === selectedCountryId);
      }

      for (const { from, to, kind } of edges) {
        const key = `${conflict.id}:${from}:${to}`;
        if (drawn.has(key)) continue;
        drawn.add(key);
        result.push({
          coords: [lonLat[from], lonLat[to]],
          lineStyle: {
            width: Math.max(0.7, conflict.severity * 0.32),
            opacity: kind === 'support' ? 0.35 : (showAllConflicts ? 0.5 : 0.75),
            color,
          },
        });
      }
    }
    return result;
  }, [lonLat, activeConflicts, selectedCountryId, showAllConflicts]);

  // Create the chart once, mounted for the lifetime of this component.
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = echarts.init(containerRef.current, null, { renderer: 'canvas' });
    chartRef.current = chart;

    // The globe is one plain textured sphere — there's no per-country mesh to click,
    // so a country click is done by hand: cast a ray from the click through the
    // camera, find where it hits the sphere, convert that 3D point back to lon/lat,
    // then test which country polygon contains that point.
    //
    // This has to be a native DOM listener, not chart.getZr().on('click', ...):
    // echarts-gl's GL layer only dispatches a zrender click when its own picking
    // hits a registered object (e.g. a scatter3D point) — clicking the bare globe
    // mesh finds no such object, so no zrender event ever fires for it.
    let downX = 0;
    let downY = 0;
    const dom = containerRef.current;

    function handleMouseDown(e) {
      downX = e.offsetX;
      downY = e.offsetY;
    }

    function handleClick(e) {
      // Ignore clicks that end a drag-to-rotate gesture (same threshold LayerGL
      // itself uses for its own object picking, for consistent feel).
      const dx = e.offsetX - downX;
      const dy = e.offsetY - downY;
      if (Math.sqrt(dx * dx + dy * dy) > 20) return;

      const globeModel = chart.getModel().getComponent('globe');
      const coordSys = globeModel && globeModel.coordinateSystem;
      const geoFeatures = featuresRef.current;
      if (!coordSys || !geoFeatures) return;

      // ViewGL.castRay writes into (and returns) the `out` ray it's given rather
      // than creating one itself, so an actual Ray instance has to be passed in.
      const ray = new Ray();
      coordSys.viewGL.castRay(e.offsetX, e.offsetY, ray);
      const hit = ray.intersectSphere(GLOBE_CENTER, coordSys.radius);
      if (!hit) return; // clicked off the globe

      const [lng, lat] = coordSys.pointToData(hit.array);
      const found = geoFeatures.find(({ feature }) => feature && d3.geoContains(feature, [lng, lat]));
      if (!found?.alpha3) return; // ocean or an unmapped territory

      const id = found.alpha3;
      dispatch(id === selectedCountryIdRef.current
        ? { type: 'CLEAR_SELECTION' }
        : { type: 'SELECT_COUNTRY', payload: id });
    }

    // Capture phase: zrender's own canvas listener calls stopPropagation() on
    // every native event it handles, so a bubble-phase listener on this wrapper
    // div would never see the click. Capture runs before that, on the way down.
    dom.addEventListener('mousedown', handleMouseDown, true);
    dom.addEventListener('click', handleClick, true);

    const onResize = () => chart.resize();
    window.addEventListener('resize', onResize);
    return () => {
      dom.removeEventListener('mousedown', handleMouseDown, true);
      dom.removeEventListener('click', handleClick, true);
      window.removeEventListener('resize', onResize);
      chart.dispose();
      chartRef.current = null;
    };
  }, [dispatch]);

  // Push data updates without re-creating the chart/globe (keeps rotation smooth).
  //
  // echarts-gl's globe component re-runs its full render() — including reloading
  // baseTexture — on EVERY setOption call, not just ones that touch `globe`. Its
  // texture loader tags each image with a `__textureid__` the first time it's
  // used and caches the GPU texture by that id; on a cache HIT (i.e. the exact
  // same canvas seen again, which happens on every subsequent setOption here) it
  // skips the callback that re-enables the texture on the material, so the globe
  // goes blank white from the second setOption call onward. Deleting the tag
  // before every call forces a fresh (if wasteful) reload each time, which is the
  // only way found to keep the texture visible — see graphicGL.js's
  // Material.prototype.setTextureImage / loadTexture for the actual bug.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !texture) return;

    delete texture.__textureid__;

    chart.setOption({
      backgroundColor: 'transparent',
      globe: {
        baseTexture: texture,
        globeOuterRadius: 100,
        shading: 'lambert',
        light: {
          main: { intensity: 1.2, shadow: false },
          ambient: { intensity: 0.5 },
        },
        viewControl: {
          autoRotate: true,
          autoRotateSpeed: 4,
          distance: 190,
          // The baseTexture is a fixed-resolution raster (unlike the 2D map's vector
          // paths), so it blurs under enough magnification. Capping how close the
          // camera can get keeps zoom inside the range the texture can render crisply.
          minDistance: 120,
        },
      },
      series: [
        {
          type: 'lines3D',
          coordinateSystem: 'globe',
          effect: { show: true, trailWidth: 1.4, trailLength: 0.25, trailOpacity: 1 },
          blendMode: 'lighter',
          lineStyle: { opacity: 0.5 },
          data: arcs,
        },
      ],
    });
  }, [arcs, texture]);

  return (
    <div className={styles.globeContainer}>
      <div ref={containerRef} className={styles.globeCanvas} />
      {!texture && <div className={styles.globeLoading}>Loading globe…</div>}
      <div className={styles.globeControls}>
        <button
          className={`${styles.allConflictsBtn} ${showAllConflicts ? styles.allConflictsBtnActive : ''}`}
          onClick={() => setShowAllConflicts((v) => !v)}
        >
          {showAllConflicts ? 'Showing all conflicts' : 'Show all conflicts'}
        </button>
      </div>
      <div className={styles.globeNote}>Drag to rotate · scroll to zoom{!showAllConflicts && ' · click a country for its conflicts'}</div>
    </div>
  );
}
