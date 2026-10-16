import type { AxiosError } from 'axios';
import type { ApiErrorBody } from '@/types/api';

export type ErrorKind =
  | 'network' | 'timeout' | 'canceled' | 'unauthorized' | 'forbidden' | 'notFound'
  | 'conflict' | 'validation' | 'rateLimit' | 'server' | 'unknown';

export interface ApiErrorInit {
  code: string;
  message: string;
  details?: unknown;
  requestId?: string;
  httpStatus?: number;
  kind?: ErrorKind;
}

export class ApiError extends Error {
  readonly code: string;
  readonly details?: unknown;
  readonly requestId?: string;
  readonly httpStatus?: number;
  readonly kind: ErrorKind;

  constructor(init: ApiErrorInit) {
    super(init.message);
    this.name = 'ApiError';
    this.code = init.code;
    this.details = init.details;
    this.requestId = init.requestId;
    this.httpStatus = init.httpStatus;
    this.kind = init.kind ?? 'unknown';
  }

  get isCanceled(): boolean {
    return this.kind === 'canceled';
  }

  get isUnauthorized(): boolean {
    return this.kind === 'unauthorized';
  }

  get isForbidden(): boolean {
    return this.kind === 'forbidden';
  }

  get isConflict(): boolean {
    return this.kind === 'conflict';
  }

  get isNotFound(): boolean {
    return this.kind === 'notFound';
  }

  get isValidation(): boolean {
    return this.kind === 'validation';
  }

  /** 字段级错误：键为字段名，值为中文提示 */
  get fieldErrors(): Record<string, string> {
    return extractFieldErrors(this.details);
  }
}

function kindFromStatus(status?: number): ErrorKind {
  if (!status) return 'network';
  if (status === 400 || status === 422) return 'validation';
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'notFound';
  if (status === 409) return 'conflict';
  if (status === 429) return 'rateLimit';
  if (status >= 500) return 'server';
  return 'unknown';
}

export function extractFieldErrors(details: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (!details) return out;
  const visit = (entry: unknown): void => {
    if (!entry || typeof entry !== 'object') return;
    const record = entry as Record<string, unknown>;
    const loc = record.loc;
    const msg = record.msg ?? record.message;
    if (Array.isArray(loc) && typeof msg === 'string') {
      const field = loc.filter((part) => part !== 'body' && part !== 'query' && part !== 'path').join('.');
      if (field) out[field] = msg;
      return;
    }
    if (typeof record.field === 'string' && typeof msg === 'string') {
      out[record.field] = msg;
      return;
    }
  };
  if (Array.isArray(details)) {
    details.forEach(visit);
    return out;
  }
  if (typeof details === 'object') {
    const record = details as Record<string, unknown>;
    if (Array.isArray(record.errors)) record.errors.forEach(visit);
    if (record.fields && typeof record.fields === 'object') {
      Object.entries(record.fields as Record<string, unknown>).forEach(([k, v]) => {
        if (typeof v === 'string') out[k] = v;
      });
    }
  }
  return out;
}

function pickRequestId(body: unknown, headerValue?: string): string | undefined {
  if (body && typeof body === 'object' && typeof (body as ApiErrorBody).request_id === 'string') {
    return (body as ApiErrorBody).request_id;
  }
  return headerValue;
}

export function normalizeAxiosError(error: AxiosError): ApiError {
  if (error.code === 'ERR_CANCELED') {
    return new ApiError({ code: 'CANCELED', message: '请求已取消', kind: 'canceled' });
  }
  const status = error.response?.status;
  const body = error.response?.data;
  const headerRequestId = error.response?.headers?.['x-request-id'];
  const requestId = pickRequestId(body, typeof headerRequestId === 'string' ? headerRequestId : undefined);
  let code = status ? `HTTP_${status}` : error.code ?? 'NETWORK_ERROR';
  let message = error.message || '网络异常，请稍后重试';
  let details: unknown;

  if (body && typeof body === 'object') {
    const record = body as ApiErrorBody & { detail?: unknown };
    if (typeof record.code === 'string') code = record.code;
    if (typeof record.message === 'string') message = record.message;
    details = record.details;
    if (details === undefined && record.detail !== undefined) {
      details = record.detail;
      if (typeof record.detail === 'string' && !record.message) message = record.detail;
    }
  }

  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
    return new ApiError({ code, message: '请求超时，请稍后重试', details, requestId, httpStatus: status, kind: 'timeout' });
  }
  if (!error.response) {
    return new ApiError({ code, message: '网络连接失败，请检查网络后重试', details, requestId, httpStatus: status, kind: 'network' });
  }
  if (!message || message === 'Request failed with status code ' + status) {
    message = defaultMessage(kindFromStatus(status));
  }
  return new ApiError({ code, message, details, requestId, httpStatus: status, kind: kindFromStatus(status) });
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof Error) {
    return new ApiError({ code: 'UNKNOWN', message: error.message || '未知错误', kind: 'unknown' });
  }
  return new ApiError({ code: 'UNKNOWN', message: '未知错误', kind: 'unknown' });
}

export function defaultMessage(kind: ErrorKind): string {
  switch (kind) {
    case 'validation': return '请求参数不正确，请检查后重试';
    case 'unauthorized': return '登录已过期，请重新登录';
    case 'forbidden': return '无权限执行该操作';
    case 'notFound': return '资源不存在或已删除';
    case 'conflict': return '数据已变化，已为你刷新，请重试';
    case 'rateLimit': return '操作过于频繁，请稍后再试';
    case 'server': return '服务异常，请稍后重试';
    case 'timeout': return '请求超时，请稍后重试';
    case 'network': return '网络连接失败，请检查网络后重试';
    case 'canceled': return '请求已取消';
    default: return '操作失败，请稍后重试';
  }
}

export function errorMessage(error: unknown): string {
  return toApiError(error).message;
}

export function errorRequestId(error: unknown): string | undefined {
  return toApiError(error).requestId;
}
