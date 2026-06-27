import { useState, useMemo } from 'react';
import { useApp } from '../../context/AppContext';
import { TYPE_LABELS, TYPE_COLORS, CONFLICT_TYPES } from '../../utils/conflictColors';
import { formatDateRange, parseYear } from '../../utils/dateUtils';
import styles from './ConflictsView.module.css';

const REGIONS = ['Africa', 'Americas', 'Asia', 'Europe', 'Oceania'];

const SORTS = {
  newest: 'Newest first',
  oldest: 'Oldest first',
  severity: 'Severity (high→low)',
  title: 'Title (A–Z)',
};

export default function ConflictsView() {
  const { state, dispatch } = useApp();
  const { conflicts, countries } = state;

  const [search, setSearch] = useState('');
  const [type, setType] = useState('all');
  const [region, setRegion] = useState('all');
  const [minSeverity, setMinSeverity] = useState(1);
  const [ongoingOnly, setOngoingOnly] = useState(false);
  const [sortBy, setSortBy] = useState('newest');

  const regionByCountry = useMemo(() => {
    const m = {};
    for (const c of countries) m[c.id] = c.region;
    return m;
  }, [countries]);

  const nameByCountry = useMemo(() => {
    const m = {};
    for (const c of countries) m[c.id] = c.name;
    return m;
  }, [countries]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let list = conflicts.filter((c) => {
      if (type !== 'all' && c.type !== type) return false;
      if (ongoingOnly && !c.ongoing) return false;
      if ((c.severity || 0) < minSeverity) return false;
      if (region !== 'all') {
        const inRegion = (c.involvedCountries || []).some((id) => regionByCountry[id] === region);
        if (!inRegion) return false;
      }
      if (q) {
        const hay = [
          c.title,
          c.description,
          ...(c.tags || []),
          ...(c.involvedCountries || []).map((id) => nameByCountry[id] || ''),
        ].join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    list = [...list].sort((a, b) => {
      switch (sortBy) {
        case 'oldest': return (parseYear(a.startDate) || 0) - (parseYear(b.startDate) || 0);
        case 'severity': return (b.severity || 0) - (a.severity || 0);
        case 'title': return a.title.localeCompare(b.title);
        case 'newest':
        default: return (parseYear(b.startDate) || 0) - (parseYear(a.startDate) || 0);
      }
    });
    return list;
  }, [conflicts, search, type, region, minSeverity, ongoingOnly, sortBy, regionByCountry, nameByCountry]);

  function openOnMap(conflict) {
    // Opens the conflict detail panel, role-colors the map, and moves the
    // timeline into the conflict's window — all handled by the reducer.
    dispatch({ type: 'OPEN_CONFLICT', payload: conflict.id });
  }

  return (
    <div className={styles.view}>
      <div className={styles.toolbar}>
        <div className={styles.toolbarTop}>
          <h1 className={styles.heading}>Conflicts</h1>
          <span className={styles.count}>{filtered.length} of {conflicts.length}</span>
        </div>
        <div className={styles.controls}>
          <input
            className={styles.search}
            placeholder="Search title, country, tag…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select className={styles.select} value={type} onChange={(e) => setType(e.target.value)}>
            <option value="all">All types</option>
            {CONFLICT_TYPES.map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
          </select>
          <select className={styles.select} value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="all">All regions</option>
            {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <select className={styles.select} value={minSeverity} onChange={(e) => setMinSeverity(Number(e.target.value))}>
            <option value={1}>Any severity</option>
            <option value={3}>Severity 3+</option>
            <option value={4}>Severity 4+</option>
            <option value={5}>Severity 5 only</option>
          </select>
          <label className={styles.checkbox}>
            <input type="checkbox" checked={ongoingOnly} onChange={(e) => setOngoingOnly(e.target.checked)} />
            Ongoing
          </label>
          <select className={styles.select} value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            {Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      </div>

      <div className={styles.list}>
        {filtered.length === 0 && <div className={styles.empty}>No conflicts match your filters.</div>}
        {filtered.map((c) => {
          const color = TYPE_COLORS[c.type] || '#94a3b8';
          const parties = (c.involvedCountries || []).map((id) => nameByCountry[id] || id);
          return (
            <button key={c.id} className={styles.row} onClick={() => openOnMap(c)} style={{ borderLeftColor: color }}>
              <div className={styles.rowMain}>
                <div className={styles.rowTitle}>
                  {c.title}
                  {c.ongoing && <span className={styles.ongoing}>ONGOING</span>}
                </div>
                <div className={styles.rowParties}>{parties.join(' · ')}</div>
              </div>
              <div className={styles.rowMeta}>
                <span className={styles.type} style={{ color }}>{TYPE_LABELS[c.type] || c.type}</span>
                <span className={styles.dates}>{formatDateRange(c.startDate, c.endDate, c.ongoing)}</span>
                <span className={styles.severity} title={`Severity ${c.severity}`}>{'◆'.repeat(c.severity || 0)}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
