import { Map, ListTree, BarChart3, CalendarRange, HelpCircle } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import styles from './LeftNav.module.css';

const NAV_ITEMS = [
  { id: 'map', Icon: Map, label: 'Map' },
  { id: 'conflicts', Icon: ListTree, label: 'Conflicts' },
  { id: 'stats', Icon: BarChart3, label: 'Stats' },
  { id: 'timeline', Icon: CalendarRange, label: 'Timeline' },
  { id: 'help', Icon: HelpCircle, label: 'Help' },
];

export default function LeftNav() {
  const { state, dispatch } = useApp();

  return (
    <nav className={styles.nav} aria-label="Main">
      {NAV_ITEMS.map(({ id, Icon, label }) => {
        const active = state.view === id;
        return (
          <button
            key={id}
            className={`${styles.item} ${active ? styles.active : ''}`}
            onClick={() => dispatch({ type: 'SET_VIEW', payload: id })}
            aria-label={label}
            aria-current={active ? 'page' : undefined}
            title={label}
          >
            <Icon size={19} strokeWidth={2} aria-hidden="true" />
            <span className={styles.label}>{label}</span>
          </button>
        );
      })}
    </nav>
  );
}
