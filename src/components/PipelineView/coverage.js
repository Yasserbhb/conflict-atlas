// Turning the coverage ledger into something you can read at a glance.
//
// The ledger is an append-only list of scan attempts. Under the daily cursor almost every row is
// one day, so after a year it is 365 rows — a table nobody scans and a page nobody reads. These
// helpers reshape it into days, so the page can render a calendar instead.

const DAY = 86400000;

/** A ledger period is "start..end". A DAY row is the degenerate case where they are equal. */
export function periodDay(period) {
  if (typeof period !== 'string') return null;
  const [a, b] = period.split('..');
  return a && a === b && /^\d{4}-\d{2}-\d{2}$/.test(a) ? a : null;
}

export const iso = (d) => d.toISOString().slice(0, 10);
export const parse = (s) => new Date(`${s}T00:00:00Z`);
export const shift = (d, n) => new Date(d.getTime() + n * DAY);

/** Collapse the ledger to one entry per day, newest attempt winning.
 *
 * Retries are the reason this has to merge rather than index: a day that failed and was picked
 * up again has two rows, and the calendar must show how it ended, not how it started. Range rows
 * (the manual `scan "1870..1900"` ones) have no single day and are dropped here — they are listed
 * separately rather than being smeared across thirty years of cells.
 */
export function byDay(ledger) {
  const out = new Map();
  for (const row of ledger) {
    const day = periodDay(row.period);
    if (!day) continue;
    const prev = out.get(day);
    out.set(day, prev ? { ...row, attempts: (prev.attempts || 1) + 1 } : { ...row, attempts: 1 });
  }
  return out;
}

export const ranges = (ledger) => ledger.filter((r) => !periodDay(r.period));

/** The window the calendar covers: the earliest day we tried, through the newest day we are
 *  allowed to try. Derived from the data rather than configured, so the page cannot disagree
 *  with the pipeline about where the cursor starts. */
export function window(days, today, settleDays = 7) {
  const horizon = shift(today, -settleDays);
  const keys = [...days.keys()].sort();
  const first = keys.length ? parse(keys[0]) : shift(horizon, -27);
  const last = keys.length ? parse(keys[keys.length - 1]) : horizon;
  return { from: first, to: horizon > last ? horizon : last, horizon };
}

/** Weeks as columns, Monday at the top — the shape a contribution graph uses, because it packs a
 *  year into one screen and makes a missed day a visible hole rather than a missing table row. */
export function weeks(from, to) {
  const start = shift(from, -((from.getUTCDay() + 6) % 7));       // back to Monday
  const cols = [];
  for (let d = start; d <= to; d = shift(d, 7)) {
    cols.push(Array.from({ length: 7 }, (_, i) => shift(d, i)));
  }
  return cols;
}

/** How the backlog is going: what the cursor has left, and how fast it is closing.
 *
 * `daysPerRun - 1` is the drain rate, not `daysPerRun`: one slot every run is reserved for the
 * newest settled day so the atlas stays current, which is deliberate but means the backlog closes
 * one day per run slower than the batch size suggests.
 */
export function progress(days, from, horizon, daysPerRun = 3) {
  let checked = 0, total = 0;
  for (let d = from; d <= horizon; d = shift(d, 1)) {
    total += 1;
    if (days.has(iso(d))) checked += 1;
  }
  const remaining = total - checked;
  const drain = Math.max(1, daysPerRun - 1);
  return { checked, total, remaining, etaRuns: Math.ceil(remaining / drain) };
}

/** Per-day values for one metric, oldest first.
 *
 * Reads `row.stats` first and falls back to the flat ledger fields, because rows written before
 * the pipeline stored the whole stats dict only have the four hand-picked ones. Without the
 * fallback the site would show a blank chart for its own history.
 */
export function series(days, key) {
  const flat = { items: 'items', candidates: 'events_found', proposals: 'proposals',
                 dropped: 'dropped', applied: 'applied', held: 'held' };
  return [...days.keys()].sort().map((day) => {
    const r = days.get(day);
    const v = r.stats?.[key] ?? (flat[key] ? r[flat[key]] : undefined);
    return { day, value: typeof v === 'number' ? v : 0, status: r.status };
  });
}

export const total = (pts) => pts.reduce((n, p) => n + p.value, 0);
