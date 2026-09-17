import { useMemo, useState } from 'react';
import {
  Activity, AlertTriangle, CheckCircle2, EyeOff, Moon, ExternalLink, Plus, Pause, Clock,
} from 'lucide-react';
import coverage from '../../data/coverage.json';
import evalHistory from '../../data/eval-history.json';
import latestRun from '../../data/latest-run.json';
import * as cov from './coverage';
import styles from './PipelineView.module.css';

// The agents' operations log, from the coverage ledger the daily job publishes. Shown to
// everyone: the atlas's claim is data rigour, and most projects making that claim can't show
// their working. This can — including the days that found nothing and the runs that failed.
//
// Built around ONE question: is it working today? The cursor appends a row per day, so a year of
// running is ~365 rows. A table that long answers that question badly, which is why the calendar
// is the centrepiece and the table is the appendix.
//
// Deliberately NOT a live dashboard: it renders a file committed by the last run.

const REPO = 'https://github.com/Yasserbhb/conflict-atlas';
const SETTLE_DAYS = 7;          // T_SETTLE_DAYS — mirrors config.py
const DAYS_PER_RUN = 3;         // PIPELINE_MAX_DAYS_PER_RUN
const HISTORY_ROWS = 40;        // the table is the appendix; the calendar is the story

const STATUS = {
  found:  { label: 'Found',  Icon: CheckCircle2,  cls: 'ok',     hint: 'events surfaced' },
  quiet:  { label: 'Quiet',  Icon: Moon,          cls: 'quiet',  hint: 'real article pool, nothing extractable' },
  blind:  { label: 'Blind',  Icon: EyeOff,        cls: 'blind',  hint: 'search returned nothing — a source gap, not proof of calm' },
  failed: { label: 'Failed', Icon: AlertTriangle, cls: 'failed', hint: 'the scan itself errored' },
};

const meta = (s) => STATUS[s] || { label: s || 'unknown', Icon: Activity, cls: 'quiet', hint: '' };
const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const cellCls = (c) => `cell${c[0].toUpperCase()}${c.slice(1)}`;

const daysSince = (isoDay, today) => Math.round((today - cov.parse(isoDay)) / 86400000);

function ago(isoDay, today) {
  if (!isoDay) return null;
  const n = daysSince(isoDay, today);
  return n <= 0 ? 'today' : n === 1 ? 'yesterday' : `${n} days ago`;
}

export default function PipelineView() {
  const today = useMemo(() => cov.parse(cov.iso(new Date())), []);
  const days = useMemo(() => cov.byDay(coverage), []);
  const rangeRows = useMemo(() => cov.ranges(coverage), []);
  const rows = useMemo(() => [...coverage].reverse(), []);   // newest attempt first
  const [showAll, setShowAll] = useState(false);

  const last = rows[0];
  const win = useMemo(() => cov.window(days, today, SETTLE_DAYS), [days, today]);
  const prog = useMemo(() => cov.progress(days, win.from, win.horizon, DAYS_PER_RUN), [days, win]);

  const failures = rows.filter((r) => r.status === 'failed').length;
  const totalHeld = rows.reduce((n, r) => n + (r.held || 0), 0);
  const totalApplied = rows.reduce((n, r) => n + (r.applied || 0), 0);
  // "Ran recently" is the health signal, not "ran successfully" — nine dead weeks went unnoticed
  // precisely because this page showed the last GOOD run and said nothing about the silence since.
  const lastRan = rows.find((r) => r.scanned_at)?.scanned_at;
  const stale = lastRan ? (today - cov.parse(lastRan)) / 86400000 >= 2 : true;

  return (
    <div className={styles.wrap}>
      <header className={styles.head}>
        <div className={styles.headRow}>
          <h1 className={styles.title}>Pipeline</h1>
          <a className={styles.actionsLink} href={`${REPO}/actions/workflows/pipeline-daily.yml`}
             target="_blank" rel="noreferrer">
            <ExternalLink size={11} strokeWidth={2} aria-hidden="true" />run history
          </a>
        </div>
        <p className={styles.sub}>
          Every day the agents take the oldest day nobody has checked yet, plus the most recent
          settled one, search it, and add only what holds up. This is that log, misses included.
        </p>
      </header>

      <HealthStrip last={last} lastRan={lastRan} stale={stale} today={today} prog={prog} />

      {last?.status === 'failed' && (
        <div className={styles.alert}>
          <AlertTriangle size={14} strokeWidth={2.2} aria-hidden="true" />
          <div>
            <strong>The most recent run failed.</strong>
            <div className={styles.alertBody}>{last.error || 'No error recorded.'}</div>
          </div>
        </div>
      )}

      <Calendar days={days} win={win} prog={prog} />

      <section className={styles.cards}>
        <Card label="Events added" value={totalApplied} note="written to the atlas" />
        <Card label="Held back" value={totalHeld} note="not corroborated enough" warn={totalHeld > 0} />
        <Card label="Days covered" value={`${prog.checked}/${prog.total}`} note={`${prog.remaining} still to check`} />
        <Card label="Failed runs" value={failures} note={`of ${rows.length} logged`} warn={failures > 0} />
      </section>

      <Trends days={days} />

      <LastRun run={latestRun} today={today} />

      <section>
        <div className={styles.h2Row}>
          <h2 className={styles.h2}>Every run</h2>
          {rows.length > HISTORY_ROWS && (
            <button type="button" className={styles.toggle} onClick={() => setShowAll((v) => !v)}>
              {showAll ? `show latest ${HISTORY_ROWS}` : `show all ${rows.length}`}
            </button>
          )}
        </div>
        <RunTable rows={showAll ? rows : rows.slice(0, HISTORY_ROWS)} />
        {rangeRows.length > 0 && (
          <p className={styles.note}>
            {rangeRows.length} of these are manual range scans of deep history
            ({rangeRows.map((r) => r.period).join(', ')}), run by hand rather than by the daily
            cursor. They cover a whole span in one pass, so they have no single day on the calendar.
          </p>
        )}
      </section>

      <Quality />

      <p className={styles.footer}>
        A run is only red when the scan itself failed. A blind or empty day is still recorded — the
        ledger is written before the run is allowed to fail, so this page cannot quietly go out of
        date the way it did for nine weeks.
      </p>
    </div>
  );
}

/* ---- is it working right now? ------------------------------------------------------------- */

function HealthStrip({ last, lastRan, stale, today, prog }) {
  const m = last ? meta(last.status) : null;
  return (
    <div className={`${styles.health} ${stale ? styles.healthStale : ''}`}>
      <span className={`${styles.dot} ${stale ? styles.dotStale : styles.dotOk}`} />
      <div className={styles.healthMain}>
        <strong>
          {!lastRan ? 'Never run'
            : stale ? `Silent for ${daysSince(lastRan, today)} days`
            : `Ran ${ago(lastRan, today)}`}
        </strong>
        {last && (
          <span className={styles.healthMeta}>
            last checked <span className={styles.mono}>{last.period}</span>
            {m && (
              <span className={`${styles.pill} ${styles[m.cls]}`} title={m.hint}>
                <m.Icon size={10} strokeWidth={2.2} aria-hidden="true" />{m.label}
              </span>
            )}
          </span>
        )}
      </div>
      <div className={styles.healthRight}>
        <Clock size={11} strokeWidth={2} aria-hidden="true" />
        next run 06:00 UTC
        {prog.remaining > 0 && <> · backlog clears in ~{prog.etaRuns} runs</>}
      </div>
    </div>
  );
}

/* ---- the calendar: one cell per day -------------------------------------------------------- */

function Calendar({ days, win, prog }) {
  const cols = useMemo(() => cov.weeks(win.from, win.to), [win]);
  const [hover, setHover] = useState(null);

  const detail = hover ? days.get(hover) : null;
  const pctDone = prog.total ? Math.round((prog.checked / prog.total) * 100) : 0;

  return (
    <section>
      <div className={styles.h2Row}>
        <h2 className={styles.h2}>Day by day</h2>
        <span className={styles.h2Note}>{prog.checked} of {prog.total} days checked · {pctDone}%</span>
      </div>
      <div className={styles.bar}><span style={{ width: `${pctDone}%` }} /></div>

      <div className={styles.calWrap}>
        <div className={styles.calMonths}>
          {cols.map((w, i) => {
            const newMonth = i === 0 || w[0].getUTCMonth() !== cols[i - 1][0].getUTCMonth();
            return <span key={i} className={styles.calMonth}>{newMonth ? MONTHS[w[0].getUTCMonth()] : ''}</span>;
          })}
        </div>
        <div className={styles.cal} onMouseLeave={() => setHover(null)}>
          {cols.map((week, i) => (
            <div key={i} className={styles.calCol}>
              {week.map((d) => {
                const key = cov.iso(d);
                const row = days.get(key);
                const outside = d < win.from || d > win.horizon;
                const cls = outside ? 'cellOff' : row ? cellCls(meta(row.status).cls) : 'cellTodo';
                const label = outside ? `${key} — outside the window`
                  : row ? `${key} — ${meta(row.status).label}`
                  : `${key} — not checked yet`;
                return (
                  <i key={key}
                     className={`${styles.cell} ${styles[cls]} ${hover === key ? styles.cellOn : ''}`}
                     title={label}
                     onMouseEnter={() => !outside && setHover(key)} />
                );
              })}
            </div>
          ))}
        </div>
      </div>

      <div className={styles.calFoot}>
        {hover ? (
          <span className={styles.calDetail}>
            <span className={styles.mono}>{hover}</span>
            {detail ? (
              <>
                <span className={`${styles.pill} ${styles[meta(detail.status).cls]}`}>
                  {meta(detail.status).label}
                </span>
                <span className={styles.dim}>
                  {detail.items ?? 0} articles · {detail.events_found ?? 0} candidates
                  {detail.applied ? ` · ${detail.applied} added` : ''}
                  {detail.held ? ` · ${detail.held} held` : ''}
                  {detail.attempts > 1 ? ` · ${detail.attempts} attempts` : ''}
                </span>
              </>
            ) : (
              <span className={styles.dim}>not checked yet — the cursor hasn&apos;t reached it</span>
            )}
          </span>
        ) : (
          <span className={styles.legend}>
            {Object.keys(STATUS).map((k) => (
              <span key={k} className={styles.legendItem} title={STATUS[k].hint}>
                <i className={`${styles.cell} ${styles[cellCls(STATUS[k].cls)]}`} />{STATUS[k].label}
              </span>
            ))}
            <span className={styles.legendItem}>
              <i className={`${styles.cell} ${styles.cellTodo}`} />not checked
            </span>
            <span className={styles.legendItem} title={`Events newer than ${SETTLE_DAYS} days are still provisional`}>
              <i className={`${styles.cell} ${styles.cellOff}`} />too recent to settle
            </span>
          </span>
        )}
      </div>
    </section>
  );
}

/* ---- cost and yield, day by day --------------------------------------------------------- */

// What a week of running actually cost and produced. The ledger is the only durable per-run
// record — latest_run.json is overwritten every run — so this is the one place a trend can come
// from. `queries` is the billed search count: the number that matters when the bill arrives, and
// the one nobody could check when 110 searches appeared unexplained.
const TRENDS = [
  { key: 'queries', label: 'Searches', note: 'billed per query' },
  { key: 'items', label: 'Articles', note: 'returned by search' },
  { key: 'triaged_out', label: 'Dropped early', note: 'before any LLM spend' },
  { key: 'applied', label: 'Events added', note: 'cleared every gate' },
];

function Trends({ days }) {
  const all = useMemo(() => TRENDS.map((t) => ({ ...t, pts: cov.series(days, t.key) })), [days]);
  // Nothing has run day-wise yet: an empty chart says less than no chart.
  if (!all[0].pts.length) return null;
  const nDays = all[0].pts.length;

  return (
    <section>
      <div className={styles.h2Row}>
        <h2 className={styles.h2}>Cost and yield</h2>
        <span className={styles.h2Note}>over {nDays} checked {nDays === 1 ? 'day' : 'days'}</span>
      </div>
      <div className={styles.trends}>
        {all.map((t) => (
          <div key={t.key} className={styles.trend}>
            <div className={styles.cardLabel}>{t.label}</div>
            <div className={styles.trendTop}>
              <span className={styles.cardValue}>{cov.total(t.pts)}</span>
              <span className={styles.trendAvg}>
                {(cov.total(t.pts) / nDays).toFixed(1)}/day
              </span>
            </div>
            <Spark pts={t.pts} />
            <div className={styles.cardNote}>{t.note}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

// A bar per day. Inline SVG rather than a charting library: four sparklines do not justify a
// dependency, and the atlas already ships enough JavaScript.
function Spark({ pts }) {
  const max = Math.max(1, ...pts.map((p) => p.value));
  const w = 3, gap = 1.6;
  const width = pts.length * (w + gap);
  return (
    <svg className={styles.spark} viewBox={`0 0 ${width} 24`} preserveAspectRatio="none"
         role="img" aria-label={`${pts.length} days, highest ${max}`}>
      {pts.map((p, i) => {
        const h = Math.max(1, (p.value / max) * 22);
        return (
          <rect key={p.day} x={i * (w + gap)} y={24 - h} width={w} height={h} rx="1"
                className={p.status === 'failed' ? styles.sparkBad : styles.sparkBar}>
            <title>{`${p.day}: ${p.value}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}

/* ---- what the last run actually did -------------------------------------------------------- */

const FUNNEL = [
  ['queries', 'searches'],
  ['items', 'articles'],
  ['candidates', 'candidates'],
  ['proposals', 'fact-checked'],
];

function LastRun({ run, today }) {
  if (!run || !run.ran_at) return null;
  const added = run.added || [];
  const held = run.held || [];
  const s = run.stats || {};
  const steps = FUNNEL.filter(([k]) => s[k] != null);

  return (
    <section>
      <div className={styles.h2Row}>
        <h2 className={styles.h2}>The last run, step by step</h2>
        <span className={styles.h2Note}>
          <span className={styles.mono}>{run.period}</span> · {ago(run.ran_at, today)}
        </span>
      </div>

      {steps.length > 0 && (
        <div className={styles.funnel}>
          {steps.map(([k, label], i) => (
            <span key={k} className={styles.step}>
              {i > 0 && <span className={styles.arrow}>→</span>}
              <span className={styles.stepN}>{s[k]}</span>
              <span className={styles.stepL}>{label}</span>
            </span>
          ))}
          <span className={styles.step}>
            <span className={styles.arrow}>→</span>
            <span className={`${styles.stepN} ${styles.stepAdd}`}>{added.length}</span>
            <span className={styles.stepL}>added</span>
          </span>
          <span className={styles.step}>
            <span className={styles.plus}>+</span>
            <span className={`${styles.stepN} ${styles.stepHold}`}>{held.length}</span>
            <span className={styles.stepL}>held</span>
          </span>
        </div>
      )}

      {s.triaged_out > 0 && (
        <p className={styles.note}>
          {s.triaged_out} of those articles were dropped before any expensive step, by a typed
          relevance judgement rather than a language model reading all of them.
          {s.out_of_window > 0 && ` ${s.out_of_window} more described events outside the day being scanned.`}
        </p>
      )}

      {added.length > 0 && (
        <>
          <h3 className={styles.h3}><Plus size={12} strokeWidth={2.5} aria-hidden="true" />Added to the atlas</h3>
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
          <h3 className={styles.h3}><Pause size={12} strokeWidth={2.5} aria-hidden="true" />Held back</h3>
          <p className={styles.note}>
            Found, but not corroborated well enough to publish. Each one names what stopped it.
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

      {!added.length && !held.length && (
        <p className={styles.note}>Nothing on that day cleared the bar.</p>
      )}
    </section>
  );
}

/* ---- the appendix -------------------------------------------------------------------------- */

function RunTable({ rows }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Scanned</th><th>Day</th><th>Status</th>
            <th className={styles.num}>Articles</th><th className={styles.num}>Candidates</th>
            <th className={styles.num}>Added</th><th className={styles.num}>Held</th>
            <th className={styles.num}>Errors</th><th>Prompts</th><th>Log</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const m = meta(r.status);
            const day = cov.periodDay(r.period);
            return (
              <tr key={i}>
                <td className={styles.mono}>{r.scanned_at}</td>
                <td className={styles.mono}>
                  {day || r.period}
                  {r.region && r.region !== '(any)' && <span className={styles.tag}>{r.region}</span>}
                </td>
                <td>
                  <span className={`${styles.pill} ${styles[m.cls]}`} title={m.hint}>
                    <m.Icon size={10} strokeWidth={2.2} aria-hidden="true" />{m.label}
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
                        view <ExternalLink size={9} strokeWidth={2} aria-hidden="true" />
                      </a>
                    : <span className={styles.dim}>local</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Quality() {
  const runs = [...evalHistory].reverse();
  return (
    <section>
      <h2 className={styles.h2}>Is it any good?</h2>
      <p className={styles.note}>
        Running is not the same as being right. The pipeline is backtested against the atlas&apos;s
        own curated events: hold out every event in a window, rescan it, and score what comes back.
        No labelling needed — every seeded event is already sourced and dated.
      </p>

      {runs.length === 0 ? (
        <div className={styles.empty}>
          <strong>Not measured yet.</strong> No backtest has been published, so nothing on this page
          should be read as evidence that the agents are accurate — only that they ran.
        </div>
      ) : (
        <>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Ran</th><th>Window</th><th className={styles.num}>Events</th>
                  <th className={styles.num}>Precision</th><th className={styles.num}>Recall</th>
                  <th className={styles.num}>F1</th><th className={styles.num}>Resolution</th>
                  <th className={styles.num}>Kind</th><th className={styles.num}>Severity ±1</th>
                  <th>Prompts</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((e, i) => (
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
  );
}

// Whether a stated confidence actually means what it says. The auto-approve gate is a single
// threshold on this number, so if it claims 0.85 and is right half the time, everything that gets
// published rests on a number that means nothing.
function Calibration({ rows }) {
  if (!rows.length) return null;
  return (
    <>
      <h3 className={styles.h3}>Is its confidence honest?</h3>
      <p className={styles.note}>
        Events are published automatically when the fact-checker&apos;s confidence clears a fixed
        bar. That only means something if a stated 80% really is right 80% of the time.
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

function Card({ label, value, note, warn }) {
  return (
    <div className={`${styles.card} ${warn ? styles.cardWarn : ''}`}>
      <div className={styles.cardLabel}>{label}</div>
      <div className={styles.cardValue}>{value ?? '—'}</div>
      <div className={styles.cardNote}>{note}</div>
    </div>
  );
}
