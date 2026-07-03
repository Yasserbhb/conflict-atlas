import { useMemo } from 'react';
import { useApp } from '../../context/AppContext';
import { TYPE_LABELS, TYPE_COLORS, severityColor } from '../../utils/conflictColors';
import { SEVERITY_LEVELS } from '../../utils/taxonomy';
import { KIND_META } from '../../utils/eventKinds';
import { parseYear } from '../../utils/dateUtils';
import styles from './StatsView.module.css';

const REGION_ORDER = ['Africa', 'Asia', 'Europe', 'Americas', 'Oceania'];

export default function StatsView() {
  const { state, dispatch } = useApp();
  const { conflicts, countries } = state;

  const nameByCountry = useMemo(() => {
    const m = {};
    for (const c of countries) m[c.id] = c.name;
    return m;
  }, [countries]);
  const regionByCountry = useMemo(() => {
    const m = {};
    for (const c of countries) m[c.id] = c.region;
    return m;
  }, [countries]);

  const stats = useMemo(() => {
    const involved = new Set();
    const byType = {};
    const byCountry = {};
    const bySeverity = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    const byRegion = {};
    const byKind = {};
    const eraCount = {};
    let ongoing = 0, genocides = 0, totalEvents = 0;
    let minYear = Infinity, maxYear = -Infinity;
    const documented = [];

    for (const c of conflicts) {
      if (c.ongoing) ongoing++;
      if (c.type === 'genocide') genocides++;
      byType[c.type] = (byType[c.type] || 0) + 1;
      if (c.severity) bySeverity[c.severity] = (bySeverity[c.severity] || 0) + 1;

      const regions = new Set();
      for (const id of c.involvedCountries || []) {
        involved.add(id);
        byCountry[id] = (byCountry[id] || 0) + 1;
        if (regionByCountry[id]) regions.add(regionByCountry[id]);
      }
      for (const r of regions) byRegion[r] = (byRegion[r] || 0) + 1;

      const sy = parseYear(c.startDate);
      if (sy != null) {
        minYear = Math.min(minYear, sy);
        maxYear = Math.max(maxYear, sy);
        const bucket = Math.floor(sy / 50) * 50;
        eraCount[bucket] = (eraCount[bucket] || 0) + 1;
      }

      const nEvents = (c.events || []).length;
      if (nEvents) {
        totalEvents += nEvents;
        documented.push([c.id, c.title, c.type, nEvents]);
        for (const e of c.events) byKind[e.kind] = (byKind[e.kind] || 0) + 1;
      }
    }

    // era buckets spanning the real data range
    const firstB = Math.floor((isFinite(minYear) ? minYear : 1500) / 50) * 50;
    const lastB = Math.floor((isFinite(maxYear) ? maxYear : 2000) / 50) * 50;
    const eraList = [];
    for (let y = firstB; y <= lastB; y += 50) eraList.push([y, eraCount[y] || 0]);

    return {
      total: conflicts.length,
      ongoing, genocides, totalEvents,
      involvedCount: involved.size,
      minYear: isFinite(minYear) ? minYear : null,
      maxYear: isFinite(maxYear) ? maxYear : null,
      typeList: Object.entries(byType).sort((a, b) => b[1] - a[1]),
      countryList: Object.entries(byCountry).sort((a, b) => b[1] - a[1]).slice(0, 10),
      severityList: [5, 4, 3, 2, 1].map((s) => [s, bySeverity[s] || 0]),
      regionList: REGION_ORDER.map((r) => [r, byRegion[r] || 0]).filter((x) => x[1] > 0),
      kindList: Object.entries(byKind).sort((a, b) => b[1] - a[1]),
      eraList,
      documentedList: documented.sort((a, b) => b[3] - a[3]).slice(0, 8),
    };
  }, [conflicts, regionByCountry]);

  const max = (list, i = 1) => Math.max(1, ...list.map((x) => x[i]));

  return (
    <div className={styles.view}>
      <div className={styles.head}>
        <h1 className={styles.heading}>The atlas at a glance</h1>
        {stats.minYear && (
          <p className={styles.sub}>
            {stats.total} conflicts · {stats.totalEvents} events · {stats.minYear}–{stats.maxYear}
          </p>
        )}
      </div>

      <div className={styles.cards}>
        <Stat label="Conflicts logged" value={stats.total} />
        <Stat label="Ongoing now" value={stats.ongoing} accent="var(--danger)" />
        <Stat label="Events logged" value={stats.totalEvents} accent="var(--accent-light)" />
        <Stat label="Countries involved" value={stats.involvedCount} accent="#7fb0d6" />
        <Stat label="Genocides" value={stats.genocides} accent="#8f2f46" />
      </div>

      <div className={styles.grid}>
        <Panel title="By type">
          {stats.typeList.map(([t, n]) => (
            <Bar key={t} label={TYPE_LABELS[t] || t} value={n} max={max(stats.typeList)} color={TYPE_COLORS[t]} />
          ))}
        </Panel>

        <Panel title="By severity">
          {stats.severityList.map(([s, n]) => (
            <Bar key={s} label={SEVERITY_LEVELS[s - 1]?.label || `Level ${s}`} value={n} max={max(stats.severityList)} color={severityColor(s)} />
          ))}
        </Panel>

        <Panel title="By region">
          {stats.regionList.map(([r, n]) => (
            <Bar key={r} label={r} value={n} max={max(stats.regionList)} color="#56988a" />
          ))}
        </Panel>

        <Panel title="Conflicts started, by era">
          {stats.eraList.map(([y, n]) => (
            <Bar key={y} label={`${y}s`} value={n} max={max(stats.eraList)} color="#c17d3e" />
          ))}
        </Panel>

        <Panel title="Events by kind">
          {stats.kindList.map(([k, n]) => (
            <Bar key={k} label={KIND_META[k]?.label || k} value={n} max={max(stats.kindList)} color={KIND_META[k]?.color || '#82b8ab'} />
          ))}
        </Panel>

        <Panel title="Most-involved countries" hint="click to open on the map">
          {stats.countryList.map(([id, n]) => (
            <Bar
              key={id}
              label={nameByCountry[id] || id}
              value={n}
              max={max(stats.countryList)}
              color="#7fb0d6"
              onClick={() => { dispatch({ type: 'SELECT_COUNTRY', payload: id }); dispatch({ type: 'SET_VIEW', payload: 'map' }); }}
            />
          ))}
        </Panel>

        <Panel title="Most-documented conflicts" hint="click to open" wide>
          {stats.documentedList.map(([id, title, type, n]) => (
            <Bar
              key={id}
              label={title}
              value={n}
              max={max(stats.documentedList, 3)}
              color={TYPE_COLORS[type] || '#82b8ab'}
              onClick={() => dispatch({ type: 'OPEN_CONFLICT', payload: id })}
            />
          ))}
        </Panel>
      </div>
    </div>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div className={styles.card}>
      <span className={styles.cardBar} style={{ background: accent || 'var(--text-muted)' }} />
      <div className={styles.cardValue} style={accent ? { color: accent } : undefined}>{value}</div>
      <div className={styles.cardLabel}>{label}</div>
    </div>
  );
}

function Panel({ title, hint, wide, children }) {
  return (
    <div className={`${styles.panel} ${wide ? styles.wide : ''}`}>
      <div className={styles.panelHead}>
        <span className={styles.panelTitle}>{title}</span>
        {hint && <span className={styles.panelHint}>{hint}</span>}
      </div>
      <div className={styles.bars}>{children}</div>
    </div>
  );
}

function Bar({ label, value, max, color, onClick }) {
  const pct = Math.max(2, (value / max) * 100);
  const interactive = !!onClick;
  return (
    <div
      className={`${styles.barRow} ${interactive ? styles.clickable : ''}`}
      onClick={onClick}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-label={interactive ? `${label}, ${value} — open` : `${label}: ${value}`}
      onKeyDown={interactive ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } } : undefined}
      title={`${label}: ${value}`}
    >
      <span className={styles.barLabel}>{label}</span>
      <span className={styles.barTrack}>
        <span className={styles.barFill} style={{ width: `${pct}%`, background: color || '#7fb0d6' }} />
      </span>
      <span className={styles.barValue}>{value}</span>
    </div>
  );
}
