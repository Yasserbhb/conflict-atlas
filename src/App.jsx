import { AppProvider, useApp } from './context/AppContext';
import ErrorBoundary from './components/ErrorBoundary';
import LeftNav from './components/LeftNav/LeftNav';
import ConflictsView from './components/ConflictsView/ConflictsView';
import StatsView from './components/StatsView/StatsView';
import TimelineView from './components/TimelineView/TimelineView';
import HelpView from './components/HelpView/HelpView';
import PipelineView from './components/PipelineView/PipelineView';
import TopBar from './components/TopBar/TopBar';
import MapSection from './components/Map/MapSection';
import GraphView from './components/GraphView/GraphView';
import DataPanel from './components/DataPanel/DataPanel';
import './styles/global.css';
import styles from './App.module.css';

function ActiveView() {
  const { state } = useApp();
  switch (state.view) {
    case 'map':
      return <MapSection />;
    case 'conflicts':
      return <ConflictsView />;
    case 'stats':
      return <StatsView />;
    case 'timeline':
      return <TimelineView />;
    case 'help':
      return <HelpView />;
    case 'pipeline':
      return <PipelineView />;
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
