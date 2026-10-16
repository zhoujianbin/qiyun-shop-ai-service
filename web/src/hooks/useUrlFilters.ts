import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { parseQuery } from '@/utils/queryString';

export type FilterValue = string | number | undefined | null;

export interface UrlFiltersApi<F extends Record<string, FilterValue>> {
  filters: F;
  page: number;
  pageSize: number;
  setFilter: (key: keyof F, value: FilterValue) => void;
  patchFilters: (patch: Partial<F>) => void;
  setPage: (page: number) => void;
  setPageSize: (pageSize: number) => void;
  reset: () => void;
  sort: string | undefined;
  setSort: (sort: string | undefined) => void;
}

/** 筛选条件写入 URL query，保证深链、刷新、前进后退可复现。 */
export function useUrlFilters<F extends Record<string, FilterValue>>(defaults: F): UrlFiltersApi<F> {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo(() => {
    const parsed = parseQuery(searchParams.toString());
    const next = { ...defaults } as Record<string, FilterValue>;
    (Object.keys(defaults) as Array<keyof F>).forEach((key) => {
      const raw = parsed[String(key)];
      if (raw !== undefined && raw !== '') next[String(key)] = raw;
    });
    return next as F;
  }, [searchParams, defaults]);

  const page = Number(parsedFrom(searchParams.toString(), 'page') ?? 1);
  const pageSize = Number(parsedFrom(searchParams.toString(), 'page_size') ?? 20);
  const sort = parsedFrom(searchParams.toString(), 'sort');

  const patch = useCallback(
    (values: Record<string, FilterValue>, resetPage = true) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          Object.entries(values).forEach(([key, value]) => {
            if (value === null || value === undefined || value === '') next.delete(key);
            else next.set(key, String(value));
          });
          if (resetPage) next.set('page', '1');
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );

  return {
    filters,
    page: Number.isFinite(page) && page > 0 ? page : 1,
    pageSize: Number.isFinite(pageSize) && pageSize > 0 ? pageSize : 20,
    setFilter: (key, value) => patch({ [String(key)]: value }),
    patchFilters: (values) => patch(values as Record<string, FilterValue>),
    setPage: (value) => patch({ page: value }, false),
    setPageSize: (value) => patch({ page_size: value, page: 1 }, false),
    reset: () => setSearchParams(new URLSearchParams(), { replace: false }),
    sort,
    setSort: (value) => patch({ sort: value }),
  };
}

function parsedFrom(search: string, key: string): string | undefined {
  const value = new URLSearchParams(search).get(key);
  return value === null ? undefined : value;
}
