import { api } from '../client';
import type {
  CurrentUser, Customer, CustomerLoginRequest, CustomerRegisterRequest, PasswordChangeRequest,
  StaffLoginRequest, TokenPair,
} from '@/types/domain';

export const authApi = {
  staffLogin: (body: StaffLoginRequest) => api.post<TokenPair>('/auth/staff/login', body),
  customerLogin: (body: CustomerLoginRequest) => api.post<TokenPair>('/auth/customer/login', body),
  register: (body: CustomerRegisterRequest) => api.post<Customer>('/auth/customer/register', body),
  guestSession: (body: { channel_account_id?: number | null; device_id?: string | null }) =>
    api.post<TokenPair>('/auth/guest-session', body),
  refresh: (refreshToken: string) => api.post<TokenPair>('/auth/refresh', { refresh_token: refreshToken }),
  logout: () => api.post<void>('/auth/logout', {}),
  me: () => api.get<CurrentUser>('/auth/me'),
  changePassword: (body: PasswordChangeRequest) => api.post<void>('/auth/password/change', body),
};
