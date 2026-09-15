import { useMemo } from 'react';
import { Play, Pause } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import styles from './TimelineSlider.module.css';

const MIN_YEAR = 1490;
const MAX_YEAR = 2026;
const SPAN = MAX_YEAR - MIN_YEAR;
const BUCKET = 4;                                   // years per histogram bar
const BUCKETS = Math.ceil(SPAN / BUCKET);
const CENTURIES = [1500, 1600, 1700, 1800, 1900, 2000];

const startYear = (c) => parseInt(String(c.startDate).slice(0, 4), 10);
const endYear = (c) =>
  c.ongoing ? MAX_YEAR : parseInt(String(c.endDate || c.startDate).slice(0, 4), 10);

export default function TimelineSlider() {
  const { state, dispatch } = useApp();
  const { timelineYear, isPlaying, conflicts } = state;

  const pct = ((timelineYear - MIN_YEAR) / SPAN) * 100;

  // How many conflicts were running in each slice of the span. Drawn behind the track so the
  // scrubber doubles as a chart of where five centuries put their violence — the 20th century
  // spike is the whole point, and a plain slider hides it.
  const density = useMemo(() => {
    const bins = new Array(BUCKETS).fill(0);
    for (const c of conflicts) {
      const s = startYear(c);
      const e = endYear(c);
      if (isNaN(s) || isNaN(e)) continue;
      const from = Math.max(MIN_YEAR, Math.min(s, e));
      const to = Math.min(MAX_YEAR, Math.max(s, e));
      if (to < MIN_YEAR || from > MAX_YEAR) continue;
      const bFrom = Math.floor((from - MIN_YEAR) / BUCKET);
      const bTo = Math.floor((to - MIN_YEAR) / BUCKET);
      for (let b = bFrom; b <= bTo && b < BUCKETS; b++) bins[b]++;
    }
    const peak = Math.max(1, ...bins);
    return bins.map((n) => n / peak);
  }, [conflicts]);

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
        <svg
          className={styles.rule}
          viewBox={`0 0 ${BUCKETS} 10`}
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          {density.map((v, i) => (
            v > 0 && (
              <rect
                key={i}
                x={i + 0.15}
                width={0.7}
                y={10 - v * 10}
                height={v * 10}
                className={(i + 0.5) * BUCKET + MIN_YEAR <= timelineYear ? styles.binPast : styles.bin}
              />
            )
          ))}
          {CENTURIES.map((y) => (
            <rect key={y} className={styles.tick} x={(y - MIN_YEAR) / BUCKET} y={0} width={0.08} height={10} />
          ))}
        </svg>
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
