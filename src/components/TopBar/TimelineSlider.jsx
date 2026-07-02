import { Play, Pause } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import styles from './TimelineSlider.module.css';

const MIN_YEAR = 1490;
const MAX_YEAR = 2026;

export default function TimelineSlider() {
  const { state, dispatch } = useApp();
  const { timelineYear, isPlaying, conflicts } = state;

  const pct = ((timelineYear - MIN_YEAR) / (MAX_YEAR - MIN_YEAR)) * 100;

  // Count active conflicts for current year
  const activeCount = conflicts.filter((c) => {
    const sy = parseInt(String(c.startDate).substring(0, 4));
    const ey = c.endDate ? parseInt(String(c.endDate).substring(0, 4)) : null;
    return sy <= timelineYear && (c.ongoing || ey === null || ey >= timelineYear);
  }).length;

  return (
    <div className={styles.container}>
      <button
        className={styles.playBtn}
        onClick={() => dispatch({ type: 'SET_PLAYING', payload: !isPlaying })}
        aria-label={isPlaying ? 'Pause timeline' : 'Play timeline'}
        title={isPlaying ? 'Pause' : 'Play timeline'}
      >
        {isPlaying ? <Pause size={13} strokeWidth={2.5} aria-hidden="true" /> : <Play size={13} strokeWidth={2.5} aria-hidden="true" />}
      </button>
      <span className={styles.yearLabel}>{MIN_YEAR}</span>
      <div className={styles.sliderWrapper}>
        <input
          type="range"
          min={MIN_YEAR}
          max={MAX_YEAR}
          value={timelineYear}
          onChange={(e) => {
            if (isPlaying) dispatch({ type: 'SET_PLAYING', payload: false });
            dispatch({ type: 'SET_TIMELINE_YEAR', payload: parseInt(e.target.value) });
          }}
          className={styles.slider}
          style={{ '--pct': `${pct}%` }}
        />
      </div>
      <span className={styles.yearLabel}>{MAX_YEAR}</span>
      <div className={styles.yearDisplay}>
        <span className={styles.yearValue}>{timelineYear}</span>
        <span className={styles.conflictCount}>{activeCount} active</span>
      </div>
    </div>
  );
}
