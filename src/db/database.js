import { openDB } from 'idb';

let dbPromise = null;

export function getDB() {
  if (!dbPromise) {
    dbPromise = openDB('geopolitical-tracker', 1, {
      upgrade(db) {
        const countries = db.createObjectStore('countries', { keyPath: 'id' });
        countries.createIndex('name', 'name');
        countries.createIndex('region', 'region');

        const conflicts = db.createObjectStore('conflicts', { keyPath: 'id' });
        conflicts.createIndex('type', 'type');
        conflicts.createIndex('ongoing', 'ongoing');
        conflicts.createIndex('involvedCountries', 'involvedCountries', { multiEntry: true });
        conflicts.createIndex('startDate', 'startDate');

        const notes = db.createObjectStore('notes', { keyPath: 'id' });
        notes.createIndex('countryId', 'countryId');
        notes.createIndex('conflictId', 'conflictId');
        notes.createIndex('date', 'date');

        db.createObjectStore('settings', { keyPath: 'id' });
      },
    });
  }
  return dbPromise;
}
