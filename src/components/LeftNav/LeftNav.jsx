import { Map, ListTree, BarChart3, CalendarRange, Network, HelpCircle, Cpu } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { isMaintainer } from '../../utils/maintainer';
import styles from './LeftNav.module.css';

const NAV_ITEMS = [
  { id: 'map', Icon: Map, label: 'Map' },
  { id: 'conflicts', Icon: ListTree, label: 'Conflicts' },
  { id: 'stats', Icon: BarChart3, label: 'Stats' },
  { id: 'timeline', Icon: CalendarRange, label: 'Timeline' },
  // Opens the relationship graph modal directly — not a `view` swap like the others above,
  // since the graph is (and stays) a full-screen overlay, not a page.
  { id: 'relationships', Icon: Network, label: 'Relationships', modal: true },
  { id: 'help', Icon: HelpCircle, label: 'Help' },
  // Maintainer-only: the operations log for the weekly agent run. Filtered out for visitors
  // below rather than omitted here, so the item's definition stays next to its siblings.
  { id: 'pipeline', Icon: Cpu, label: 'Pipeline', maintainerOnly: true },
];

export default function LeftNav() {
  const { state, dispatch } = useApp();
  const maintainer = isMaintainer();
  const items = NAV_ITEMS.filter((i) => !i.maintainerOnly || maintainer);

  return (
    <nav className={styles.nav} aria-label="Main">
      {items.map(({ id, Icon, label, modal }) => {
        const active = modal ? (state.showGraphView && state.graphMode === 'conflicts') : state.view === id;
        return (
          <button
            key={id}
            className={`${styles.item} ${active ? styles.active : ''}`}
            onClick={() => modal
              ? dispatch({ type: 'SHOW_GRAPH', payload: { mode: 'conflicts' } })
              : dispatch({ type: 'SET_VIEW', payload: id })}
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
