export function parseYear(dateStr) {
  if (!dateStr) return null;
  return parseInt(String(dateStr).substring(0, 4), 10);
}

export function isActiveAt(conflict, year) {
  const start = parseYear(conflict.startDate);
  const end = parseYear(conflict.endDate);
  if (start === null) return false;
  if (start > year) return false;
  if (conflict.ongoing || end === null) return true;
  return end >= year;
}

// Parse "YYYY" | "YYYY-MM" | "YYYY-MM-DD" into a decimal year, for sorting and
// positioning events along a conflict's span. Returns null if unparseable.
export function dateToValue(dateStr) {
  if (!dateStr) return null;
  const [y, m, d] = String(dateStr).split('-').map((n) => parseInt(n, 10));
  if (!y) return null;
  let v = y;
  if (m) v += (m - 1) / 12;
  if (d) v += (d - 1) / 372; // keep within the month's slice
  return v;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// Human-friendly event date at whatever precision was given.
export function formatEventDate(dateStr) {
  if (!dateStr) return '';
  const parts = String(dateStr).split('-');
  const [y, m, d] = parts.map((n) => parseInt(n, 10));
  if (parts.length >= 3) return `${d} ${MONTHS[m - 1]} ${y}`;
  if (parts.length === 2) return `${MONTHS[m - 1]} ${y}`;
  return String(y);
}

export function formatDateRange(startDate, endDate, ongoing) {
  const start = startDate ? String(startDate).substring(0, 4) : '?';
  if (ongoing || !endDate) return `${start} – present`;
  const end = String(endDate).substring(0, 4);
  return start === end ? start : `${start} – ${end}`;
}

// Narrow a conflict list by the map filters (type / min severity / ongoing).
export function applyConflictFilters(conflicts, f) {
  if (!f) return conflicts;
  return conflicts.filter((c) => {
    if (f.type && f.type !== 'all' && c.type !== f.type) return false;
    if (f.ongoingOnly && !c.ongoing) return false;
    if ((c.severity || 0) < (f.minSeverity || 1)) return false;
    return true;
  });
}

export function isFilterActive(f) {
  return !!f && (f.type !== 'all' || f.ongoingOnly || (f.minSeverity || 1) > 1);
}
