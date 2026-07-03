import { X, Network, Pencil, ExternalLink } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { TYPE_LABELS, TYPE_COLORS, ROLE_LABELS, roleColor, severityColor } from '../../utils/conflictColors';
import { formatDateRange } from '../../utils/dateUtils';
import { flagEmoji } from '../../utils/flags';
import { TypeIcon } from '../../utils/typeIcons';
import EventTimeline from './EventTimeline';
import styles from './ConflictDetailPanel.module.css';

const SIDES = [
  { label: 'Aggressors', roles: ['aggressor', 'occupier'] },
  { label: 'Victims & defenders', roles: ['victim', 'defender', 'sanctioned'] },
  { label: 'Backers', roles: ['funder', 'proxy', 'sanctioner'] },
  { label: 'Mediators', roles: ['mediator'] },
];

export default function ConflictDetailPanel() {
  const { state, dispatch } = useApp();
  const { openConflictId, conflicts, countries, mode } = state;

  const conflict = conflicts.find((c) => c.id === openConflictId);
  if (!conflict) return null;

  const country = (id) => countries.find((c) => c.id === id);
  const typeColor = TYPE_COLORS[conflict.type] || '#94a3b8';

  const partiesByRole = {};
  for (const p of conflict.parties || []) {
    (partiesByRole[p.role] = partiesByRole[p.role] || []).push(p);
  }

  const wikiUrl = `https://en.wikipedia.org/wiki/Special:Search?search=${encodeURIComponent(conflict.title)}`;
  const hasSources = (conflict.sources || []).length > 0;

  return (
    <div className={styles.panel}>
      <div className={styles.accent} style={{ background: `linear-gradient(90deg, ${typeColor}, transparent)` }} />

      <div className={styles.header}>
        <span className={styles.glyph} style={{ background: typeColor + '22', color: typeColor }}>
          <TypeIcon type={conflict.type} size={17} aria-hidden="true" />
        </span>
        <div className={styles.headMain}>
          <div className={styles.title}>{conflict.title}</div>
          <div className={styles.sub}>
            <span style={{ color: typeColor }}>{TYPE_LABELS[conflict.type] || conflict.type}</span>
            <span className={styles.dot}>·</span>
            <span>{formatDateRange(conflict.startDate, conflict.endDate, conflict.ongoing)}</span>
            {conflict.ongoing && <span className={styles.live}>● live</span>}
          </div>
        </div>
        <button className={styles.closeBtn} onClick={() => dispatch({ type: 'CLOSE_CONFLICT' })} aria-label="Close" title="Close"><X size={15} strokeWidth={2.2} aria-hidden="true" /></button>
      </div>

      <div className={styles.severityRow}>
        <span className={styles.sevLabel}>Severity</span>
        <span className={styles.gauge}>
          {[1, 2, 3, 4, 5].map((s) => (
            <span key={s} className={styles.gaugeSeg} style={{ background: s <= conflict.severity ? severityColor(conflict.severity) : undefined }} />
          ))}
        </span>
      </div>

      <div className={styles.body}>
        {conflict.description && <p className={styles.description}>{conflict.description}</p>}

        {conflict.events?.length > 0 && <EventTimeline events={conflict.events} conflict={conflict} />}

        {/* Parties grouped by side */}
        {SIDES.map(({ label, roles }) => {
          const members = roles.flatMap((r) => partiesByRole[r] || []);
          if (members.length === 0) return null;
          return (
            <div key={label} className={styles.side}>
              <div className={styles.sideLabel}>{label}</div>
              <div className={styles.partyList}>
                {members.map((p) => {
                  const c = country(p.countryId);
                  const rc = roleColor(p.role);
                  return (
                    <button
                      key={p.countryId}
                      className={styles.party}
                      onClick={() => dispatch({ type: 'SELECT_COUNTRY', payload: p.countryId })}
                      title={`Go to ${c?.name || p.countryId}`}
                    >
                      <span className={styles.partyFlag}>{c?.iso2 ? flagEmoji(c.iso2) : '🏳'}</span>
                      <span className={styles.partyName}>{c?.name || p.countryId}</span>
                      <span className={styles.partyRole} style={{ color: rc, borderColor: rc + '66' }}>
                        {ROLE_LABELS[p.role] || p.role}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}

        {conflict.tags?.length > 0 && (
          <div className={styles.tags}>
            {conflict.tags.map((t) => <span key={t} className={styles.tag}>#{t}</span>)}
          </div>
        )}

        {/* Sources */}
        <div className={styles.sources}>
          <div className={styles.sourcesLabel}>Sources</div>
          {hasSources
            ? conflict.sources.map((url, i) => (
                <a key={i} href={url} target="_blank" rel="noreferrer" className={styles.sourceLink}>
                  <ExternalLink size={12} strokeWidth={2} aria-hidden="true" />
                  {url.replace(/^https?:\/\/(www\.)?/, '').slice(0, 46)}
                </a>
              ))
            : (
              <p className={styles.unsourced}>
                No primary sources cited yet — this entry is a curated summary. Treat it as a
                starting point and verify before relying on it.
              </p>
            )}
          <a href={wikiUrl} target="_blank" rel="noreferrer" className={styles.wikiLink}>
            <ExternalLink size={13} strokeWidth={2} aria-hidden="true" /> Look it up on Wikipedia
          </a>
        </div>
      </div>

      <div className={styles.footer}>
        {mode === 'edit' && (
          <button className={styles.editBtn} onClick={() => dispatch({ type: 'OPEN_EDIT', payload: { kind: 'conflict', data: conflict } })}>
            <Pencil size={13} strokeWidth={2} aria-hidden="true" /> Edit
          </button>
        )}
        <button className={styles.graphBtn} onClick={() => {
          const first = conflict.parties?.[0]?.countryId;
          if (first) dispatch({ type: 'SELECT_COUNTRY', payload: first });
          dispatch({ type: 'SHOW_GRAPH' });
        }}>
          <Network size={14} strokeWidth={2} aria-hidden="true" /> Network Graph
        </button>
      </div>
    </div>
  );
}
