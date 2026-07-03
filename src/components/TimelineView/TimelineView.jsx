import { useMemo, useRef, useState } from 'react';
import { useApp } from '../../context/AppContext';
import { isActiveAt, parseYear, formatDateRange } from '../../utils/dateUtils';
import { TYPE_COLORS, TYPE_LABELS, severityColor } from '../../utils/conflictColors';
import { TypeIcon } from '../../utils/typeIcons';
import SeverityGauge from '../common/SeverityGauge';
import NestedEvents from '../common/NestedEvents';
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

  // Events grouped by the year they occurred
  const eventsByYear = useMemo(() => {
    const byYear = new Map();
    for (const c of conflicts) {
      for (const e of c.events || []) {
        const y = parseYear(e.date);
        if (y == null) continue;
        if (!byYear.has(y)) byYear.set(y, []);
        byYear.get(y).push({ event: e, conflict: c });
      }
    }
    return byYear;
  }, [conflicts]);

  // One tick per eventful year, colored by its worst event — a "notable moments" ribbon
  const eventYears = useMemo(() => {
    const out = [];
    for (const [year, arr] of eventsByYear) {
      const maxSev = arr.reduce((m, x) => Math.max(m, x.event.severity || 0), 0);
      out.push({ year, maxSev });
    }
    return out;
  }, [eventsByYear]);

  const eventsThisYear = useMemo(
    () => [...(eventsByYear.get(timelineYear) || [])].sort((a, b) => (b.event.severity || 0) - (a.event.severity || 0)),
    [eventsByYear, timelineYear]
  );

  const activeNow = useMemo(
    () => conflicts
      .filter((c) => isActiveAt(c, timelineYear))
      .sort((a, b) => (b.severity || 0) - (a.severity || 0)),
    [conflicts, timelineYear]
  );

  const N = perYear.length;
  const barW = VB_W / N;

  const [hover, setHover] = useState(null);
  const peak = useMemo(
    () => perYear.reduce((a, b) => (b.count > a.count ? b : a), perYear[0] || { year: 0, count: 0 }),
    [perYear]
  );

  function yearFromEvent(e) {
    const rect = svgRef.current.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    const y = Math.round(MIN_YEAR + frac * (MAX_YEAR - MIN_YEAR));
    return Math.min(MAX_YEAR, Math.max(MIN_YEAR, y));
  }

  function handleHover(e) {
    const y = yearFromEvent(e);
    const d = perYear[y - MIN_YEAR];
    const evs = eventsByYear.get(y);
    setHover({ year: y, count: d ? d.count : 0, events: evs ? evs.length : 0, xPct: ((y - MIN_YEAR) / (MAX_YEAR - MIN_YEAR)) * 100 });
  }

  function setYear(y) {
    dispatch({ type: 'SET_TIMELINE_YEAR', payload: y });
  }

  function openOnMap(conflict) {
    dispatch({ type: 'OPEN_CONFLICT', payload: conflict.id });
  }

  // Open the conflict on the map AND park the timeline on the event's year so it pins/pulses
  function openEvent(conflict, event) {
    dispatch({ type: 'OPEN_CONFLICT', payload: conflict.id });
    const y = parseYear(event.date);
    if (y != null) dispatch({ type: 'SET_TIMELINE_YEAR', payload: y });
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
          role="img"
          aria-label={`Active conflicts each year from ${MIN_YEAR} to ${MAX_YEAR}, peaking near ${peak.count} around ${peak.year}. A ribbon of ticks marks years with notable events. Currently ${timelineYear} with ${activeNow.length} active and ${eventsThisYear.length} events. Click to pick a year.`}
          onClick={(e) => setYear(yearFromEvent(e))}
          onMouseMove={handleHover}
          onMouseLeave={() => setHover(null)}
        >
          {perYear.map((d, i) => {
            const h = (d.count / maxCount) * (VB_H - 18);
            const isCurrent = d.year === timelineYear;
            const isHover = hover && d.year === hover.year;
            return (
              <rect
                key={d.year}
                x={i * barW}
                y={VB_H - h}
                width={Math.max(barW * 0.9, 0.6)}
                height={h}
                fill={isCurrent ? '#82b8ab' : isHover ? '#4ade80' : '#263230'}
              />
            );
          })}
          {/* notable-events ribbon along the top: one tick per eventful year, colored by worst event */}
          {eventYears.map((ey) => {
            const i = ey.year - MIN_YEAR;
            const isCurrent = ey.year === timelineYear;
            return (
              <rect
                key={`ev-${ey.year}`}
                x={i * barW}
                y={0}
                width={Math.max(barW * 0.9, 0.8)}
                height={8}
                fill={severityColor(ey.maxSev)}
                opacity={isCurrent ? 1 : 0.72}
              />
            );
          })}
          {/* hovered-year line */}
          {hover && (
            <line
              x1={(hover.xPct / 100) * VB_W} y1={0}
              x2={(hover.xPct / 100) * VB_W} y2={VB_H}
              stroke="#82b8ab" strokeWidth={1} strokeDasharray="3 3" opacity={0.6}
              vectorEffect="non-scaling-stroke"
            />
          )}
          {/* current-year cursor */}
          <line x1={cursorX} y1={0} x2={cursorX} y2={VB_H} stroke="#56988a" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        </svg>
        {hover && (
          <div className={styles.chartTip} style={{ left: `${hover.xPct}%` }}>
            <strong>{hover.year}</strong> · {hover.count} active{hover.events > 0 ? ` · ${hover.events} event${hover.events === 1 ? '' : 's'}` : ''}
          </div>
        )}
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

      <div className={styles.scroll}>
        <div className={styles.section}>
          {activeNow.length === 0 && <div className={styles.empty}>No conflicts logged for {timelineYear}.</div>}
          {activeNow.map((c) => {
            const color = TYPE_COLORS[c.type] || '#94a3b8';
            const parties = (c.involvedCountries || []).map((id) => nameByCountry[id] || id);
            const yearEvents = (c.events || []).filter((e) => parseYear(e.date) === timelineYear);
            return (
              <div key={c.id} className={styles.rowWrap}>
                <button className={styles.row} onClick={() => openOnMap(c)} style={{ borderLeftColor: color }}>
                  <span className={styles.rowGlyph} style={{ background: color + '22', color }}>
                    <TypeIcon type={c.type} size={15} aria-hidden="true" />
                  </span>
                  <div className={styles.rowMain}>
                    <div className={styles.rowTitle}>{c.title}{c.ongoing && <span className={styles.ongoing}>ONGOING</span>}</div>
                    <div className={styles.rowParties}>{parties.join(' · ')}</div>
                  </div>
                  <div className={styles.rowMeta}>
                    <span className={styles.type} style={{ color }}>{TYPE_LABELS[c.type] || c.type}</span>
                    <span className={styles.dates}>{formatDateRange(c.startDate, c.endDate, c.ongoing)}</span>
                    <SeverityGauge severity={c.severity} />
                  </div>
                </button>
                {yearEvents.length > 0 && <NestedEvents events={yearEvents} onOpen={(ev) => openEvent(c, ev)} />}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
