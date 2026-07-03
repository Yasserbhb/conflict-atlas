import { useMemo, useState } from 'react';
import { ChevronDown, ExternalLink } from 'lucide-react';
import { dateToValue, formatEventDate } from '../../utils/dateUtils';
import { severityColor } from '../../utils/conflictColors';
import { kindMeta } from '../../utils/eventKinds';
import styles from './EventTimeline.module.css';

// sparkline geometry, in viewBox units
const S_W = 100, S_H = 40, S_PAD = 3;
const yForSev = (s) => S_H - S_PAD - (s / 5) * (S_H - 2 * S_PAD);

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
    return withSev.map((e) => ({
      x: S_PAD + ((dateToValue(e.date) - lo) / span) * (S_W - 2 * S_PAD),
      y: yForSev(e.severity),
      color: kindMeta(e.kind).color,
      title: e.title,
    }));
  }, [sorted, conflict]);

  const linePts = spark || [];

  // Distinct kinds present in this conflict — a small key so the point colors read.
  const kinds = useMemo(() => {
    const seen = new Set();
    const out = [];
    for (const e of sorted) {
      const k = e.kind || 'milestone';
      if (!seen.has(k)) { seen.add(k); out.push(k); }
    }
    return out;
  }, [sorted]);

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        Timeline <span className={styles.count}>{sorted.length}</span>
      </div>

      {spark && (
        <div className={styles.sparkWrap}>
          {/* the line shows only the up/down shape of severity; the dots carry the kind color */}
          <svg className={styles.spark} viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
            {linePts.length >= 2 && (
              <>
                <polyline
                  className={styles.sparkArea}
                  points={`${linePts[0].x},40 ${linePts.map((p) => `${p.x},${p.y}`).join(' ')} ${linePts[linePts.length - 1].x},40`}
                />
                <polyline
                  className={styles.sparkLine}
                  points={linePts.map((p) => `${p.x},${p.y}`).join(' ')}
                  vectorEffect="non-scaling-stroke"
                />
              </>
            )}
          </svg>
          {spark.map((p, i) => (
            <span
              key={i}
              className={styles.node}
              style={{ left: `${p.x}%`, top: `${(p.y / S_H) * 100}%`, background: p.color }}
              title={p.title}
            />
          ))}
        </div>
      )}

      {kinds.length > 0 && (
        <div className={styles.legend}>
          {kinds.map((k) => {
            const m = kindMeta(k);
            return (
              <span key={k} className={styles.legItem}>
                <span className={styles.legDot} style={{ background: m.color }} />
                {m.label}
              </span>
            );
          })}
        </div>
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
