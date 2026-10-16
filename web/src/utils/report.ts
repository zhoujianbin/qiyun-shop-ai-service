/** 报表聚合对象字段兼容读取（后端 breakdown/top 为自由 object）。 */
export function pickString(source: Record<string, unknown> | undefined, keys: string[], fallback = '-'): string {
  if (!source) return fallback;
  for (const key of keys) {
    const value = source[key];
    if (typeof value === 'string' && value.length > 0) return value;
  }
  return fallback;
}

export function pickNumber(source: Record<string, unknown> | undefined, keys: string[]): number {
  if (!source) return 0;
  for (const key of keys) {
    const value = source[key];
    if (typeof value === 'number') return value;
    if (typeof value === 'string' && value.length > 0 && !Number.isNaN(Number(value))) return Number(value);
  }
  return 0;
}
