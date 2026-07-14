import { useState, useEffect, useMemo } from 'react';
import { useApp } from '../../context/AppContext';
import { getNotesByCountry } from '../../db/queries';
import { useCountryConflicts } from '../../hooks/useConflictFilter';
import { TYPE_LABELS, TYPE_COLORS, ROLE_LABELS, roleColor } from '../../utils/conflictColors';
import { X, Crosshair, Network } from 'lucide-react';
import { formatDateRange, applyConflictFilters } from '../../utils/dateUtils';
import { flagEmoji } from '../../utils/flags';
import { TypeIcon } from '../../utils/typeIcons';
import SeverityGauge from '../common/SeverityGauge';
import styles from './SidePanel.module.css';

const TABS = ['Conflicts', 'Territories', 'Notes'];

export default function SidePanel() {
  const { state, dispatch } = useApp();
  const { selectedCountryId, focusedConflictId, conflicts: allStateConflicts, timelineYear, mode, countries } = state;
  const [tab, setTab] = useState('Conflicts');
  const [notes, setNotes] = useState([]);

  const country = countries.find((c) => c.id === selectedCountryId);

  // Respect the map filter bar so the panel matches what's shown on the map
  const conflicts = useMemo(
    () => applyConflictFilters(allStateConflicts, state.mapFilters),
    [allStateConflicts, state.mapFilters]
  );
  const allConflicts = useCountryConflicts(conflicts, selectedCountryId, null);
  const activeConflicts = allConflicts.filter((c) => {
    const sy = parseInt(String(c.startDate).substring(0, 4));
    const ey = c.endDate ? parseInt(String(c.endDate).substring(0, 4)) : null;
    return sy <= timelineYear && (c.ongoing || ey === null || ey >= timelineYear);
  });
  const territories = allConflicts.filter((c) => ['occupation','disputed_territory'].includes(c.type));

  useEffect(() => {
    if (!selectedCountryId) return;
    let cancelled = false;
    getNotesByCountry(selectedCountryId)
      .then((n) => { if (!cancelled) setNotes(n); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [selectedCountryId]);

  if (!selectedCountryId || !country) return null;

  // Related countries: all countries that share any conflict
  const relatedIds = new Set();
  for (const c of allConflicts) {
    for (const id of c.involvedCountries || []) {
      if (id !== selectedCountryId) relatedIds.add(id);
    }
  }
  const relatedCountries = [...relatedIds].map((id) => countries.find((c) => c.id === id)).filter(Boolean);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div>
          <div className={styles.countryName}>{country.name}</div>
          <div className={styles.countryMeta}>{country.region} · {allConflicts.length} conflicts recorded</div>
        </div>
        <button
          className={styles.closeBtn}
          aria-label="Close panel"
          onClick={() => dispatch({ type: 'CLEAR_SELECTION' })}
        ><X size={15} strokeWidth={2.2} aria-hidden="true" /></button>
      </div>

      <div className={styles.tabs}>
        {TABS.map((t) => (
          <button
            key={t}
            className={`${styles.tab} ${tab === t ? styles.activeTab : ''}`}
            onClick={() => setTab(t)}
          >
            {t}
            {t === 'Conflicts' && <span className={styles.badge}>{activeConflicts.length}</span>}
            {t === 'Territories' && territories.length > 0 && <span className={styles.badge}>{territories.length}</span>}
            {t === 'Notes' && notes.length > 0 && <span className={styles.badge}>{notes.length}</span>}
          </button>
        ))}
      </div>

      <div className={styles.body}>
        {tab === 'Conflicts' && (
          <>
            {activeConflicts.length === 0 && (
              <div className={styles.empty}>No active conflicts in {timelineYear}</div>
            )}
            {activeConflicts.map((c) => (
              <ConflictCard
                key={c.id}
                conflict={c}
                mode={mode}
                onEdit={() => dispatch({ type: 'OPEN_EDIT', payload: { kind: 'conflict', data: c } })}
                countries={countries}
                selectedId={selectedCountryId}
                isFocused={focusedConflictId === c.id}
                onFocus={() => dispatch({ type: 'OPEN_CONFLICT', payload: c.id })}
              />
            ))}
          </>
        )}

        {tab === 'Territories' && (
          <>
            {territories.length === 0 && <div className={styles.empty}>No territorial disputes recorded</div>}
            {territories.map((c) => (
              <ConflictCard
                key={c.id}
                conflict={c}
                mode={mode}
                onEdit={() => dispatch({ type: 'OPEN_EDIT', payload: { kind: 'conflict', data: c } })}
                countries={countries}
                selectedId={selectedCountryId}
                isFocused={focusedConflictId === c.id}
                onFocus={() => dispatch({ type: 'OPEN_CONFLICT', payload: c.id })}
              />
            ))}
          </>
        )}

        {tab === 'Notes' && (
          <>
            {mode === 'edit' && (
              <button
                className={styles.addNoteBtn}
                onClick={() => dispatch({
                  type: 'OPEN_EDIT',
                  payload: { kind: 'note', data: { countryId: selectedCountryId } }
                })}
              >
                + Add Note
              </button>
            )}
            {notes.length === 0 && <div className={styles.empty}>No notes yet. Switch to Edit mode to add one.</div>}
            {notes.map((n) => (
              <NoteCard
                key={n.id}
                note={n}
                mode={mode}
                onEdit={() => dispatch({ type: 'OPEN_EDIT', payload: { kind: 'note', data: n } })}
              />
            ))}
          </>
        )}

        {relatedCountries.length > 0 && tab !== 'Notes' && (
          <div className={styles.related}>
            <div className={styles.relatedTitle}>Also involved</div>
            <div className={styles.relatedList}>
              {relatedCountries.map((c) => (
                <button
                  key={c.id}
                  className={styles.relatedBtn}
                  onClick={() => dispatch({ type: 'SELECT_COUNTRY', payload: c.id })}
                >
                  {c.name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className={styles.footer}>
        <button
          className={styles.graphBtn}
          onClick={() => dispatch({ type: 'SHOW_GRAPH' })}
        >
          <Network size={14} strokeWidth={2} aria-hidden="true" /> View Network Graph
        </button>
      </div>
    </div>
  );
}

function ConflictCard({ conflict, mode, onEdit, countries, selectedId, isFocused, onFocus }) {
  const [expanded, setExpanded] = useState(false);

  // Focusing a conflict on the map auto-opens its full text here
  useEffect(() => {
    if (isFocused) setExpanded(true);
  }, [isFocused]);

  const party = conflict.parties?.find((p) => p.countryId === selectedId);
  const roleKey = party?.role || null;
  const rColor = roleKey ? roleColor(roleKey) : (TYPE_COLORS[conflict.type] || '#94a3b8');
  const typeColor = TYPE_COLORS[conflict.type] || '#94a3b8';

  return (
    <div className={`${styles.card} ${isFocused ? styles.cardFocused : ''}`} style={{ '--accent': rColor }}>
      <div className={styles.cardAccent} style={{ background: `linear-gradient(90deg, ${rColor}, transparent)` }} />
      <div className={styles.cardHeader} onClick={() => setExpanded((v) => !v)}>
        <div className={styles.cardTitleRow}>
          <span className={styles.glyph} style={{ background: typeColor + '22', color: typeColor }}>
            <TypeIcon type={conflict.type} size={15} aria-hidden="true" />
          </span>
          <div className={styles.titleCol}>
            <div className={styles.cardTitle}>{conflict.title}</div>
            <div className={styles.cardSub}>
              <span style={{ color: typeColor }}>{TYPE_LABELS[conflict.type] || conflict.type}</span>
              <span className={styles.dot}>·</span>
              <span>{formatDateRange(conflict.startDate, conflict.endDate, conflict.ongoing)}</span>
            </div>
          </div>
          <button
            className={`${styles.focusBtn} ${isFocused ? styles.focusBtnActive : ''}`}
            aria-label="Open conflict details"
            title="Open conflict details"
            onClick={(e) => { e.stopPropagation(); onFocus(); }}
            style={isFocused ? { color: rColor, borderColor: rColor } : {}}
          >
            <Crosshair size={13} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>

        <div className={styles.cardMeta}>
          {roleKey && (
            <span className={styles.roleBadge} style={{ background: rColor + '22', borderColor: rColor + '66', color: rColor }}>
              {ROLE_LABELS[roleKey] || roleKey}
            </span>
          )}
          {conflict.ongoing && <span className={styles.ongoingBadge}>● live</span>}
          <span className={styles.metaSpacer} />
          <SeverityGauge severity={conflict.severity} />
        </div>
      </div>

      {expanded && (
        <div className={styles.cardBody}>
          <p className={styles.description}>{conflict.description}</p>
          <div className={styles.parties}>
            {conflict.parties?.map((p) => {
              const c = countries.find((x) => x.id === p.countryId);
              const pRoleColor = roleColor(p.role);
              const isSel = p.countryId === selectedId;
              return (
                <span
                  key={p.countryId}
                  className={`${styles.partyChip} ${isSel ? styles.partySelected : ''}`}
                  style={isSel ? { borderColor: rColor + '88', background: rColor + '1a' } : {}}
                >
                  <span className={styles.chipFlag}>{c?.iso2 ? flagEmoji(c.iso2) : '🏳'}</span>
                  {c?.name || p.countryId}
                  <em style={{ color: pRoleColor }}>{ROLE_LABELS[p.role] || p.role}</em>
                </span>
              );
            })}
          </div>
          {conflict.tags?.length > 0 && (
            <div className={styles.tags}>
              {conflict.tags.map((t) => <span key={t} className={styles.tag}>#{t}</span>)}
            </div>
          )}
          {mode === 'edit' && (
            <button className={styles.editBtn} onClick={onEdit}>Edit</button>
          )}
        </div>
      )}
    </div>
  );
}

function NoteCard({ note, mode, onEdit }) {
  return (
    <div className={styles.noteCard}>
      <div className={styles.noteTitle}>{note.title || 'Untitled'}</div>
      {note.date && <div className={styles.noteDate}>{note.date}</div>}
      <p className={styles.noteBody}>{note.body}</p>
      {mode === 'edit' && (
        <button className={styles.editBtn} onClick={onEdit}>Edit</button>
      )}
    </div>
  );
}
