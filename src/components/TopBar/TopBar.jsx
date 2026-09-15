import { Globe2, Plus, Database } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { isMaintainer } from '../../utils/maintainer';
import ModeToggle from './ModeToggle';
import TimelineSlider from './TimelineSlider';
import SearchBar from './SearchBar';
import styles from './TopBar.module.css';

export default function TopBar() {
  const { state, dispatch } = useApp();
  // Visitors never see Edit. Their changes would only ever land in their own browser, so the
  // toggle promises a contribution it cannot deliver — see utils/maintainer.js.
  const maintainer = isMaintainer();

  return (
    <header className={styles.topBar}>
      <div className={styles.left}>
        <div className={styles.logo}>
          <Globe2 size={18} strokeWidth={2.2} className={styles.logoIcon} aria-hidden="true" />
          <span className={styles.logoText}>Conflict Atlas</span>
        </div>
        {maintainer && <ModeToggle />}
      </div>
      <div className={styles.center}>
        <TimelineSlider />
      </div>
      <div className={styles.right}>
        <SearchBar />
        {maintainer && state.mode === 'edit' && (
          <button
            className={styles.addBtn}
            onClick={() => dispatch({ type: 'OPEN_EDIT', payload: { kind: 'conflict', data: null } })}
          >
            <Plus size={14} strokeWidth={2.5} aria-hidden="true" /> Add Conflict
          </button>
        )}
        <button
          className={styles.iconBtn}
          aria-label="Data & export"
          title="Data & export"
          onClick={() => dispatch({ type: 'SHOW_DATA_PANEL' })}
        >
          <Database size={15} strokeWidth={2} aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
