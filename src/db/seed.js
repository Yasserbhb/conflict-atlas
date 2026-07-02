import { getDB } from './database';
import { getSettings, saveSettings, saveConflict } from './queries';
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

  await saveSettings({ ...settings, lastImportedSeedVersion: seedData.version });
}
