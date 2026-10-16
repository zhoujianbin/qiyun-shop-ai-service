/**
 * 一期埋点封装：仅记录非敏感字段；生产环境默认静默（可在此接入采集端点）。
 * 严禁记录密码、验证码、完整手机号、完整地址、身份证、银行卡、token。
 */
const SENSITIVE_KEYS = ['password', 'sms_code', 'token', 'access_token', 'refresh_token', 'mobile', 'phone', 'address', 'id_card', 'bank'];

export type TrackPayload = Record<string, string | number | boolean | null | undefined>;

export function sanitizeTrackPayload(payload: TrackPayload): TrackPayload {
  const out: TrackPayload = {};
  Object.entries(payload).forEach(([key, value]) => {
    if (SENSITIVE_KEYS.some((s) => key.toLowerCase().includes(s))) return;
    out[key] = value;
  });
  return out;
}

export function track(event: string, payload: TrackPayload = {}): void {
  const body = sanitizeTrackPayload(payload);
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.debug('[track]', event, body);
  }
}

export function useTrack() {
  return track;
}
