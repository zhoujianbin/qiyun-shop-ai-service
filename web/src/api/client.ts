import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios';
import { normalizeAxiosError, ApiError } from './errors';
import { tokenStore } from './tokenStore';
import { newRequestId } from './requestId';
import { newIdempotencyKey } from './idempotency';
import type { TokenPair } from '@/types/domain';

export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1';

declare module 'axios' {
  export interface AxiosRequestConfig {
    /** 跳过 401 单飞刷新（登录/刷新/公开接口使用） */
    skipAuthRefresh?: boolean;
  }
}

const WRITE_METHODS = ['post', 'put', 'patch', 'delete'];
const READ_METHODS = ['get', 'head', 'options'];

interface AppRequestConfig extends InternalAxiosRequestConfig {
  _retryCount?: number;
  _authRetried?: boolean;
  skipAuthRefresh?: boolean;
}

export const http = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

function isWrite(method?: string): boolean {
  return WRITE_METHODS.includes((method ?? 'get').toLowerCase());
}

http.interceptors.request.use((config) => {
  const cfg = config as AppRequestConfig;
  if (!cfg.headers.get('X-Request-Id')) cfg.headers.set('X-Request-Id', newRequestId());
  const accessToken = tokenStore.getAccess();
  if (accessToken) cfg.headers.set('Authorization', `Bearer ${accessToken}`);
  // 写请求自动附加幂等键；重试复用同一 config，因此复用同一 key。
  if (isWrite(cfg.method) && !cfg.headers.get('Idempotency-Key')) {
    cfg.headers.set('Idempotency-Key', newIdempotencyKey());
  }
  return cfg;
});

let refreshPromise: Promise<boolean> | null = null;

/** 单飞刷新：并发 401 共用同一个刷新 Promise，避免雪崩。 */
function refreshAccessToken(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  const refreshToken = tokenStore.getRefresh();
  if (!refreshToken) return Promise.resolve(false);
  refreshPromise = axios
    .post<TokenPair>(`${API_BASE}/auth/refresh`, { refresh_token: refreshToken }, { timeout: 15000, withCredentials: true })
    .then((res) => {
      const data = res.data;
      if (data && data.access_token) {
        tokenStore.set({
          accessToken: data.access_token,
          refreshToken: data.refresh_token ?? refreshToken,
          expiresAt: Date.now() + (data.expires_in ?? 0) * 1000,
        });
        return true;
      }
      return false;
    })
    .catch(() => false)
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

http.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError) => {
    const cfg = error.config as AppRequestConfig | undefined;
    if (!cfg) throw normalizeAxiosError(error);
    const status = error.response?.status;
    const method = (cfg.method ?? 'get').toLowerCase();

    // 401：单飞刷新后重放原请求一次
    if (status === 401 && !cfg._authRetried && !cfg.skipAuthRefresh && tokenStore.getRefresh()) {
      cfg._authRetried = true;
      const refreshed = await refreshAccessToken();
      if (refreshed) return http.request(cfg);
      tokenStore.notifyCleared();
      throw new ApiError({ code: 'UNAUTHORIZED', message: '登录已过期，请重新登录', requestId: cfg.headers.get('X-Request-Id')?.toString(), httpStatus: 401, kind: 'unauthorized' });
    }

    // 重试策略：仅幂等读与网络层失败的写
    const isRead = READ_METHODS.includes(method);
    const isNetworkFailure = !error.response;
    const isRetryableStatus = status === 429 || (status !== undefined && status >= 500);
    const maxRetry = isRead ? 2 : 1;
    cfg._retryCount = (cfg._retryCount ?? 0) + 1;
    const retryable = (isRead && (isNetworkFailure || isRetryableStatus)) || (isWrite(method) && isNetworkFailure);
    if (retryable && status !== 401 && cfg._retryCount <= maxRetry) {
      await delay(isRead ? 300 * cfg._retryCount : 500);
      return http.request(cfg);
    }

    throw normalizeAxiosError(error);
  },
);

/** 统一请求入口：返回响应体（响应拦截器已解包 data）。 */
export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const result = await http.request(config);
  return result as unknown as T;
}

/**
 * 统一请求入口：返回响应体（响应拦截器已解包 data）。
 * 说明：列表 endpoint 习惯把 AbortSignal 与查询参数放在同一对象里传入，
 * 这里统一把 params.signal 提升为 axios 的取消信号，避免被序列化成查询串。
 */
export const api = {
  get: <T>(url: string, config?: AxiosRequestConfig) => {
    const { params, signal, ...rest } = config ?? {};
    let cleanParams = params;
    let realSignal = signal;
    if (params && typeof params === 'object' && 'signal' in params) {
      const { signal: innerSignal, ...restParams } = params as Record<string, unknown>;
      cleanParams = restParams as AxiosRequestConfig['params'];
      realSignal = realSignal ?? (innerSignal as AbortSignal | undefined);
    }
    return request<T>({ ...rest, url, method: 'get', params: cleanParams, signal: realSignal });
  },
  post: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    request<T>({ ...config, url, method: 'post', data }),
  put: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    request<T>({ ...config, url, method: 'put', data }),
  patch: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    request<T>({ ...config, url, method: 'patch', data }),
  delete: <T>(url: string, config?: AxiosRequestConfig) => request<T>({ ...config, url, method: 'delete' }),
};

/** 文件上传：multipart/form-data，超时放宽到 120s */
export async function upload<T>(url: string, formData: FormData, config?: AxiosRequestConfig): Promise<T> {
  return request<T>({
    ...config,
    url,
    method: 'post',
    data: formData,
    timeout: 120000,
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}

export { ApiError };
