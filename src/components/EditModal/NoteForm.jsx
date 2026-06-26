import { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { generateId } from '../../utils/uuid';
import styles from './ConflictForm.module.css';

export default function NoteForm({ initial, onClose }) {
  const { state, handleSaveNote, handleDeleteNote } = useApp();
  const { countries, conflicts } = state;

  const [form, setForm] = useState({
    id: initial?.id || generateId('note'),
    title: initial?.title || '',
    body: initial?.body || '',
    countryId: initial?.countryId || '',
    conflictId: initial?.conflictId || '',
    date: initial?.date || new Date().toISOString().substring(0, 10),
  });

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    await handleSaveNote({ ...form });
    onClose();
  }

  async function handleDelete() {
    if (confirm('Delete this note?')) {
      await handleDeleteNote(form.id);
      onClose();
    }
  }

  const sortedCountries = [...countries].sort((a, b) => a.name.localeCompare(b.name));
  const sortedConflicts = [...conflicts].sort((a, b) => a.title.localeCompare(b.title));

  return (
    <form onSubmit={handleSubmit} className={styles.form}>
      <div className={styles.field}>
        <label>Title</label>
        <input value={form.title} onChange={(e) => set('title', e.target.value)} placeholder="Note title…" />
      </div>

      <div className={styles.row}>
        <div className={styles.field}>
          <label>Country</label>
          <select value={form.countryId} onChange={(e) => set('countryId', e.target.value)}>
            <option value="">— None —</option>
            {sortedCountries.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div className={styles.field}>
          <label>Event date</label>
          <input type="date" value={form.date} onChange={(e) => set('date', e.target.value)} />
        </div>
      </div>

      <div className={styles.field}>
        <label>Related conflict (optional)</label>
        <select value={form.conflictId} onChange={(e) => set('conflictId', e.target.value)}>
          <option value="">— None —</option>
          {sortedConflicts.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
        </select>
      </div>

      <div className={styles.field}>
        <label>Note</label>
        <textarea
          value={form.body}
          onChange={(e) => set('body', e.target.value)}
          rows={8}
          placeholder="Write what you learned…"
          required
        />
      </div>

      <div className={styles.actions}>
        {initial?.id && (
          <button type="button" className={styles.deleteBtn} onClick={handleDelete}>Delete</button>
        )}
        <button type="button" className={styles.cancelBtn} onClick={onClose}>Cancel</button>
        <button type="submit" className={styles.saveBtn}>Save Note</button>
      </div>
    </form>
  );
}
