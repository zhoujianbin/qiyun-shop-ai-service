import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { channelsApi } from '@/api/endpoints/channels';
import { queryKeys } from '@/api/queryKeys';
import { useChannelScopeStore } from '@/stores/channelScopeStore';
import { usePermission } from './usePermission';
import { P } from '@/types/permissions';

/** 渠道范围：管理员可切换，其余角色按授权范围只读；后台列表统一注入 channel_account_id。 */
export function useChannelScope() {
  const available = useChannelScopeStore((state) => state.available);
  const activeIds = useChannelScopeStore((state) => state.activeIds);
  const setActive = useChannelScopeStore((state) => state.setActive);
  const setAvailable = useChannelScopeStore((state) => state.setAvailable);
  const canRead = usePermission(P.channelRead);

  const query = useQuery({
    queryKey: queryKeys.channels.list({ page: 1, page_size: 100 }),
    queryFn: ({ signal }) => channelsApi.list({ page: 1, page_size: 100, signal }),
    enabled: canRead,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (query.data?.items) setAvailable(query.data.items);
  }, [query.data, setAvailable]);

  const activeChannelId = activeIds.length === 1 ? activeIds[0] : null;

  return {
    available,
    activeIds,
    activeChannelId,
    setActive,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}
