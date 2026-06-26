import { SEVERITY_COLORS, TYPE_COLORS, TYPE_LABELS, ROLE_COLORS, ROLE_LABELS, CONFLICT_TYPES, ROLE_TYPES } from '../../utils/conflictColors';
import styles from './HelpView.module.css';

const SEVERITY_LABELS = ['No conflict', 'Low tension', 'Serious', 'Armed conflict', 'Mass atrocity', 'Catastrophic'];

export default function HelpView() {
  return (
    <div className={styles.view}>
      <div className={styles.inner}>
        <h1 className={styles.title}>Conflict Atlas</h1>
        <p className={styles.lead}>
          An interactive map of geopolitical conflicts, genocides, occupations, and atrocities
          from 1490 to today. Browse the world, dig into any country or conflict, scrub through
          history, and add your own notes as you learn.
        </p>

        <section className={styles.section}>
          <h2>The three ways to read the map</h2>
          <div className={styles.modeCard}>
            <span className={styles.modeDot} style={{ background: '#64748b' }} />
            <div>
              <strong>Overview</strong> — every country is shaded by <em>severity</em> (how intense its
              worst active conflict is). The faint arcs hint at who's connected.
            </div>
          </div>
          <div className={styles.modeCard}>
            <span className={styles.modeDot} style={{ background: '#3b82f6' }} />
            <div>
              <strong>Click a country</strong> — thin lines radiate to every conflict it's in (its "reach"),
              colored by <em>its role</em>. Solid = it attacks, dashed = it backs / is involved.
            </div>
          </div>
          <div className={styles.modeCard}>
            <span className={styles.modeDot} style={{ background: '#9f1239' }} />
            <div>
              <strong>Open a conflict</strong> — every country in it fills with <em>its role color</em>
              (aggressor, victim, funder…), so you read the whole structure at a glance.
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2>Country fill = severity</h2>
          <p className={styles.note}>How intense it is — not what kind. A country can be deep crimson from a war, not only a genocide.</p>
          <div className={styles.swatchRow}>
            {SEVERITY_COLORS.slice(1).map((c, i) => (
              <div key={i} className={styles.swatch}>
                <span className={styles.box} style={{ background: c }} />
                <span>{SEVERITY_LABELS[i + 1]}</span>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.section}>
          <h2>Conflict type</h2>
          <p className={styles.note}>The classification — its own separate color code, shown on arcs (overview) and type chips.</p>
          <div className={styles.swatchRow}>
            {CONFLICT_TYPES.map((t) => (
              <div key={t} className={styles.swatch}>
                <span className={styles.box} style={{ background: TYPE_COLORS[t] }} />
                <span>{TYPE_LABELS[t]}</span>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.section}>
          <h2>Roles</h2>
          <p className={styles.note}>A country's part in a conflict — drives the colors when you select a country or open a conflict.</p>
          <div className={styles.swatchRow}>
            {ROLE_TYPES.map((r) => (
              <div key={r} className={styles.swatch}>
                <span className={styles.box} style={{ background: ROLE_COLORS[r] }} />
                <span>{ROLE_LABELS[r]}</span>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.section}>
          <h2>Getting around</h2>
          <ul className={styles.list}>
            <li><strong>Left sidebar</strong> — switch between Map, Conflicts list, Stats, Timeline, and Help.</li>
            <li><strong>Timeline slider</strong> (top) — scrub 1490→2026; ▶ animates history.</li>
            <li><strong>Map</strong> — scroll to zoom, drag to pan, "Reset view" to recenter.</li>
            <li><strong>Edit mode</strong> (top bar) — add or edit conflicts and write notes per country.</li>
            <li><strong>Export / import</strong> (top bar) — save your whole dataset as JSON or load it back.</li>
          </ul>
        </section>

        <section className={styles.section}>
          <h2>About the data</h2>
          <p className={styles.note}>
            This is an educational tool, not an authoritative record. Entries are concise summaries,
            and for many events casualty figures and even classifications are genuinely debated by
            historians. Pre-modern events are mapped onto modern countries (borders are always today's).
            Treat everything as a starting point — and use Edit mode to correct and refine it.
          </p>
          <p className={styles.credit}>Map data: Natural Earth. Built with React &amp; D3.</p>
        </section>
      </div>
    </div>
  );
}
