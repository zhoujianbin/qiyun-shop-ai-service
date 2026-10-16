import { api } from '../client';
import type { ChannelAccount, ChannelAccountCreateRequest, ChannelAccountUpdateRequest } from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const channelsApi = {
  list: (params: Record<string, unknown> = {}) => api.get<ListResponse<ChannelAccount>>('/channel-accounts', { params }),
  create: (body: ChannelAccountCreateRequest) => api.post<ChannelAccount>('/channel-accounts', body),
  update: (id: number, body: ChannelAccountUpdateRequest) => api.patch<ChannelAccount>(`/channel-accounts/${id}`, body),
};
