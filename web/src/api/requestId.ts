import { newUuid } from './uuid';

/** 每个请求生成 X-Request-Id，便于与后端 audit_log.request_id 对齐。 */
export function newRequestId(): string {
  return newUuid();
}
