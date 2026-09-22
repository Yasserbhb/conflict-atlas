import { useState } from 'react';
import { useApp } from '../../context/AppContext';
import WorldMap from './WorldMap';
import GlobeView from './GlobeView';
import MapFilterBar from './MapFilterBar';
import MapLegend from './MapLegend';
import SidePanel from '../SidePanel/SidePanel';
import ConflictDetailPanel from '../ConflictDetail/ConflictDetailPanel';
import appStyles from '../../App.module.css';
import styles from './MapSection.module.css';

export default function MapSection() {
  const { state } = useApp();
  const [mode, setMode] = useState('map'); // 'map' (2D) | 'globe' (3D)

  return (
    <div className={appStyles.mapView}>
      <MapFilterBar />
      <div className={appStyles.main}>
        {mode === 'map'
          ? <WorldMap />
          : <GlobeView />}
        {state.openConflictId
          ? <ConflictDetailPanel />
          : state.selectedCountryId && <SidePanel />}
        <MapLegend />
        <div className={styles.modeSwitch}>
          <button
            className={`${styles.modeBtn} ${mode === 'map' ? styles.modeBtnActive : ''}`}
            onClick={() => setMode('map')}
          >
            2D Map
          </button>
          <button
            className={`${styles.modeBtn} ${mode === 'globe' ? styles.modeBtnActive : ''}`}
            onClick={() => setMode('globe')}
          >
            3D Globe
          </button>
        </div>
      </div>
    </div>
  );
}
