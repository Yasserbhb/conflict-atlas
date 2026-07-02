import { severityColor } from '../../utils/conflictColors';
import styles from './SeverityGauge.module.css';

// Segmented 1–5 severity meter (replaces the old ◆◆◆ text marks)
export default function SeverityGauge({ severity = 0, size = 'sm' }) {
  const color = severityColor(severity);
  return (
    <span
      className={`${styles.gauge} ${styles[size] || ''}`}
      title={`Severity ${severity} of 5`}
      aria-label={`Severity ${severity} of 5`}
      role="img"
    >
      {[1, 2, 3, 4, 5].map((s) => (
        <span
          key={s}
          className={styles.seg}
          style={{ background: s <= severity ? color : undefined }}
        />
      ))}
    </span>
  );
}
