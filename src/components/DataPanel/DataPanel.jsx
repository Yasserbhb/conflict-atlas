import { X, Download, Upload } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { getAllConflicts, getAllCountries, saveConflict, saveCountry } from '../../db/queries';
import styles from './DataPanel.module.css';

export default function DataPanel() {
  const { state, dispatch, reloadData } = useApp();

  if (!state.showDataPanel) return null;

  async function handleExport() {
    const [conflicts, countries] = await Promise.all([getAllConflicts(), getAllCountries()]);
    const data = {
      exportedAt: new Date().toISOString(),
      version: '1.0.0',
      conflicts,
      countries,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `conflict-atlas-${new Date().toISOString().substring(0,10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleImport(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (ev) => {
      try {
        const data = JSON.parse(ev.target.result);
        const conflicts = data.conflicts || [];
        const countries = data.countries || [];
        for (const c of countries) await saveCountry(c);
        for (const c of conflicts) await saveConflict(c);
        await reloadData();
        alert(`Imported ${conflicts.length} conflicts and ${countries.length} countries.`);
      } catch (err) {
        alert('Import failed: ' + err.message);
      }
    };
    reader.readAsText(file);
  }

  return (
    <div className={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) dispatch({ type: 'HIDE_DATA_PANEL' }); }}>
      <div className={styles.panel}>
        <div className={styles.header}>
          <span className={styles.title}>Data & Export</span>
          <button className={styles.closeBtn} aria-label="Close" onClick={() => dispatch({ type: 'HIDE_DATA_PANEL' })}><X size={16} strokeWidth={2.2} aria-hidden="true" /></button>
        </div>
        <div className={styles.body}>
          <section className={styles.section}>
            <h3>Export</h3>
            <p>Download all your conflicts and notes as a JSON file. You can re-import this later or back it up.</p>
            <button className={styles.primaryBtn} onClick={handleExport}>
              <Download size={14} strokeWidth={2.2} aria-hidden="true" /> Download JSON
            </button>
          </section>
          <section className={styles.section}>
            <h3>Import</h3>
            <p>Import a previously exported JSON file. Existing records are merged (not duplicated by ID).</p>
            <label className={styles.fileLabel}>
              <Upload size={14} strokeWidth={2.2} aria-hidden="true" /> Choose file
              <input type="file" accept=".json" onChange={handleImport} className={styles.fileInput} />
            </label>
          </section>
          <section className={styles.section}>
            <h3>Stats</h3>
            <div className={styles.stats}>
              <div className={styles.stat}>
                <span className={styles.statVal}>{state.conflicts.length}</span>
                <span className={styles.statKey}>conflicts</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statVal}>{state.conflicts.filter((c) => c.ongoing).length}</span>
                <span className={styles.statKey}>ongoing</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statVal}>{state.countries.length}</span>
                <span className={styles.statKey}>countries</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
