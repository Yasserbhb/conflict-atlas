import { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { generateId } from '../../utils/uuid';
import { CONFLICT_TYPES, ROLE_TYPES, TYPE_LABELS, ROLE_LABELS } from '../../utils/conflictColors';
import styles from './ConflictForm.module.css';

const emptyParty = () => ({ countryId: '', role: 'aggressor' });

export default function ConflictForm({ initial, onClose }) {
  const { state, handleSaveConflict, handleDeleteConflict } = useApp();
  const { countries } = state;

  const [form, setForm] = useState({
    id: initial?.id || generateId('user'),
    title: initial?.title || '',
    type: initial?.type || 'war',
    severity: initial?.severity || 3,
    startDate: initial?.startDate || '',
    endDate: initial?.endDate || '',
    ongoing: initial?.ongoing ?? true,
    description: initial?.description || '',
    parties: initial?.parties?.length ? [...initial.parties] : [emptyParty()],
    tags: initial?.tags?.join(', ') || '',
    sources: initial?.sources?.join('\n') || '',
  });

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function setParty(i, key, value) {
    setForm((f) => {
      const parties = [...f.parties];
      parties[i] = { ...parties[i], [key]: value };
      return { ...f, parties };
    });
  }

  function addParty() {
    setForm((f) => ({ ...f, parties: [...f.parties, emptyParty()] }));
  }

  function removeParty(i) {
    setForm((f) => ({ ...f, parties: f.parties.filter((_, idx) => idx !== i) }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const tags = form.tags.split(',').map((t) => t.trim()).filter(Boolean);
    const sources = form.sources.split('\n').map((s) => s.trim()).filter(Boolean);
    const parties = form.parties.filter((p) => p.countryId);

    await handleSaveConflict({
      ...form,
      tags,
      sources,
      parties,
      involvedCountries: parties.map((p) => p.countryId),
      endDate: form.ongoing ? null : form.endDate || null,
    });
  }

  async function handleDelete() {
    if (confirm('Delete this conflict?')) {
      await handleDeleteConflict(form.id);
      onClose();
    }
  }

  const sortedCountries = [...countries].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <form onSubmit={handleSubmit} className={styles.form}>
      <div className={styles.field}>
        <label>Title</label>
        <input value={form.title} onChange={(e) => set('title', e.target.value)} required placeholder="e.g. Yemen War" />
      </div>

      <div className={styles.row}>
        <div className={styles.field}>
          <label>Type</label>
          <select value={form.type} onChange={(e) => set('type', e.target.value)}>
            {CONFLICT_TYPES.map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
          </select>
        </div>
        <div className={styles.field}>
          <label>Severity (1–5)</label>
          <input
            type="range" min={1} max={5} value={form.severity}
            onChange={(e) => set('severity', parseInt(e.target.value))}
          />
          <span className={styles.sevVal}>{'◆'.repeat(form.severity)}</span>
        </div>
      </div>

      <div className={styles.row}>
        <div className={styles.field}>
          <label>Start date (year or YYYY-MM-DD)</label>
          <input value={form.startDate} onChange={(e) => set('startDate', e.target.value)} placeholder="1948" required />
        </div>
        <div className={styles.field}>
          <label>End date</label>
          <input value={form.endDate} onChange={(e) => set('endDate', e.target.value)} placeholder="1949" disabled={form.ongoing} />
        </div>
        <div className={styles.checkField}>
          <label>
            <input type="checkbox" checked={form.ongoing} onChange={(e) => set('ongoing', e.target.checked)} />
            Ongoing
          </label>
        </div>
      </div>

      <div className={styles.field}>
        <label>Description</label>
        <textarea
          value={form.description}
          onChange={(e) => set('description', e.target.value)}
          rows={5}
          placeholder="Describe the conflict, its causes and impact…"
        />
      </div>

      <div className={styles.partiesSection}>
        <div className={styles.partiesHeader}>
          <label>Parties involved</label>
          <button type="button" className={styles.addPartyBtn} onClick={addParty}>+ Add party</button>
        </div>
        {form.parties.map((p, i) => (
          <div key={i} className={styles.partyRow}>
            <select
              value={p.countryId}
              onChange={(e) => setParty(i, 'countryId', e.target.value)}
            >
              <option value="">— Select country —</option>
              {sortedCountries.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <select value={p.role} onChange={(e) => setParty(i, 'role', e.target.value)}>
              {ROLE_TYPES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </select>
            <button type="button" className={styles.removeBtn} onClick={() => removeParty(i)}>✕</button>
          </div>
        ))}
      </div>

      <div className={styles.field}>
        <label>Tags (comma-separated)</label>
        <input value={form.tags} onChange={(e) => set('tags', e.target.value)} placeholder="genocide, colonial, africa" />
      </div>

      <div className={styles.field}>
        <label>Sources (one URL per line)</label>
        <textarea value={form.sources} onChange={(e) => set('sources', e.target.value)} rows={2} placeholder="https://..." />
      </div>

      <div className={styles.actions}>
        {initial?.id && (
          <button type="button" className={styles.deleteBtn} onClick={handleDelete}>Delete</button>
        )}
        <button type="button" className={styles.cancelBtn} onClick={onClose}>Cancel</button>
        <button type="submit" className={styles.saveBtn}>Save Conflict</button>
      </div>
    </form>
  );
}
