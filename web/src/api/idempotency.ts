import { newUuid } from './uuid';

/**
 * 幂等键：按“用户点击一次提交”的粒度生成一个 UUID，并在重试时复用。
 * 统一走 newUuid()，避免在非安全上下文（http + 局域网 IP）下调用
 * crypto.randomUUID 抛错。
 */
export function newIdempotencyKey(): string {
  return newUuid();
}

/** 在一次提交动作内复用的幂等键持有器 */
export function createIdempotencyHolder(): { get: () => string; reset: () => void } {
  let key = newIdempotencyKey();
  return {
    get: () => key,
    reset: () => {
      key = newIdempotencyKey();
    },
  };
}
