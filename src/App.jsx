import { AppProvider, useApp } from './context/AppContext';
import ErrorBoundary from './components/ErrorBoundary';
import LeftNav from './components/LeftNav/LeftNav';
import ConflictsView from './components/ConflictsView/ConflictsView';
import StatsView from './components/StatsView/StatsView';
import TimelineView from './components/TimelineView/TimelineView';
import HelpView from './components/HelpView/HelpView';
import TopBar from './components/TopBar/TopBar';
import WorldMap from './components/Map/WorldMap';
import MapFilterBar from './components/Map/MapFilterBar';
import SidePanel from './components/SidePanel/SidePanel';
import GraphView from './components/GraphView/GraphView';
import EditModal from './components/EditModal/EditModal';
import DataPanel from './components/DataPanel/DataPanel';
import './styles/global.css';
import styles from './App.module.css';

function ActiveView() {
  const { state } = useApp();
  switch (state.view) {
    case 'map':
      return (
        <div className={styles.mapView}>
          <MapFilterBar />
          <div className={styles.main}>
            <WorldMap />
            {state.selectedCountryId && <SidePanel />}
          </div>
        </div>
      );
    case 'conflicts':
      return <ConflictsView />;
    case 'stats':
      return <StatsView />;
    case 'timeline':
      return <TimelineView />;
    case 'help':
      return <HelpView />;
    default:
      return null;
  }
}

function AppShell() {
  const { state } = useApp();

  if (state.isLoading) {
    return (
      <div className={styles.loading}>
        <div className={styles.loadingText}>Loading Conflict Atlas…</div>
      </div>
    );
  }

  return (
    <div className={styles.app}>
      <TopBar />
      <div className={styles.shell}>
        <LeftNav />
        <div className={styles.viewArea}>
          <ActiveView />
        </div>
      </div>
      {state.showGraphView && <GraphView />}
      {state.editTarget && <EditModal />}
      {state.showDataPanel && <DataPanel />}
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <AppProvider>
        <ErrorBoundary>
          <AppShell />
        </ErrorBoundary>
      </AppProvider>
    </ErrorBoundary>
  );
}
