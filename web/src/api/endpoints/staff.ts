import { api } from '../client';
import type {
  Permission, Role, StaffChannelScopes, StaffUser, StaffUserCreateRequest, StaffUserRoles,
  StaffUserUpdateRequest,
} from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const staffApi = {
  list: (params: Record<string, unknown>) => api.get<ListResponse<StaffUser>>('/staff/users', { params }),
  create: (body: StaffUserCreateRequest) => api.post<StaffUser>('/staff/users', body),
  detail: (id: number) => api.get<StaffUser>(`/staff/users/${id}`),
  update: (id: number, body: StaffUserUpdateRequest) => api.patch<StaffUser>(`/staff/users/${id}`, body),
  disable: (id: number) => api.post<void>(`/staff/users/${id}/disable`, {}),
  getRoles: (id: number) => api.get<StaffUserRoles>(`/staff/users/${id}/roles`),
  setRoles: (id: number, roleCodes: string[]) => api.put<StaffUserRoles>(`/staff/users/${id}/roles`, { role_codes: roleCodes }),
  getChannelScopes: (id: number) => api.get<StaffChannelScopes>(`/staff/users/${id}/channel-scopes`),
  setChannelScopes: (id: number, channelAccountIds: number[]) =>
    api.put<StaffChannelScopes>(`/staff/users/${id}/channel-scopes`, { channel_account_ids: channelAccountIds }),
  roles: (params: Record<string, unknown> = {}) => api.get<ListResponse<Role>>('/roles', { params }),
  permissions: () => api.get<ListResponse<Permission>>('/permissions'),
};
