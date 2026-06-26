import { useMemo, useRef } from 'react';
import { useApp } from '../../context/AppContext';
import { isActiveAt, parseYear, formatDateRange } from '../../utils/dateUtils';
import { TYPE_COLORS, TYPE_LABELS } from '../../utils/conflictColors';
import styles from './TimelineView.module.css';

const MIN_YEAR = 1490;
const MAX_YEAR = 2026;
const VB_W = 1000;
const VB_H = 200;

export default function TimelineView() {
  const { state, dispatch } = useApp();
  const { conflicts, countries, timelineYear } = state;
  const svgRef = useRef(null);

  const nameByCountry = useMemo(() => {
    const m = {};
    for (const c of countries) m[c.id] = c.name;
    return m;
  }, [countries]);

  // Active-conflict count per year
  const { perYear, maxCount } = useMemo(() => {
    const years = [];
    let max = 0;
    for (let y = MIN_YEAR; y <= MAX_YEAR; y++) {
      const count = conflicts.reduce((n, c) => n + (isActiveAt(c, y) ? 1 : 0), 0);
      years.push({ year: y, count });
      if (count > max) max = count;
    }
    return { perYear: years, maxCount: Math.max(1, max) };
  }, [conflicts]);

  const activeNow = useMemo(
    () => conflicts
      .filter((c) => isActiveAt(c, timelineYear))
      .sort((a, b) => (b.severity || 0) - (a.severity || 0)),
    [conflicts, timelineYear]
  );

  const N = perYear.length;
  const barW = VB_W / N;

  function yearFromEvent(e) {
    const rect = svgRef.current.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    const y = Math.round(MIN_YEAR + frac * (MAX_YEAR - MIN_YEAR));
    return Math.min(MAX_YEAR, Math.max(MIN_YEAR, y));
  }

  function setYear(y) {
    dispatch({ type: 'SET_TIMELINE_YEAR', payload: y });
  }

  function openOnMap(conflict) {
    const firstParty = conflict.parties?.[0]?.countryId;
    if (firstParty) dispatch({ type: 'SELECT_COUNTRY', payload: firstParty });
    dispatch({ type: 'FOCUS_CONFLICT', payload: conflict.id });
    dispatch({ type: 'SET_VIEW', payload: 'map' });
  }

  const cursorX = ((timelineYear - MIN_YEAR) / (MAX_YEAR - MIN_YEAR)) * VB_W;
  const axisYears = [1500, 1600, 1700, 1800, 1900, 2000];

  return (
    <div className={styles.view}>
      <div className={styles.headerRow}>
        <h1 className={styles.heading}>Timeline</h1>
        <div className={styles.yearBox}>
          <span className={styles.year}>{timelineYear}</span>
          <span className={styles.activeCount}>{activeNow.length} active</span>
        </div>
      </div>

      <div className={styles.chartWrap}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${VB_W} ${VB_H}`}
          preserveAspectRatio="none"
          className={styles.chart}
          onClick={(e) => setYear(yearFromEvent(e))}
        >
          {perYear.map((d, i) => {
            const h = (d.count / maxCount) * (VB_H - 10);
            const isCurrent = d.year === timelineYear;
            return (
              <rect
                key={d.year}
                x={i * barW}
                y={VB_H - h}
                width={Math.max(barW * 0.9, 0.6)}
                height={h}
                fill={isCurrent ? '#6ee7b7' : '#2a4a42'}
              />
            );
          })}
          {/* current-year cursor */}
          <line x1={cursorX} y1={0} x2={cursorX} y2={VB_H} stroke="#34d399" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        </svg>
        {/* axis labels */}
        <div className={styles.axis}>
          {axisYears.map((y) => (
            <span
              key={y}
              className={styles.axisLabel}
              style={{ left: `${((y - MIN_YEAR) / (MAX_YEAR - MIN_YEAR)) * 100}%` }}
            >
              {y}
            </span>
          ))}
        </div>
      </div>

      <input
        type="range"
        min={MIN_YEAR}
        max={MAX_YEAR}
        value={timelineYear}
        onChange={(e) => setYear(Number(e.target.value))}
        className={styles.slider}
      />

      <div className={styles.listHeader}>
        Active in {timelineYear} — {activeNow.length} conflict{activeNow.length === 1 ? '' : 's'}
      </div>
      <div className={styles.list}>
        {activeNow.length === 0 && <div className={styles.empty}>No conflicts logged for {timelineYear}.</div>}
        {activeNow.map((c) => {
          const color = TYPE_COLORS[c.type] || '#94a3b8';
          const parties = (c.involvedCountries || []).map((id) => nameByCountry[id] || id);
          return (
            <button key={c.id} className={styles.row} onClick={() => openOnMap(c)} style={{ borderLeftColor: color }}>
              <div className={styles.rowMain}>
                <div className={styles.rowTitle}>{c.title}{c.ongoing && <span className={styles.ongoing}>ONGOING</span>}</div>
                <div className={styles.rowParties}>{parties.join(' · ')}</div>
              </div>
              <div className={styles.rowMeta}>
                <span className={styles.type} style={{ color }}>{TYPE_LABELS[c.type] || c.type}</span>
                <span className={styles.dates}>{formatDateRange(c.startDate, c.endDate, c.ongoing)}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
