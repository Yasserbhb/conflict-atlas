import { getDB } from './database';

// --- Countries ---
export async function getAllCountries() {
  const db = await getDB();
  return db.getAll('countries');
}

export async function getCountry(id) {
  const db = await getDB();
  return db.get('countries', id);
}

export async function saveCountry(country) {
  const db = await getDB();
  return db.put('countries', country);
}

// --- Conflicts ---
export async function getAllConflicts() {
  const db = await getDB();
  return db.getAll('conflicts');
}

export async function getConflictsByCountry(countryId) {
  const db = await getDB();
  return db.getAllFromIndex('conflicts', 'involvedCountries', countryId);
}

export async function saveConflict(conflict) {
  const db = await getDB();
  const now = new Date().toISOString();
  const record = {
    ...conflict,
    involvedCountries: conflict.parties.map((p) => p.countryId),
    updatedAt: now,
    createdAt: conflict.createdAt || now,
  };
  await db.put('conflicts', record);
  return record;
}

export async function deleteConflict(id) {
  const db = await getDB();
  return db.delete('conflicts', id);
}

// --- Notes ---
export async function getNotesByCountry(countryId) {
  const db = await getDB();
  return db.getAllFromIndex('notes', 'countryId', countryId);
}

export async function getNotesByConflict(conflictId) {
  const db = await getDB();
  return db.getAllFromIndex('notes', 'conflictId', conflictId);
}

export async function saveNote(note) {
  const db = await getDB();
  const now = new Date().toISOString();
  const record = { ...note, updatedAt: now, createdAt: note.createdAt || now };
  await db.put('notes', record);
  return record;
}

export async function deleteNote(id) {
  const db = await getDB();
  return db.delete('notes', id);
}

// --- Settings ---
export async function getSettings() {
  const db = await getDB();
  return (await db.get('settings', 'app')) || defaultSettings();
}

export async function saveSettings(settings) {
  const db = await getDB();
  return db.put('settings', { id: 'app', ...settings });
}

function defaultSettings() {
  return {
    id: 'app',
    timelineYear: 2026,
    activeView: 'map',
    colorScheme: 'dark',
    lastImportedSeedVersion: null,
  };
}
