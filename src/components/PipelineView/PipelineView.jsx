import { useMemo } from 'react';
import { Activity, AlertTriangle, CheckCircle2, EyeOff, Moon, ExternalLink } from 'lucide-react';
import coverage from '../../data/coverage.json';
import styles from './PipelineView.module.css';

// Maintainer-only. Reads the coverage ledger the weekly job publishes — the same file the Help
// page summarises for visitors, but shown here as an operations log rather than a caveat.
//
// Deliberately NOT a live dashboard: it renders a file committed by the last run. The bulky
// per-run output (full digests, proposals, eval reports) is uploaded as a GitHub Actions
// artifact instead, so the repo only ever carries the dataset itself.

const STATUS = {
  found:  { label: 'Found',  Icon: CheckCircle2,  cls: 'ok',      hint: 'events surfaced' },
  quiet:  { label: 'Quiet',  Icon: Moon,          cls: 'quiet',   hint: 'real article pool, nothing extractable' },
  blind:  { label: 'Blind',  Icon: EyeOff,        cls: 'blind',   hint: 'search returned nothing — a source gap, not proof of calm' },
  failed: { label: 'Failed', Icon: AlertTriangle, cls: 'failed',  hint: 'the scan itself errored' },
};

const meta = (s) => STATUS[s] || { label: s || 'unknown', Icon: Activity, cls: 'quiet', hint: '' };

export default function PipelineView() {
  const rows = useMemo(() => [...coverage].reverse(), []);   // newest first
  const last = rows[0];
  const failures = rows.filter((r) => r.status === 'failed').length;
  const totalHeld = rows.reduce((n, r) => n + (r.held || 0), 0);
  const totalApplied = rows.reduce((n, r) => n + (r.applied || 0), 0);

  return (
    <div className={styles.wrap}>
      <header className={styles.head}>
        <h1 className={styles.title}>Pipeline</h1>
        <p className={styles.sub}>
          What the agents did, from the coverage ledger the weekly job publishes.
          Full logs live with each run in the Actions tab, not in the repo.
        </p>
      </header>

      {!last ? (
        <div className={styles.empty}>
          No scans logged yet. Run <code>python -m conflict_updater auto week</code> to record one.
        </div>
      ) : (
        <>
          <section className={styles.cards}>
            <Card label="Last run" value={last.scanned_at} note={last.period} status={last.status} />
            <Card label="Events applied" value={totalApplied} note="written to seed.json" />
            <Card label="Held for review" value={totalHeld} note="awaiting a decision" warn={totalHeld > 0} />
            <Card label="Failed runs" value={failures} note={`of ${rows.length} logged`} warn={failures > 0} />
          </section>

          {last.status === 'failed' && (
            <div className={styles.alert}>
              <AlertTriangle size={15} strokeWidth={2.2} aria-hidden="true" />
              <div>
                <strong>The most recent run failed.</strong>
                <div className={styles.alertBody}>{last.error || 'No error recorded.'}</div>
              </div>
            </div>
          )}

          <section>
            <h2 className={styles.h2}>Run history</h2>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Scanned</th><th>Window</th><th>Region</th><th>Status</th>
                    <th className={styles.num}>Articles</th><th className={styles.num}>Found</th>
                    <th className={styles.num}>Applied</th><th className={styles.num}>Held</th>
                    <th className={styles.num}>Errored</th><th>Prompts</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const m = meta(r.status);
                    return (
                      <tr key={i}>
                        <td className={styles.mono}>{r.scanned_at}</td>
                        <td className={styles.mono}>{r.period}</td>
                        <td>{r.region}</td>
                        <td>
                          <span className={`${styles.pill} ${styles[m.cls]}`} title={m.hint}>
                            <m.Icon size={11} strokeWidth={2.2} aria-hidden="true" />{m.label}
                          </span>
                        </td>
                        <td className={`${styles.num} ${styles.mono}`}>{r.items ?? '—'}</td>
                        <td className={`${styles.num} ${styles.mono}`}>{r.events_found ?? '—'}</td>
                        <td className={`${styles.num} ${styles.mono}`}>{r.applied ?? '—'}</td>
                        <td className={`${styles.num} ${styles.mono}`}>{r.held ?? '—'}</td>
                        <td className={`${styles.num} ${styles.mono}`}>{r.failed ?? 0}</td>
                        <td className={`${styles.mono} ${styles.dim}`}>{r.prompt_version || '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className={styles.h2}>Quality</h2>
            <p className={styles.note}>
              Backtest the pipeline against the atlas's own curated events — no labelling needed,
              since every seeded event is already sourced and dated.
            </p>
            <pre className={styles.cmd}>python -m conflict_updater eval "2024..2026" --limit 20</pre>
            <p className={styles.note}>
              It reports extraction precision/recall, resolution accuracy, and <strong>Verify
              calibration</strong> — whether a stated confidence of 0.8 really means right 80% of
              the time. The auto-approve gate depends entirely on that number, so it is the one
              measurement worth running before trusting anything else here. Reports are written to{' '}
              <code>ai-updater/out/eval_*.json</code> and archived with each run.
            </p>
          </section>

          <p className={styles.footer}>
            <ExternalLink size={12} strokeWidth={2} aria-hidden="true" />
            Per-run digests, proposals and eval reports are attached to each weekly run as an
            artifact — downloadable for 90 days, never committed.
          </p>
        </>
      )}
    </div>
  );
}

function Card({ label, value, note, status, warn }) {
  const m = status ? meta(status) : null;
  return (
    <div className={`${styles.card} ${warn ? styles.cardWarn : ''}`}>
      <div className={styles.cardLabel}>{label}</div>
      <div className={styles.cardValue}>{value ?? '—'}</div>
      <div className={styles.cardNote}>
        {m && <span className={`${styles.pill} ${styles[m.cls]}`}><m.Icon size={10} strokeWidth={2.2} aria-hidden="true" />{m.label}</span>}
        {note}
      </div>
    </div>
  );
}
