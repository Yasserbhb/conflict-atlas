import { useMemo, useState } from 'react';
import { ChevronDown, ExternalLink } from 'lucide-react';
import { dateToValue, formatEventDate } from '../../utils/dateUtils';
import { severityColor } from '../../utils/conflictColors';
import { kindMeta } from '../../utils/eventKinds';
import styles from './EventTimeline.module.css';

// A conflict's events, presented as an intensity sparkline + a narrative timeline.
export default function EventTimeline({ events, conflict }) {
  const [openId, setOpenId] = useState(null);

  const sorted = useMemo(
    () => [...events].sort((a, b) => (dateToValue(a.date) ?? 0) - (dateToValue(b.date) ?? 0)),
    [events]
  );

  // Sparkline points: x = position across the span, y = event severity.
  const spark = useMemo(() => {
    const withSev = sorted.filter((e) => e.severity != null && dateToValue(e.date) != null);
    if (withSev.length < 2) return null;
    const vals = withSev.map((e) => dateToValue(e.date));
    const lo = Math.min(dateToValue(conflict.startDate) ?? vals[0], ...vals);
    const hi = Math.max(dateToValue(conflict.endDate) ?? vals[vals.length - 1], ...vals);
    const span = hi - lo || 1;
    const W = 100, H = 40, pad = 3;
    return withSev.map((e) => ({
      x: pad + ((dateToValue(e.date) - lo) / span) * (W - 2 * pad),
      y: H - pad - ((e.severity) / 5) * (H - 2 * pad),
      sev: e.severity,
    }));
  }, [sorted, conflict]);

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        Timeline <span className={styles.count}>{sorted.length}</span>
      </div>

      {spark && (
        <svg className={styles.spark} viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
          <polyline
            className={styles.sparkArea}
            points={`${spark[0].x},40 ${spark.map((p) => `${p.x},${p.y}`).join(' ')} ${spark[spark.length - 1].x},40`}
          />
          <polyline
            className={styles.sparkLine}
            points={spark.map((p) => `${p.x},${p.y}`).join(' ')}
            vectorEffect="non-scaling-stroke"
          />
          {spark.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r={1.6} fill={severityColor(p.sev)} vectorEffect="non-scaling-stroke" />
          ))}
        </svg>
      )}

      <ol className={styles.list}>
        {sorted.map((e, i) => {
          const meta = kindMeta(e.kind);
          const Icon = meta.Icon;
          const id = e.id || `${e.date}-${i}`;
          const open = openId === id;
          const hasDetail = e.description || (e.sources || []).length > 0;
          return (
            <li key={id} className={styles.item}>
              <span className={styles.rail}>
                <span className={styles.dot} style={{ background: meta.color }} />
              </span>
              <div className={styles.content}>
                <button
                  className={styles.row}
                  onClick={() => hasDetail && setOpenId(open ? null : id)}
                  aria-expanded={open}
                  data-static={!hasDetail}
                >
                  <span className={styles.date}>{formatEventDate(e.date)}</span>
                  <span className={styles.glyph} style={{ color: meta.color, background: meta.color + '22' }}>
                    <Icon size={12} strokeWidth={2.2} aria-hidden="true" />
                  </span>
                  <span className={styles.title}>{e.title}</span>
                  {e.severity != null && (
                    <span className={styles.gauge} title={`Severity ${e.severity}`}>
                      {[1, 2, 3, 4, 5].map((s) => (
                        <span key={s} className={styles.seg} style={{ background: s <= e.severity ? severityColor(e.severity) : undefined }} />
                      ))}
                    </span>
                  )}
                  {hasDetail && <ChevronDown size={13} className={open ? styles.chevOpen : styles.chev} aria-hidden="true" />}
                </button>
                {open && (
                  <div className={styles.detail}>
                    <span className={styles.kindLabel} style={{ color: meta.color }}>{meta.label}</span>
                    {e.description && <p className={styles.desc}>{e.description}</p>}
                    {(e.sources || []).map((url, j) => (
                      <a key={j} href={url} target="_blank" rel="noreferrer" className={styles.src}>
                        <ExternalLink size={11} strokeWidth={2} aria-hidden="true" />
                        {url.replace(/^https?:\/\/(www\.)?/, '').slice(0, 42)}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
