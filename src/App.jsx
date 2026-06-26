import { AppProvider, useApp } from './context/AppContext';
import ErrorBoundary from './components/ErrorBoundary';
import TopBar from './components/TopBar/TopBar';
import WorldMap from './components/Map/WorldMap';
import SidePanel from './components/SidePanel/SidePanel';
import GraphView from './components/GraphView/GraphView';
import EditModal from './components/EditModal/EditModal';
import DataPanel from './components/DataPanel/DataPanel';
import './styles/global.css';
import styles from './App.module.css';

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
      <div className={styles.main}>
        <WorldMap />
        {state.selectedCountryId && <SidePanel />}
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
