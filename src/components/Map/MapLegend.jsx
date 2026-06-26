import { SEVERITY_COLORS, ROLE_COLORS } from '../../utils/conflictColors';
import { useApp } from '../../context/AppContext';
import styles from './MapLegend.module.css';

const SEVERITY_LABELS = ['No conflict', 'Low tension', 'Serious', 'Armed conflict', 'Mass atrocity', 'Catastrophic'];

const ROLE_ITEMS = [
  { color: ROLE_COLORS.aggressor,  label: 'Aggressor / Occupier' },
  { color: ROLE_COLORS.victim,     label: 'Victim / Defender' },
  { color: ROLE_COLORS.funder,     label: 'Funder / Proxy' },
  { color: ROLE_COLORS.sanctioner, label: 'Sanctioner' },
  { color: ROLE_COLORS.mediator,   label: 'Mediator' },
];

export default function MapLegend() {
  const { state } = useApp();
  const { selectedCountryId, focusedConflictId, countries, conflicts } = state;

  const country = selectedCountryId
    ? countries.find((c) => c.id === selectedCountryId)
    : null;
  const focused = focusedConflictId
    ? conflicts.find((c) => c.id === focusedConflictId)
    : null;

  // Determine mode + banner copy
  let mode, bannerTitle, bannerSub, arcMeaning;
  if (focused) {
    mode = 'focus';
    bannerTitle = focused.title;
    bannerSub = 'Each country colored by its role';
    arcMeaning = 'Country color = role';
  } else if (country) {
    mode = 'country';
    bannerTitle = country.name;
    bannerSub = 'Lines = its reach. Click a conflict for roles.';
    arcMeaning = `Line color = ${country.name}'s role`;
  } else {
    mode = 'global';
    bannerTitle = 'All conflicts';
    bannerSub = 'Click a country to begin';
    arcMeaning = 'Country fill = severity';
  }

  return (
    <div className={styles.legend}>
      {/* Loud mode banner — always says what you're looking at + the color rule */}
      <div className={`${styles.banner} ${styles['banner_' + mode]}`}>
        <div className={styles.bannerMode}>
          {mode === 'global' ? 'OVERVIEW' : mode === 'country' ? 'COUNTRY' : 'CONFLICT'}
        </div>
        <div className={styles.bannerTitle}>{bannerTitle}</div>
        <div className={styles.bannerSub}>{bannerSub}</div>
        <div className={styles.bannerRule}><strong>{arcMeaning}</strong></div>
      </div>

      <div className={styles.swatches}>
        {/* FOCUS: role colors as country fills */}
        {mode === 'focus' && (
          <div className={styles.section}>
            <div className={styles.title}>Country color = role</div>
            {ROLE_ITEMS.map(({ color, label }) => (
              <div key={label} className={styles.item}>
                <span className={styles.swatch} style={{ background: color }} />
                <span>{label}</span>
              </div>
            ))}
          </div>
        )}

        {/* COUNTRY: reach lines colored by role + solid/dashed meaning */}
        {mode === 'country' && (
          <div className={styles.section}>
            <div className={styles.title}>Reach lines</div>
            {ROLE_ITEMS.map(({ color, label }) => (
              <div key={label} className={styles.item}>
                <span className={styles.line} style={{ background: color }} />
                <span>{label}</span>
              </div>
            ))}
            <div className={styles.lineStyleNote}>
              <div className={styles.item}>
                <span className={styles.lineSolid} />
                <span>attacks</span>
              </div>
              <div className={styles.item}>
                <span className={styles.lineDashed} />
                <span>backs / involved</span>
              </div>
            </div>
          </div>
        )}

        {/* Severity scale — shown in overview and country modes */}
        {mode !== 'focus' && (
          <div className={styles.section}>
            <div className={styles.title}>Country fill = severity</div>
            {SEVERITY_COLORS.slice(1).map((color, i) => (
              <div key={i} className={styles.item}>
                <span className={styles.swatch} style={{ background: color }} />
                <span>{SEVERITY_LABELS[i + 1]}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
