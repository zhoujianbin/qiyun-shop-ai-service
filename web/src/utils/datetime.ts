import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import 'dayjs/locale/zh-cn';

dayjs.extend(utc);
dayjs.locale('zh-cn');

export const DATE_TIME_FORMAT = 'YYYY-MM-DD HH:mm';
export const DATE_FORMAT = 'YYYY-MM-DD';
export const DATE_TIME_SECOND_FORMAT = 'YYYY-MM-DD HH:mm:ss';

export function formatDateTime(value?: string | null, fmt = DATE_TIME_FORMAT): string {
  if (!value) return '-';
  const d = dayjs(value);
  return d.isValid() ? d.format(fmt) : '-';
}

export function formatDate(value?: string | null): string {
  return formatDateTime(value, DATE_FORMAT);
}

/** 本地时间 -> UTC ISO8601（接口统一传 UTC） */
export function toUtcIso(value?: string | null): string | null {
  if (!value) return null;
  const d = dayjs(value);
  return d.isValid() ? d.utc().toISOString() : null;
}

export function nowIso(): string {
  return dayjs().utc().toISOString();
}

export { dayjs };
