import { useState, useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { getNotesByCountry } from '../../db/queries';
import { useCountryConflicts } from '../../hooks/useConflictFilter';
import { TYPE_LABELS, TYPE_COLORS, ROLE_LABELS, ROLE_COLORS, roleColor } from '../../utils/conflictColors';
import { formatDateRange } from '../../utils/dateUtils';
import styles from './SidePanel.module.css';

const TABS = ['Conflicts', 'Territories', 'Notes'];

export default function SidePanel() {
  const { state, dispatch } = useApp();
  const { selectedCountryId, focusedConflictId, conflicts, timelineYear, mode, countries } = state;
  const [tab, setTab] = useState('Conflicts');
  const [notes, setNotes] = useState([]);

  const country = countries.find((c) => c.id === selectedCountryId);

  const allConflicts = useCountryConflicts(conflicts, selectedCountryId, null);
  const activeConflicts = allConflicts.filter((c) => {
    const sy = parseInt(String(c.startDate).substring(0, 4));
    const ey = c.endDate ? parseInt(String(c.endDate).substring(0, 4)) : null;
    return sy <= timelineYear && (c.ongoing || ey === null || ey >= timelineYear);
  });
  const warConflicts = allConflicts.filter((c) => ['war','civil_war','proxy_war'].includes(c.type));
  const atrocities = allConflicts.filter((c) => ['genocide'].includes(c.type));
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

  function getRole(conflict) {
    const party = conflict.parties?.find((p) => p.countryId === selectedCountryId);
    return party ? ROLE_LABELS[party.role] || party.role : '—';
  }

  const displayConflicts = tab === 'Conflicts'
    ? activeConflicts
    : tab === 'Territories'
    ? territories
    : [];

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div>
          <div className={styles.countryName}>{country.name}</div>
          <div className={styles.countryMeta}>{country.region} · {allConflicts.length} conflicts recorded</div>
        </div>
        <button
          className={styles.closeBtn}
          onClick={() => dispatch({ type: 'CLEAR_SELECTION' })}
        >✕</button>
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
                role={getRole(c)}
                mode={mode}
                onEdit={() => dispatch({ type: 'OPEN_EDIT', payload: { kind: 'conflict', data: c } })}
                countries={countries}
                selectedId={selectedCountryId}
                isFocused={focusedConflictId === c.id}
                onFocus={() => dispatch({
                  type: focusedConflictId === c.id ? 'CLEAR_FOCUSED_CONFLICT' : 'FOCUS_CONFLICT',
                  payload: c.id,
                })}
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
                role={getRole(c)}
                mode={mode}
                onEdit={() => dispatch({ type: 'OPEN_EDIT', payload: { kind: 'conflict', data: c } })}
                countries={countries}
                selectedId={selectedCountryId}
                isFocused={focusedConflictId === c.id}
                onFocus={() => dispatch({
                  type: focusedConflictId === c.id ? 'CLEAR_FOCUSED_CONFLICT' : 'FOCUS_CONFLICT',
                  payload: c.id,
                })}
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
          View Network Graph
        </button>
      </div>
    </div>
  );
}

function ConflictCard({ conflict, role, mode, onEdit, countries, selectedId, isFocused, onFocus }) {
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
    <div
      className={styles.card}
      style={{
        borderLeftColor: rColor,
        outline: isFocused ? `1px solid ${rColor}` : 'none',
        background: isFocused ? `${rColor}0d` : undefined,
      }}
    >
      <div className={styles.cardHeader} onClick={() => setExpanded((v) => !v)}>
        <div className={styles.cardTitleRow}>
          <div className={styles.cardTitle}>{conflict.title}</div>
          <button
            className={`${styles.focusBtn} ${isFocused ? styles.focusBtnActive : ''}`}
            title={isFocused ? 'Show all conflicts' : 'Isolate this conflict on map'}
            onClick={(e) => { e.stopPropagation(); onFocus(); }}
            style={isFocused ? { color: rColor, borderColor: rColor } : {}}
          >
            {isFocused ? '✕' : '⊙'}
          </button>
        </div>

        {/* Role badge — most prominent, this is what matters in context */}
        {roleKey && (
          <div
            className={styles.roleBadge}
            style={{ background: rColor + '22', borderColor: rColor, color: rColor }}
          >
            {ROLE_LABELS[roleKey] || roleKey}
          </div>
        )}

        <div className={styles.cardMeta}>
          {/* Conflict type is secondary context — shown smaller */}
          <span className={styles.type} style={{ color: typeColor }}>
            {TYPE_LABELS[conflict.type] || conflict.type}
          </span>
          <span className={styles.dates}>{formatDateRange(conflict.startDate, conflict.endDate, conflict.ongoing)}</span>
          {conflict.ongoing && <span className={styles.ongoingBadge}>ONGOING</span>}
        </div>

        <div className={styles.roleRow}>
          <span className={styles.severity}>{'◆'.repeat(conflict.severity)}</span>
        </div>
      </div>

      {expanded && (
        <div className={styles.cardBody}>
          <p className={styles.description}>{conflict.description}</p>
          <div className={styles.parties}>
            {conflict.parties?.map((p) => {
              const c = countries.find((x) => x.id === p.countryId);
              const pRoleColor = roleColor(p.role);
              return (
                <span
                  key={p.countryId}
                  className={`${styles.partyTag} ${p.countryId === selectedId ? styles.partySelected : ''}`}
                  style={p.countryId === selectedId
                    ? { borderColor: rColor, color: rColor, background: rColor + '15' }
                    : {}}
                >
                  {c?.name || p.countryId}
                  <em style={{ color: pRoleColor }}> {ROLE_LABELS[p.role] || p.role}</em>
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
