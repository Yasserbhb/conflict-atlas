import { SEVERITY_COLORS, TYPE_COLORS, TYPE_LABELS, ROLE_COLORS, ROLE_LABELS, CONFLICT_TYPES, ROLE_TYPES } from '../../utils/conflictColors';
import { SEVERITY_LEVELS, TYPE_DEFINITIONS, ROLE_DEFINITIONS } from '../../utils/taxonomy';
import styles from './HelpView.module.css';

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
          <h2>Severity — how intense</h2>
          <p className={styles.note}>
            A 1–5 measure of <em>intensity</em>, not category — a war and a genocide can both be a 5.
            The figures below are rough guides for consistency, not strict legal thresholds. Country
            fill on the map always shows a country's <strong>worst active</strong> severity.
          </p>
          <div className={styles.defList}>
            {SEVERITY_LEVELS.map((s) => (
              <div key={s.level} className={styles.defRow}>
                <span className={styles.defBox} style={{ background: SEVERITY_COLORS[s.level] }}>{s.level}</span>
                <div className={styles.defText}>
                  <span className={styles.defTerm}>{s.label}</span>
                  <span className={styles.defDef}>{s.definition}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.section}>
          <h2>Conflict type — what kind</h2>
          <p className={styles.note}>The classification of an event. Its own separate color code, shown on arcs (overview) and type chips.</p>
          <div className={styles.defList}>
            {CONFLICT_TYPES.map((t) => (
              <div key={t} className={styles.defRow}>
                <span className={styles.defBox} style={{ background: TYPE_COLORS[t] }} />
                <div className={styles.defText}>
                  <span className={styles.defTerm}>{TYPE_LABELS[t]}</span>
                  <span className={styles.defDef}>{TYPE_DEFINITIONS[t]}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.section}>
          <h2>Roles — who did what</h2>
          <p className={styles.note}>Each country's part in a conflict. Roles drive the colors when you select a country or open a conflict.</p>
          <div className={styles.defList}>
            {ROLE_TYPES.map((r) => (
              <div key={r} className={styles.defRow}>
                <span className={styles.defBox} style={{ background: ROLE_COLORS[r] }} />
                <div className={styles.defText}>
                  <span className={styles.defTerm}>{ROLE_LABELS[r]}</span>
                  <span className={styles.defDef}>{ROLE_DEFINITIONS[r]}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.section}>
          <h2>Methodology</h2>
          <p className={styles.note}>
            How entries are built — so you know what the colors and numbers do and don't mean.
          </p>
          <ul className={styles.list}>
            <li><strong>Severity is intensity, not kind.</strong> It's scored on the 1–5 scale above from the human toll and scale of fighting, independent of the type. Where casualty figures are disputed, the entry leans toward the range most historians accept and rounds conservatively.</li>
            <li><strong>Roles are analytical judgments.</strong> "Aggressor," "victim," "funder" and the rest are assigned from the definitions above. Who "started it" is often exactly what a conflict is fought over — these labels are a reading of the record, not a verdict, and reasonable sources disagree.</li>
            <li><strong>Type is the primary character</strong> of an event. Many conflicts genuinely fit more than one (a civil war with genocidal phases); each entry is filed under its most defining type and the detail text notes the rest.</li>
            <li><strong>Borders are always today's.</strong> Pre-modern events are mapped onto the modern countries that occupy that land, so a 1490 event appears on a 2026 map. This is a deliberate simplification and distorts historical geography.</li>
            <li><strong>Dating.</strong> Start / end years mark the main active period. "Ongoing" means active as of 2026. Frozen disputes keep their original start year.</li>
            <li><strong>Sources &amp; limits.</strong> Entries are concise, single-curator summaries meant as a <em>starting point</em> — not a citable authority. Where a conflict has sources attached they're listed in its detail panel; many don't yet. Use Edit mode to correct, cite, and refine anything.</li>
          </ul>
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

        <p className={styles.credit}>Map data: Natural Earth. Built with React &amp; D3.</p>
      </div>
    </div>
  );
}
