import { parseYear } from '../../utils/dateUtils';
import { kindMeta } from '../../utils/eventKinds';
import styles from './EventPins.module.css';

// Plots a focused conflict's events at their real coordinates. Events reveal as the
// timeline year reaches them; the event(s) happening in the current year pulse.
export default function EventPins({ events, project, timelineYear, k }) {
  const r = 4 / k; // counter-scale so pins stay a constant size through zoom

  const pts = [];
  for (const e of events) {
    const loc = e.location;
    if (!loc || loc.lat == null || loc.lng == null) continue;
    const xy = project([loc.lng, loc.lat]);
    if (!xy) continue;
    const y = parseYear(e.date);
    pts.push({ e, x: xy[0], y: xy[1], shown: y <= timelineYear, current: y === timelineYear });
  }
  if (!pts.length) return null;

  return (
    <g>
      {pts.map(({ e, x, y, shown, current }, i) => {
        const color = kindMeta(e.kind).color;
        return (
          <g
            key={e.id || i}
            transform={`translate(${x},${y})`}
            opacity={shown ? 1 : 0.1}
            style={{ transition: 'opacity 0.5s ease' }}
          >
            {shown && current && <circle className={styles.pulse} r={r} fill={color} />}
            <circle r={r} fill={color} stroke="#0d1215" strokeWidth={1.3} vectorEffect="non-scaling-stroke" />
            <title>{e.title}</title>
          </g>
        );
      })}
    </g>
  );
}
