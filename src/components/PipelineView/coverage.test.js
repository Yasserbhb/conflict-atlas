// node --test src/components/PipelineView/coverage.test.js
//
// coverage.js is pure and dependency-free, so it runs under node's built-in runner with no
// framework, no config and no jsdom. The date arithmetic is the part worth pinning: an off-by-one
// in the week bucketing or a retry that overwrites the wrong way would both render as a plausible
// calendar that is quietly wrong, which is the failure mode nobody notices.
import assert from 'node:assert/strict';
import test from 'node:test';
import * as cov from './coverage.js';

const row = (period, status, extra = {}) => ({ period, status, region: '(any)', ...extra });

test('a day period is recognised, a range is not', () => {
  assert.equal(cov.periodDay('2026-06-01..2026-06-01'), '2026-06-01');
  assert.equal(cov.periodDay('1870..1900'), null);
  assert.equal(cov.periodDay('2026-06-01..2026-06-03'), null);
  assert.equal(cov.periodDay(undefined), null);
});

test('the manual range scans stay off the calendar', () => {
  const ledger = [row('1870..1900', 'found'), row('2026-06-01..2026-06-01', 'found')];
  assert.deepEqual([...cov.byDay(ledger).keys()], ['2026-06-01']);
  assert.equal(cov.ranges(ledger).length, 1);
});

test('a retried day shows how it ENDED, not how it started', () => {
  const ledger = [
    row('2026-06-01..2026-06-01', 'failed'),
    row('2026-06-01..2026-06-01', 'found', { applied: 2 }),
  ];
  const d = cov.byDay(ledger).get('2026-06-01');
  assert.equal(d.status, 'found');
  assert.equal(d.applied, 2);
  assert.equal(d.attempts, 2, 'the retry itself is worth surfacing');
});

test('the window never reaches past the settle horizon', () => {
  const days = cov.byDay([row('2026-06-01..2026-06-01', 'found')]);
  const w = cov.window(days, cov.parse('2026-09-17'), 7);
  assert.equal(cov.iso(w.from), '2026-06-01');
  assert.equal(cov.iso(w.horizon), '2026-09-10');
});

test('weeks start on Monday and cover every day in the window', () => {
  // 2026-06-01 is a Monday; 2026-06-14 a Sunday. Two whole columns, no partial week.
  const cols = cov.weeks(cov.parse('2026-06-01'), cov.parse('2026-06-14'));
  assert.equal(cols.length, 2);
  assert.equal(cov.iso(cols[0][0]), '2026-06-01');
  assert.equal(cov.iso(cols[1][6]), '2026-06-14');
  // A window starting mid-week must still begin its column on the Monday before it.
  const mid = cov.weeks(cov.parse('2026-06-03'), cov.parse('2026-06-10'));
  assert.equal(cov.iso(mid[0][0]), '2026-06-01');
});

test('progress counts the backlog and drains it one slot slower than the batch', () => {
  // Jun 1..Jun 10 eligible = 10 days; two of them checked.
  const days = cov.byDay([
    row('2026-06-01..2026-06-01', 'found'),
    row('2026-06-02..2026-06-02', 'quiet'),
  ]);
  const p = cov.progress(days, cov.parse('2026-06-01'), cov.parse('2026-06-10'), 3);
  assert.equal(p.total, 10);
  assert.equal(p.checked, 2);
  assert.equal(p.remaining, 8);
  // 3 days per run, but one is reserved for the newest day, so the backlog drains at 2.
  assert.equal(p.etaRuns, 4);
});

test('a blind or failed day still counts as checked on the calendar', () => {
  // It is a day we have an answer about ("we looked and saw nothing"), which is the whole point
  // of recording it. Whether the CURSOR retries it is a separate question, decided in cursor.py.
  const days = cov.byDay([row('2026-06-01..2026-06-01', 'blind')]);
  const p = cov.progress(days, cov.parse('2026-06-01'), cov.parse('2026-06-01'), 3);
  assert.equal(p.checked, 1);
});

test('a metric series reads stats, and falls back for rows written before stats existed', () => {
  const days = cov.byDay([
    // an old row: no stats dict, only the four flat fields
    row('2026-06-01..2026-06-01', 'found', { items: 40, events_found: 3, applied: 1 }),
    // a new row: the whole dict
    row('2026-06-02..2026-06-02', 'found', {
      items: 68, applied: 2, stats: { items: 68, queries: 6, triaged_out: 59 },
    }),
  ]);
  assert.deepEqual(cov.series(days, 'items').map((p) => p.value), [40, 68]);
  assert.deepEqual(cov.series(days, 'applied').map((p) => p.value), [1, 2]);
  // queries only exists on the newer row; the older one must read 0, not undefined or NaN
  assert.deepEqual(cov.series(days, 'queries').map((p) => p.value), [0, 6]);
  assert.equal(cov.total(cov.series(days, 'triaged_out')), 59);
});

test('a series is ordered oldest first regardless of ledger order', () => {
  const days = cov.byDay([
    row('2026-06-03..2026-06-03', 'found', { items: 3 }),
    row('2026-06-01..2026-06-01', 'found', { items: 1 }),
  ]);
  assert.deepEqual(cov.series(days, 'items').map((p) => p.day), ['2026-06-01', '2026-06-03']);
});
