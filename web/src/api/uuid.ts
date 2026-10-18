/**
 * 生成 UUID v4（同步）。
 *
 * 为什么不能直接写 crypto.randomUUID()：
 * crypto.randomUUID 属于「安全上下文（secure context）」限定的 API —— 只有在
 * HTTPS 或被视为可信来源的 localhost / 127.0.0.1 下才存在。用 http://<局域网 IP>
 * 打开页面时，window.crypto 有、crypto.getRandomValues 有，但 randomUUID 是
 * undefined，直接调用就会抛 "crypto.randomUUID is not a function"。
 *
 * 所以这里按能力逐级降级：
 *   1) crypto.randomUUID —— 首选，安全上下文下可用；
 *   2) crypto.getRandomValues + 手工拼 v4 —— 非安全上下文同样可用，随机性足够；
 *   3) Math.random —— 最后的兜底，仅用于极老环境，避免整条链路不可用。
 *
 * 返回值始终是标准 UUID v4 字符串（36 字符），因此可以安全地放进入库字段
 * （如 assistant_message.client_msg_id 为 String(64)）。
 */
export function newUuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  const bytes = new Uint8Array(16);
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }

  // RFC 4122：第 7 字节高 4 位为版本号 4，第 9 字节高 2 位为变体 10xx。
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
