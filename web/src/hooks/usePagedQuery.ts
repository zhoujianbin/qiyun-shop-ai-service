import { keepPreviousData, useQuery, type UseQueryResult } from '@tanstack/react-query';
import type { ListResponse } from '@/types/api';

export interface PagedQueryArgs<T> {
  queryKey: readonly unknown[];
  queryFn: (signal?: AbortSignal) => Promise<ListResponse<T>>;
  enabled?: boolean;
  staleTime?: number;
}

/**
 * 列表查询：翻页保留上一页数据（keepPreviousData），避免翻页闪空。
 * 列表页据此派生 loading / empty / error 三态。
 */
export function usePagedQuery<T>(args: PagedQueryArgs<T>): UseQueryResult<ListResponse<T>> {
  return useQuery<ListResponse<T>>({
    queryKey: args.queryKey,
    queryFn: ({ signal }) => args.queryFn(signal),
    enabled: args.enabled ?? true,
    placeholderData: keepPreviousData,
    staleTime: args.staleTime ?? 30_000,
    retry: 1,
  });
}

export interface ListViewState<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: unknown;
  isEmpty: boolean;
  retry: () => void;
}

export function toListViewState<T>(query: UseQueryResult<ListResponse<T>>, page: number, pageSize: number): ListViewState<T> {
  return {
    items: query.data?.items ?? [],
    total: query.data?.meta?.total ?? 0,
    page: query.data?.meta?.page ?? page,
    pageSize: query.data?.meta?.page_size ?? pageSize,
    loading: query.isLoading || query.isFetching,
    error: query.error,
    isEmpty: !query.isLoading && !query.error && (query.data?.items?.length ?? 0) === 0,
    retry: () => {
      void query.refetch();
    },
  };
}
