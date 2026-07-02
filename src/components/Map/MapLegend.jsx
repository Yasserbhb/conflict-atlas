import { useState } from 'react';
import { ChevronDown, PanelBottomOpen } from 'lucide-react';
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
  const [open, setOpen] = useState(true);

  const mode = state.focusedConflictId ? 'focus' : state.selectedCountryId ? 'country' : 'global';
  const modeLabel = mode === 'global' ? 'Overview' : mode === 'country' ? 'Country' : 'Conflict';
  const rule = mode === 'global' ? 'Fill = severity' : mode === 'country' ? 'Lines = role' : 'Fill = role';

  if (!open) {
    return (
      <button className={styles.chip} onClick={() => setOpen(true)} aria-label="Show legend" title="Show legend">
        <PanelBottomOpen size={13} strokeWidth={2} aria-hidden="true" /> Legend
      </button>
    );
  }

  return (
    <div className={styles.legend}>
      <div className={styles.head}>
        <span className={`${styles.modeChip} ${styles['mode_' + mode]}`}>{modeLabel}</span>
        <span className={styles.rule}>{rule}</span>
        <button className={styles.collapse} onClick={() => setOpen(false)} aria-label="Hide legend" title="Hide legend">
          <ChevronDown size={14} strokeWidth={2} aria-hidden="true" />
        </button>
      </div>

      <div className={styles.body}>
        {mode === 'focus' && (
          <div className={styles.section}>
            {ROLE_ITEMS.map(({ color, label }) => (
              <div key={label} className={styles.item}>
                <span className={styles.swatch} style={{ background: color }} />
                <span>{label}</span>
              </div>
            ))}
          </div>
        )}

        {mode === 'country' && (
          <div className={styles.section}>
            {ROLE_ITEMS.map(({ color, label }) => (
              <div key={label} className={styles.item}>
                <span className={styles.line} style={{ background: color }} />
                <span>{label}</span>
              </div>
            ))}
            <div className={styles.lineStyleNote}>
              <div className={styles.item}><span className={styles.lineSolid} /><span>attacks</span></div>
              <div className={styles.item}><span className={styles.lineDashed} /><span>backs / involved</span></div>
            </div>
          </div>
        )}

        {mode !== 'focus' && (
          <div className={styles.section}>
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
