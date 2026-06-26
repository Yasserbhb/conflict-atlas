import { useApp } from '../../context/AppContext';
import { TYPE_LABELS, CONFLICT_TYPES } from '../../utils/conflictColors';
import { applyConflictFilters, isActiveAt, isFilterActive } from '../../utils/dateUtils';
import styles from './MapFilterBar.module.css';

export default function MapFilterBar() {
  const { state, dispatch } = useApp();
  const f = state.mapFilters;

  const set = (patch) => dispatch({ type: 'SET_MAP_FILTERS', payload: patch });

  // How many conflicts are shown at the current year under these filters
  const shown = applyConflictFilters(state.conflicts, f).filter((c) => isActiveAt(c, state.timelineYear)).length;
  const active = isFilterActive(f);

  return (
    <div className={styles.bar}>
      <span className={styles.label}>Show on map:</span>

      <select className={styles.select} value={f.type} onChange={(e) => set({ type: e.target.value })}>
        <option value="all">All types</option>
        {CONFLICT_TYPES.map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
      </select>

      <select className={styles.select} value={f.minSeverity} onChange={(e) => set({ minSeverity: Number(e.target.value) })}>
        <option value={1}>Any severity</option>
        <option value={3}>Severity 3+</option>
        <option value={4}>Severity 4+</option>
        <option value={5}>Severity 5 only</option>
      </select>

      <label className={styles.checkbox}>
        <input type="checkbox" checked={f.ongoingOnly} onChange={(e) => set({ ongoingOnly: e.target.checked })} />
        Ongoing only
      </label>

      <span className={styles.count}>{shown} active in {state.timelineYear}</span>

      {active && (
        <button className={styles.reset} onClick={() => dispatch({ type: 'RESET_MAP_FILTERS' })}>
          Clear filters
        </button>
      )}
    </div>
  );
}
