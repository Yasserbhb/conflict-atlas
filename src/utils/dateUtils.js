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
