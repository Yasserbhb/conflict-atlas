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

  // Import conflicts (only seed_ prefixed — never overwrite user-created ones)
  for (const conflict of seedData.conflicts) {
    const existing = await db.get('conflicts', conflict.id);
    if (!existing) {
      await saveConflict(conflict);
    }
  }

  await saveSettings({ ...settings, lastImportedSeedVersion: seedData.version });
}
