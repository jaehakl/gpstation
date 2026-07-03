export function getString(value: unknown) {
  return typeof value === 'string' ? value : '';
}

export function getNumber(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function getNumberArray(value: unknown) {
  return Array.isArray(value)
    ? [...new Set(value.filter((item): item is number => typeof item === 'number' && Number.isFinite(item)))]
    : [];
}
