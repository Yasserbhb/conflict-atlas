// Convert an ISO 3166-1 alpha-2 code to its emoji flag.
export function flagEmoji(iso2) {
  if (!iso2 || iso2.length !== 2) return '';
  return iso2
    .toUpperCase()
    .replace(/./g, (c) => String.fromCodePoint(127397 + c.charCodeAt(0)));
}

// Small glyph per conflict type
export const TYPE_GLYPH = {
  war: '⚔',
  civil_war: '🔥',
  genocide: '☠',
  occupation: '⛓',
  proxy_war: '🎯',
  sanctions: '🚫',
  disputed_territory: '🗺',
};
