import { useApp } from '../../context/AppContext';
import styles from './LeftNav.module.css';

const NAV_ITEMS = [
  { id: 'map', icon: '🗺', label: 'Map' },
  { id: 'conflicts', icon: '📋', label: 'Conflicts' },
  { id: 'stats', icon: '📊', label: 'Stats' },
  { id: 'timeline', icon: '📅', label: 'Timeline' },
  { id: 'help', icon: '❓', label: 'Help' },
];

export default function LeftNav() {
  const { state, dispatch } = useApp();

  return (
    <nav className={styles.nav}>
      {NAV_ITEMS.map((item) => (
        <button
          key={item.id}
          className={`${styles.item} ${state.view === item.id ? styles.active : ''}`}
          onClick={() => dispatch({ type: 'SET_VIEW', payload: item.id })}
          title={item.label}
        >
          <span className={styles.icon}>{item.icon}</span>
          <span className={styles.label}>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
