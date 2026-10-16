/**
 * 幂等键：按“用户点击一次提交”的粒度生成一个 UUID，并在重试时复用。
 * uuid 生成为同步操作；无 crypto.randomUUID 时降级到时间戳 + 随机数。
 */
export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `idem-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
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
