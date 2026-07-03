import { useState, useMemo } from 'react';
import { Search } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { parseYear } from '../../utils/dateUtils';
import { TYPE_LABELS } from '../../utils/conflictColors';
import { TypeIcon } from '../../utils/typeIcons';
import { kindMeta } from '../../utils/eventKinds';
import styles from './SearchBar.module.css';

export default function SearchBar() {
  const { state, dispatch } = useApp();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);

  const q = query.trim().toLowerCase();
  const results = useMemo(() => {
    if (q.length < 2) return { countries: [], conflicts: [], events: [] };
    const countries = state.countries.filter((c) =>
      c.name.toLowerCase().includes(q) || (c.aliases || []).some((a) => a.toLowerCase().includes(q))
    ).slice(0, 4);
    const conflicts = state.conflicts.filter((c) =>
      c.title.toLowerCase().includes(q) || (c.tags || []).some((t) => t.toLowerCase().includes(q))
    ).slice(0, 5);
    const events = [];
    for (const c of state.conflicts) {
      for (const e of c.events || []) {
        if (e.title.toLowerCase().includes(q)) events.push({ event: e, conflict: c });
      }
    }
    events.sort((a, b) => (b.event.severity || 0) - (a.event.severity || 0));
    return { countries, conflicts, events: events.slice(0, 6) };
  }, [q, state.countries, state.conflicts]);

  const hasResults = results.countries.length || results.conflicts.length || results.events.length;

  function close() { setQuery(''); setOpen(false); }
  function pickCountry(id) { dispatch({ type: 'SELECT_COUNTRY', payload: id }); dispatch({ type: 'SET_VIEW', payload: 'map' }); close(); }
  function pickConflict(id) { dispatch({ type: 'OPEN_CONFLICT', payload: id }); close(); }
  function pickEvent(conflict, event) {
    dispatch({ type: 'OPEN_CONFLICT', payload: conflict.id });
    const y = parseYear(event.date);
    if (y != null) dispatch({ type: 'SET_TIMELINE_YEAR', payload: y });
    close();
  }

  return (
    <div className={styles.wrapper}>
      <Search size={13} strokeWidth={2} className={styles.searchIcon} aria-hidden="true" />
      <input
        className={styles.input}
        placeholder="Search country, conflict, event…"
        aria-label="Search countries, conflicts and events"
        value={query}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && hasResults ? (
        <div className={styles.dropdown}>
          {results.countries.length > 0 && (
            <div className={styles.group}>
              <div className={styles.groupLabel}>Countries</div>
              {results.countries.map((c) => (
                <button key={c.id} type="button" className={styles.option} onMouseDown={() => pickCountry(c.id)}>
                  <span className={styles.name}>{c.name}</span>
                  <span className={styles.region}>{c.region}</span>
                </button>
              ))}
            </div>
          )}
          {results.conflicts.length > 0 && (
            <div className={styles.group}>
              <div className={styles.groupLabel}>Conflicts</div>
              {results.conflicts.map((c) => (
                <button key={c.id} type="button" className={styles.option} onMouseDown={() => pickConflict(c.id)}>
                  <span className={styles.optMain}>
                    <TypeIcon type={c.type} size={13} aria-hidden="true" />
                    <span className={styles.name}>{c.title}</span>
                  </span>
                  <span className={styles.region}>{TYPE_LABELS[c.type] || c.type}</span>
                </button>
              ))}
            </div>
          )}
          {results.events.length > 0 && (
            <div className={styles.group}>
              <div className={styles.groupLabel}>Events</div>
              {results.events.map(({ event, conflict }, i) => {
                const m = kindMeta(event.kind);
                const Icon = m.Icon;
                return (
                  <button key={event.id || i} type="button" className={styles.option} onMouseDown={() => pickEvent(conflict, event)}>
                    <span className={styles.optMain}>
                      <Icon size={13} style={{ color: m.color, flexShrink: 0 }} aria-hidden="true" />
                      <span className={styles.optText}>
                        <span className={styles.name}>{event.title}</span>
                        <span className={styles.sub}>{conflict.title}</span>
                      </span>
                    </span>
                    <span className={styles.region}>{event.date}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      ) : (open && q.length >= 2 ? (
        <div className={styles.dropdown}><div className={styles.noResults}>No matches for “{query}”.</div></div>
      ) : null)}
    </div>
  );
}
