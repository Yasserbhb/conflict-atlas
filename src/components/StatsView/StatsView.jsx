import { useMemo } from 'react';
import { useApp } from '../../context/AppContext';
import { TYPE_LABELS, TYPE_COLORS, severityColor } from '../../utils/conflictColors';
import { parseYear } from '../../utils/dateUtils';
import styles from './StatsView.module.css';

export default function StatsView() {
  const { state, dispatch } = useApp();
  const { conflicts, countries } = state;

  const nameByCountry = useMemo(() => {
    const m = {};
    for (const c of countries) m[c.id] = c.name;
    return m;
  }, [countries]);

  const stats = useMemo(() => {
    const ongoing = conflicts.filter((c) => c.ongoing).length;
    const genocides = conflicts.filter((c) => c.type === 'genocide').length;

    const involved = new Set();
    const byType = {};
    const byCountry = {};
    const bySeverity = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    const byEra = {};

    // 50-year buckets from 1500
    const eras = [];
    for (let y = 1500; y <= 2000; y += 50) { eras.push(y); byEra[y] = 0; }

    for (const c of conflicts) {
      byType[c.type] = (byType[c.type] || 0) + 1;
      if (c.severity) bySeverity[c.severity] = (bySeverity[c.severity] || 0) + 1;
      for (const id of c.involvedCountries || []) {
        involved.add(id);
        byCountry[id] = (byCountry[id] || 0) + 1;
      }
      const sy = parseYear(c.startDate);
      if (sy != null) {
        const bucket = Math.min(2000, Math.max(1500, Math.floor(sy / 50) * 50));
        byEra[bucket] = (byEra[bucket] || 0) + 1;
      }
    }

    const typeList = Object.entries(byType).sort((a, b) => b[1] - a[1]);
    const countryList = Object.entries(byCountry).sort((a, b) => b[1] - a[1]).slice(0, 12);
    const severityList = [5, 4, 3, 2, 1].map((s) => [s, bySeverity[s] || 0]);
    const eraList = eras.map((y) => [y, byEra[y] || 0]);

    return {
      total: conflicts.length,
      ongoing,
      genocides,
      involvedCount: involved.size,
      typeList,
      countryList,
      severityList,
      eraList,
    };
  }, [conflicts]);

  const maxType = Math.max(1, ...stats.typeList.map((t) => t[1]));
  const maxCountry = Math.max(1, ...stats.countryList.map((t) => t[1]));
  const maxEra = Math.max(1, ...stats.eraList.map((t) => t[1]));
  const maxSev = Math.max(1, ...stats.severityList.map((t) => t[1]));

  return (
    <div className={styles.view}>
      <h1 className={styles.heading}>Stats</h1>

      <div className={styles.cards}>
        <Stat label="Conflicts logged" value={stats.total} />
        <Stat label="Ongoing now" value={stats.ongoing} accent="#ef4444" />
        <Stat label="Genocides" value={stats.genocides} accent="#7c3aed" />
        <Stat label="Countries involved" value={stats.involvedCount} accent="#3b82f6" />
      </div>

      <div className={styles.grid}>
        <Panel title="By type">
          {stats.typeList.map(([t, n]) => (
            <Bar key={t} label={TYPE_LABELS[t] || t} value={n} max={maxType} color={TYPE_COLORS[t]} />
          ))}
        </Panel>

        <Panel title="Most-involved countries">
          {stats.countryList.map(([id, n]) => (
            <Bar
              key={id}
              label={nameByCountry[id] || id}
              value={n}
              max={maxCountry}
              color="#3b82f6"
              onClick={() => { dispatch({ type: 'SELECT_COUNTRY', payload: id }); dispatch({ type: 'SET_VIEW', payload: 'map' }); }}
            />
          ))}
        </Panel>

        <Panel title="Conflicts started, by era">
          {stats.eraList.map(([y, n]) => (
            <Bar key={y} label={`${y}s`} value={n} max={maxEra} color="#f59e0b" />
          ))}
        </Panel>

        <Panel title="By severity">
          {stats.severityList.map(([s, n]) => (
            <Bar key={s} label={`${'◆'.repeat(s)}`} value={n} max={maxSev} color={severityColor(s)} />
          ))}
        </Panel>
      </div>
    </div>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardValue} style={accent ? { color: accent } : undefined}>{value}</div>
      <div className={styles.cardLabel}>{label}</div>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <div className={styles.panel}>
      <div className={styles.panelTitle}>{title}</div>
      <div className={styles.bars}>{children}</div>
    </div>
  );
}

function Bar({ label, value, max, color, onClick }) {
  const pct = (value / max) * 100;
  const interactive = !!onClick;
  return (
    <div
      className={`${styles.barRow} ${interactive ? styles.clickable : ''}`}
      onClick={onClick}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-label={interactive ? `${label}, ${value} — open on map` : `${label}: ${value}`}
      onKeyDown={interactive ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } } : undefined}
    >
      <span className={styles.barLabel}>{label}</span>
      <span className={styles.barTrack}>
        <span className={styles.barFill} style={{ width: `${pct}%`, background: color || '#3b82f6' }} />
      </span>
      <span className={styles.barValue}>{value}</span>
    </div>
  );
}
