import { getDB } from './database';
import { getSettings, saveSettings, saveConflict, deleteConflict } from './queries';
import seedData from '../data/seed.json';

export async function initSeed() {
  const settings = await getSettings();
  if (settings.lastImportedSeedVersion === seedData.version) return;

  const db = await getDB();

  // Import countries (always replace seed countries, never overwrite user notes)
  const existingCountries = await db.getAll('countries');
  const existingMap = Object.fromEntries(existingCountries.map((c) => [c.id, c]));

  const tx = db.transaction('countries', 'readwrite');
  for (const country of seedData.countries) {
    const existing = existingMap[country.id];
    // Preserve user notes if they exist
    tx.store.put({ ...country, notes: existing?.notes || country.notes });
  }
  await tx.done;

  // Import conflicts. On a version bump, seed_ conflicts are refreshed to the
  // latest data (so corrections/edits in seed.json actually reach you), while
  // user-created (user_) conflicts are never touched.
  for (const conflict of seedData.conflicts) {
    if (conflict.id.startsWith('seed_')) {
      await saveConflict(conflict);
    } else {
      const existing = await db.get('conflicts', conflict.id);
      if (!existing) await saveConflict(conflict);
    }
  }

  // Drop seed conflicts that seed.json no longer has.
  //
  // This import was add-only, and the app reads getAllConflicts() from IndexedDB rather than from
  // seed.json — so anything ever imported stayed forever. A conflict removed upstream (renamed,
  // merged into another, or gone because the dataset was rebuilt) kept rendering on every machine
  // that had seen it, and its events were counted twice: once in the stale record and once inside
  // whichever conflict absorbed them. Only `seed_` ids are touched; `user_` conflicts are theirs.
  const keep = new Set(seedData.conflicts.map((c) => c.id));
  const stale = (await db.getAllKeys('conflicts'))
    .filter((id) => typeof id === 'string' && id.startsWith('seed_') && !keep.has(id));
  for (const id of stale) await deleteConflict(id);
  if (stale.length) console.info(`[seed] removed ${stale.length} conflict(s) no longer in seed.json`);

  await saveSettings({ ...settings, lastImportedSeedVersion: seedData.version });
}
