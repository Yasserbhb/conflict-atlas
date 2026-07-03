import { useState } from 'react';
import { ChevronDown, Trash2, Plus } from 'lucide-react';
import { KIND_META, kindMeta } from '../../utils/eventKinds';
import { generateId } from '../../utils/uuid';
import styles from './EventsEditor.module.css';

const KIND_KEYS = Object.keys(KIND_META);
const emptyEvent = () => ({
  id: generateId('evt'), date: '', title: '', kind: 'battle',
  severity: 3, location: null, parties: [], description: '', sources: [],
});

// Editor for a conflict's events[] timeline. Emits the full events array on any change.
export default function EventsEditor({ events, onChange }) {
  const list = events || [];
  const [open, setOpen] = useState(list.length ? null : null);

  const setEvent = (i, patch) => {
    const next = [...list];
    next[i] = { ...next[i], ...patch };
    onChange(next);
  };
  const setLoc = (i, key, val) => {
    const cur = list[i].location || { lat: '', lng: '', label: '' };
    setEvent(i, { location: { ...cur, [key]: val } });
  };
  const add = () => { onChange([...list, emptyEvent()]); setOpen(list.length); };
  const remove = (i) => { onChange(list.filter((_, idx) => idx !== i)); setOpen(null); };

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <label>Events (timeline)</label>
        <button type="button" className={styles.addBtn} onClick={add}><Plus size={13} aria-hidden="true" /> Add event</button>
      </div>
      {list.length === 0 && (
        <p className={styles.empty}>No events yet. Add key moments (attacks, battles, ceasefires, treaties…) to build a timeline and map pins.</p>
      )}
      {list.map((ev, i) => {
        const m = kindMeta(ev.kind);
        const isOpen = open === i;
        return (
          <div key={ev.id || i} className={styles.card}>
            <div className={styles.rowHead}>
              <button type="button" className={styles.toggle} onClick={() => setOpen(isOpen ? null : i)}>
                <span className={styles.dot} style={{ background: m.color }} />
                <span className={styles.summary}>{ev.date || '(no date)'} — {ev.title || '(untitled)'}</span>
                <ChevronDown size={14} className={isOpen ? styles.chevOpen : styles.chev} aria-hidden="true" />
              </button>
              <button type="button" className={styles.del} onClick={() => remove(i)} aria-label="Remove event"><Trash2 size={13} aria-hidden="true" /></button>
            </div>
            {isOpen && (
              <div className={styles.body}>
                <div className={styles.grid2}>
                  <div className={styles.f}>
                    <label>Date</label>
                    <input value={ev.date} onChange={(e) => setEvent(i, { date: e.target.value })} placeholder="1944-06-06 or 1944" />
                  </div>
                  <div className={styles.f}>
                    <label>Kind</label>
                    <select value={ev.kind} onChange={(e) => setEvent(i, { kind: e.target.value })}>
                      {KIND_KEYS.map((k) => <option key={k} value={k}>{KIND_META[k].label}</option>)}
                    </select>
                  </div>
                </div>
                <div className={styles.f}>
                  <label>Title</label>
                  <input value={ev.title} onChange={(e) => setEvent(i, { title: e.target.value })} placeholder="D-Day: Normandy landings" />
                </div>
                <div className={styles.f}>
                  <label>Severity (1–5): {ev.severity}</label>
                  <input type="range" min={1} max={5} value={ev.severity} onChange={(e) => setEvent(i, { severity: parseInt(e.target.value) })} />
                </div>
                <div className={styles.grid3}>
                  <div className={styles.f}><label>Lat</label><input value={ev.location?.lat ?? ''} onChange={(e) => setLoc(i, 'lat', e.target.value)} placeholder="49.34" /></div>
                  <div className={styles.f}><label>Lng</label><input value={ev.location?.lng ?? ''} onChange={(e) => setLoc(i, 'lng', e.target.value)} placeholder="-0.51" /></div>
                  <div className={styles.f}><label>Place</label><input value={ev.location?.label ?? ''} onChange={(e) => setLoc(i, 'label', e.target.value)} placeholder="Normandy" /></div>
                </div>
                <p className={styles.hint}>Leave lat/lng blank for events with no single place (e.g. a nationwide famine) — they show in the timeline but not as a map pin.</p>
                <div className={styles.f}>
                  <label>Description</label>
                  <textarea rows={2} value={ev.description} onChange={(e) => setEvent(i, { description: e.target.value })} />
                </div>
                <div className={styles.f}>
                  <label>Sources (one URL per line)</label>
                  <textarea rows={2} value={(ev.sources || []).join('\n')} onChange={(e) => setEvent(i, { sources: e.target.value.split('\n').map((s) => s.trim()).filter(Boolean) })} />
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
