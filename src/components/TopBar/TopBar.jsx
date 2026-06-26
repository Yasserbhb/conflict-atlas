import { useApp } from '../../context/AppContext';
import ModeToggle from './ModeToggle';
import TimelineSlider from './TimelineSlider';
import SearchBar from './SearchBar';
import styles from './TopBar.module.css';

export default function TopBar() {
  const { state, dispatch } = useApp();

  return (
    <header className={styles.topBar}>
      <div className={styles.left}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>⚔</span>
          <span className={styles.logoText}>Conflict Atlas</span>
        </div>
        <ModeToggle />
      </div>
      <div className={styles.center}>
        <TimelineSlider />
      </div>
      <div className={styles.right}>
        <SearchBar />
        {state.mode === 'edit' && (
          <button
            className={styles.addBtn}
            onClick={() => dispatch({ type: 'OPEN_EDIT', payload: { kind: 'conflict', data: null } })}
          >
            + Add Conflict
          </button>
        )}
        <button
          className={styles.iconBtn}
          title="Data & Export"
          onClick={() => dispatch({ type: 'SHOW_DATA_PANEL' })}
        >
          ⬇
        </button>
      </div>
    </header>
  );
}
