import { useMemo } from 'react';
import { isActiveAt } from '../utils/dateUtils';

export function useConflictFilter(conflicts, year) {
  return useMemo(
    () => conflicts.filter((c) => isActiveAt(c, year)),
    [conflicts, year]
  );
}

export function useCountryConflicts(conflicts, countryId, year) {
  return useMemo(() => {
    if (!countryId) return [];
    return conflicts.filter(
      (c) =>
        c.involvedCountries?.includes(countryId) &&
        (year == null || isActiveAt(c, year))
    );
  }, [conflicts, countryId, year]);
}

export function useCountrySeverity(conflicts, year) {
  return useMemo(() => {
    const map = {};
    for (const c of conflicts) {
      if (!isActiveAt(c, year)) continue;
      for (const id of c.involvedCountries || []) {
        if (!map[id] || c.severity > map[id]) {
          map[id] = c.severity;
        }
      }
    }
    return map;
  }, [conflicts, year]);
}
