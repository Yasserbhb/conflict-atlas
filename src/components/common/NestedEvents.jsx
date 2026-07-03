import { dateToValue, formatEventDate } from '../../utils/dateUtils';
import { kindMeta } from '../../utils/eventKinds';
import { severityColor } from '../../utils/conflictColors';
import styles from './NestedEvents.module.css';

// Renders a conflict's events as a nested list (date · kind · title · severity).
// Shared by the Conflicts catalogue and the Timeline view so events read the same
// everywhere. `highlightQuery` flags matching events (for search).
export default function NestedEvents({ events, onOpen, highlightQuery }) {
  const q = (highlightQuery || '').trim().toLowerCase();
  const sorted = [...events].sort((a, b) => (dateToValue(a.date) ?? 0) - (dateToValue(b.date) ?? 0));

  return (
    <div className={styles.events}>
      {sorted.map((ev, i) => {
        const m = kindMeta(ev.kind);
        const Icon = m.Icon;
        const match = q && ev.title.toLowerCase().includes(q);
        return (
          <button
            key={ev.id || i}
            className={`${styles.eventRow} ${match ? styles.match : ''}`}
            onClick={() => onOpen(ev)}
          >
            <span className={styles.evDate}>{formatEventDate(ev.date)}</span>
            <span className={styles.evGlyph} style={{ background: m.color + '22', color: m.color }}>
              <Icon size={11} strokeWidth={2.2} aria-hidden="true" />
            </span>
            <span className={styles.evTitle}>{ev.title}</span>
            <span className={styles.evKind} style={{ color: m.color }}>{m.label}</span>
            <span className={styles.evGauge}>
              {[1, 2, 3, 4, 5].map((s) => (
                <span key={s} className={styles.evSeg} style={{ background: s <= ev.severity ? severityColor(ev.severity) : undefined }} />
              ))}
            </span>
          </button>
        );
      })}
    </div>
  );
}
