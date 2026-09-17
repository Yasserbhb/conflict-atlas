import { useMemo } from 'react';
import { Activity, AlertTriangle, CheckCircle2, EyeOff, Moon, ExternalLink, Plus, Pause } from 'lucide-react';
import coverage from '../../data/coverage.json';
import evalHistory from '../../data/eval-history.json';
import latestRun from '../../data/latest-run.json';
import styles from './PipelineView.module.css';

// The agents' operations log, from the coverage ledger the weekly job publishes. Shown to
// everyone: the atlas's claim is data rigour, and most projects making that claim can't show
// their working. This can — including the weeks that found nothing and the runs that failed.
//
// Deliberately NOT a live dashboard: it renders a file committed by the last run. The bulky
// per-run output (full digests, proposals, eval reports) is uploaded as a GitHub Actions
// artifact instead, so the repo only ever carries the dataset itself.

const REPO = 'https://github.com/Yasserbhb/conflict-atlas';

const STATUS = {
  found:  { label: 'Found',  Icon: CheckCircle2,  cls: 'ok',      hint: 'events surfaced' },
  quiet:  { label: 'Quiet',  Icon: Moon,          cls: 'quiet',   hint: 'real article pool, nothing extractable' },
  blind:  { label: 'Blind',  Icon: EyeOff,        cls: 'blind',   hint: 'search returned nothing — a source gap, not proof of calm' },
  failed: { label: 'Failed', Icon: AlertTriangle, cls: 'failed',  hint: 'the scan itself errored' },
};

const meta = (s) => STATUS[s] || { label: s || 'unknown', Icon: Activity, cls: 'quiet', hint: '' };

const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);

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
        <a className={styles.actionsLink} href={`${REPO}/actions/workflows/pipeline-daily.yml`}
           target="_blank" rel="noreferrer">
          <ExternalLink size={12} strokeWidth={2} aria-hidden="true" />
          Open the weekly run history on GitHub
        </a>
      </header>

      {!last ? (
        <div className={styles.empty}>
          Nothing logged yet — the agents haven't completed a run.
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

          <LastRun run={latestRun} />

          <section>
            <h2 className={styles.h2}>Run history</h2>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Scanned</th><th>Window</th><th>Region</th><th>Status</th>
                    <th className={styles.num}>Articles</th><th className={styles.num}>Found</th>
                    <th className={styles.num}>Applied</th><th className={styles.num}>Held</th>
                    <th className={styles.num}>Errored</th><th>Prompts</th><th>Logs</th>
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
                        <td>
                          {r.run_url
                            ? <a className={styles.rowLink} href={r.run_url} target="_blank" rel="noreferrer">
                                view run <ExternalLink size={10} strokeWidth={2} aria-hidden="true" />
                              </a>
                            : <span className={styles.dim}>local</span>}
                        </td>
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
              Running is not the same as being right. The pipeline is backtested against the
              atlas's own curated events: hold out every event in a window, rescan that window,
              and score what comes back. No labelling is needed — every seeded event is already
              sourced and dated.
            </p>

            {evalHistory.length === 0 ? (
              <div className={styles.empty}>
                <strong>Not measured yet.</strong> No backtest has been published, so nothing on
                this page should be read as evidence that the agents are accurate — only that
                they ran.
              </div>
            ) : (
              <>
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Ran</th><th>Window</th>
                        <th className={styles.num}>Events</th>
                        <th className={styles.num}>Precision</th><th className={styles.num}>Recall</th>
                        <th className={styles.num}>F1</th><th className={styles.num}>Resolution</th>
                        <th className={styles.num}>Kind</th><th className={styles.num}>Severity ±1</th>
                        <th>Prompts</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...evalHistory].reverse().map((e, i) => (
                        <tr key={i}>
                          <td className={styles.mono}>{e.ran_at}</td>
                          <td className={styles.mono}>{e.period}</td>
                          <td className={`${styles.num} ${styles.mono}`}>{e.gold ?? '—'}</td>
                          <td className={`${styles.num} ${styles.mono}`}>{pct(e.precision)}</td>
                          <td className={`${styles.num} ${styles.mono}`}>{pct(e.recall)}</td>
                          <td className={`${styles.num} ${styles.mono}`}>{pct(e.f1)}</td>
                          <td className={`${styles.num} ${styles.mono}`}>{pct(e.resolution_accuracy)}</td>
                          <td className={`${styles.num} ${styles.mono}`}>{pct(e.kind_accuracy)}</td>
                          <td className={`${styles.num} ${styles.mono}`}>{pct(e.severity_within_1)}</td>
                          <td className={`${styles.mono} ${styles.dim}`}>{e.prompt_version || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Calibration rows={evalHistory[evalHistory.length - 1].calibration || []} />
              </>
            )}
          </section>

          <section>
            <h2 className={styles.h2}>Where the logs are</h2>
            <p className={styles.note}>
              Each row above links to the run that produced it. On a run's page you get three
              things, none of which are stored in the repo:
            </p>
            <ul className={styles.where}>
              <li>
                <strong>Summary</strong> — a rendered report of that week: what was found,
                applied, held, and the digest. This is the page to read.
              </li>
              <li>
                <strong>The job's step output</strong> — expand
                <em> Scan the week…</em> for the pipeline's actual console output, candidate by
                candidate. This is your terminal.
              </li>
              <li>
                <strong>Artifacts</strong> (bottom of the page) —
                <code>pipeline-run-N.zip</code> with the full digests, proposals and eval
                reports. Downloadable for 90 days.
              </li>
            </ul>
            <p className={styles.note}>
              A run is only red when the scan itself failed — the blind-window row is committed
              first either way, so this table never goes quietly out of date.
            </p>
          </section>
        </>
      )}
    </div>
  );
}

// Whether a stated confidence actually means what it says. The auto-approve gate is a single
// threshold on this number, so if the model claims 0.85 and is right half the time, everything
// that gets published rests on a number that means nothing.
// Last week's actual findings, rendered here rather than behind a link. The same content the
// markdown digest carries, shaped as JSON by the pipeline so it can be read without leaving.
function LastRun({ run }) {
  if (!run || !run.ran_at) return null;
  const added = run.added || [];
  const held = run.held || [];
  if (!added.length && !held.length) return null;
  return (
    <section>
      <h2 className={styles.h2}>What the last run found</h2>
      <p className={styles.note}>
        {run.period} · {added.length} added to the atlas, {held.length} held back.
      </p>

      {added.length > 0 && (
        <>
          <h3 className={styles.h3}><Plus size={12} strokeWidth={2.5} aria-hidden="true" /> Added</h3>
          <ul className={styles.findings}>
            {added.map((e, i) => (
              <li key={i}>
                <span className={styles.fDate}>{e.date}</span>
                <span className={styles.fTitle}>{e.title}</span>
                <span className={styles.fMeta}>{e.kind} · severity {e.severity} · {e.conflict}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {held.length > 0 && (
        <>
          <h3 className={styles.h3}><Pause size={12} strokeWidth={2.5} aria-hidden="true" /> Held back</h3>
          <p className={styles.note}>
            Found, but not corroborated well enough to publish. Each one names the question that
            stopped it.
          </p>
          <ul className={styles.findings}>
            {held.map((e, i) => (
              <li key={i}>
                <span className={styles.fDate}>{e.date}</span>
                <span className={styles.fTitle}>{e.title}</span>
                {e.question && <span className={styles.fQuestion}>{e.question}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function Calibration({ rows }) {
  if (!rows.length) return null;
  return (
    <>
      <h3 className={styles.h3}>Is the agents' confidence honest?</h3>
      <p className={styles.note}>
        Events are published automatically when the fact-checker's confidence clears a fixed bar.
        That only means something if a stated 80% really is right 80% of the time.
      </p>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Stated confidence</th><th className={styles.num}>Events</th>
              <th className={styles.num}>Claimed</th><th className={styles.num}>Actually right</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const gap = r.observed - r.stated_mid;
              const weak = r.n < 5;
              const label = weak ? 'too few to tell'
                : gap < -0.15 ? 'overconfident'
                : gap > 0.15 ? 'underconfident'
                : 'well calibrated';
              const cls = weak ? 'quiet' : gap < -0.15 ? 'failed' : gap > 0.15 ? 'blind' : 'ok';
              return (
                <tr key={i}>
                  <td className={styles.mono}>{r.range}</td>
                  <td className={`${styles.num} ${styles.mono}`}>{r.n}</td>
                  <td className={`${styles.num} ${styles.mono}`}>{pct(r.stated_mid)}</td>
                  <td className={`${styles.num} ${styles.mono}`}>{pct(r.observed)}</td>
                  <td><span className={`${styles.pill} ${styles[cls]}`}>{label}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
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
