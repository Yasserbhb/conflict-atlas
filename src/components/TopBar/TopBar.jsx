import { Globe2, Database } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import TimelineSlider from './TimelineSlider';
import SearchBar from './SearchBar';
import styles from './TopBar.module.css';

export default function TopBar() {
  const { dispatch } = useApp();

  return (
    <header className={styles.topBar}>
      <div className={styles.left}>
        <div className={styles.logo}>
          <Globe2 size={18} strokeWidth={2.2} className={styles.logoIcon} aria-hidden="true" />
          <span className={styles.logoText}>Conflict Atlas</span>
        </div>
      </div>
      <div className={styles.center}>
        <TimelineSlider />
      </div>
      <div className={styles.right}>
        <SearchBar />
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
