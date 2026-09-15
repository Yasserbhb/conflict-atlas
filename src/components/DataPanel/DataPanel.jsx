import { X, Download } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { getAllConflicts, getAllCountries } from '../../db/queries';
import styles from './DataPanel.module.css';

export default function DataPanel() {
  const { state, dispatch } = useApp();

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

  return (
    <div className={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) dispatch({ type: 'HIDE_DATA_PANEL' }); }}>
      <div className={styles.panel}>
        <div className={styles.header}>
          <span className={styles.title}>Data</span>
          <button className={styles.closeBtn} aria-label="Close" onClick={() => dispatch({ type: 'HIDE_DATA_PANEL' })}><X size={16} strokeWidth={2.2} aria-hidden="true" /></button>
        </div>
        <div className={styles.body}>
          <section className={styles.section}>
            <h3>Export</h3>
            <p>Download the whole dataset as JSON — every conflict, its events, parties and sources.</p>
            <button className={styles.primaryBtn} onClick={handleExport}>
              <Download size={14} strokeWidth={2.2} aria-hidden="true" /> Download JSON
            </button>
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
