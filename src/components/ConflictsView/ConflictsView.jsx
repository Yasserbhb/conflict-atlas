import { useState, useMemo } from 'react';
import { ChevronDown } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { TYPE_LABELS, TYPE_COLORS, CONFLICT_TYPES } from '../../utils/conflictColors';
import { formatDateRange, parseYear } from '../../utils/dateUtils';
import { TypeIcon } from '../../utils/typeIcons';
import SeverityGauge from '../common/SeverityGauge';
import NestedEvents from '../common/NestedEvents';
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
  const [expanded, setExpanded] = useState(() => new Set());

  const q = search.trim().toLowerCase();

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
          ...(c.events || []).map((e) => e.title),
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
  }, [conflicts, q, type, region, minSeverity, ongoingOnly, sortBy, regionByCountry, nameByCountry]);

  function toggle(id) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function openOnMap(conflict) {
    dispatch({ type: 'OPEN_CONFLICT', payload: conflict.id });
  }

  // Open the conflict on the map and park the timeline on the event's year
  function openEvent(conflict, event) {
    dispatch({ type: 'OPEN_CONFLICT', payload: conflict.id });
    const y = parseYear(event.date);
    if (y != null) dispatch({ type: 'SET_TIMELINE_YEAR', payload: y });
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
            placeholder="Search title, country, tag, event…"
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
          const events = c.events || [];
          const hasEvents = events.length > 0;
          // auto-expand when the search matched one of this conflict's events
          const matchedEvent = q.length >= 2 && !c.title.toLowerCase().includes(q) && events.some((e) => e.title.toLowerCase().includes(q));
          const isOpen = hasEvents && (expanded.has(c.id) || matchedEvent);

          return (
            <div key={c.id} className={styles.rowWrap}>
              <div className={styles.row} style={{ borderLeftColor: color }}>
                <button className={styles.rowClick} onClick={() => openOnMap(c)}>
                  <span className={styles.rowGlyph} style={{ background: color + '22', color }}>
                    <TypeIcon type={c.type} size={15} aria-hidden="true" />
                  </span>
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
                    <SeverityGauge severity={c.severity} />
                  </div>
                </button>
                {hasEvents && (
                  <button
                    className={styles.expandBtn}
                    onClick={() => toggle(c.id)}
                    aria-expanded={isOpen}
                    aria-label={isOpen ? 'Hide events' : `Show ${events.length} events`}
                  >
                    <span className={styles.evCount}>{events.length}</span>
                    <ChevronDown size={14} className={isOpen ? styles.chevOpen : styles.chev} aria-hidden="true" />
                  </button>
                )}
              </div>

              {isOpen && (
                <NestedEvents events={events} onOpen={(ev) => openEvent(c, ev)} highlightQuery={q} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
