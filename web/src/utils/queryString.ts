/** URL query 序列化：剔除空值，键顺序稳定，保证深链与前进后退可复现。 */
export type QueryValue = string | number | boolean | null | undefined;

export function buildQuery(params: Record<string, QueryValue>): string {
  const sp = new URLSearchParams();
  Object.keys(params)
    .sort()
    .forEach((key) => {
      const value = params[key];
      if (value === null || value === undefined || value === '' || value === false) return;
      sp.set(key, String(value));
    });
  const qs = sp.toString();
  return qs ? `?${qs}` : '';
}

export function parseQuery(search: string): Record<string, string> {
  const sp = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  const out: Record<string, string> = {};
  sp.forEach((value, key) => {
    out[key] = value;
  });
  return out;
}

/** 生成用于埋点的 filters_hash（不包含敏感字段明文） */
export function hashFilters(params: Record<string, QueryValue>): string {
  const text = JSON.stringify(
    Object.keys(params)
      .sort()
      .filter((k) => params[k] !== undefined && params[k] !== null && params[k] !== '')
      .map((k) => [k, params[k]]),
  );
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) | 0;
  }
  return Math.abs(hash).toString(36);
}
