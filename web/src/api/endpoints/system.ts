import { api } from '../client';

export interface SystemHealth { status: 'UP' | 'DEGRADED' | 'DOWN'; time: string; version?: string; checks?: unknown[] }
export interface VersionInfo {
  name: string; version: string; api_version: string; python_version?: string;
  environment?: string; build_time?: string | null; git_commit?: string | null;
}

export const systemApi = {
  health: () => api.get<SystemHealth>('/system/health', { skipAuthRefresh: true }),
  version: () => api.get<VersionInfo>('/system/version', { skipAuthRefresh: true }),
};
