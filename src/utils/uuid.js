export const generateId = (prefix = 'id') =>
  `${prefix}_${crypto.randomUUID()}`;
