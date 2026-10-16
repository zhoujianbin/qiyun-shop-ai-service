import type { MoneyString } from '@/types/money';

/** 金额字符串 -> 整数分（唯一允许的金额运算入口）。 */
export function toCents(value: MoneyString | null | undefined): number {
  if (value === null || value === undefined || value === '') return 0;
  const raw = String(value).trim();
  const negative = raw.startsWith('-');
  const [intPart = '0', decPart = ''] = raw.replace(/^-/, '').split('.');
  const intCents = Number.parseInt(intPart || '0', 10) * 100;
  const decCents = Number.parseInt((decPart + '00').slice(0, 2), 10);
  if (Number.isNaN(intCents) || Number.isNaN(decCents)) return 0;
  const total = intCents + decCents;
  return negative ? -total : total;
}

/** 整数分 -> 金额字符串（两位小数）。 */
export function fromCents(cents: number): MoneyString {
  const negative = cents < 0;
  const abs = Math.abs(Math.round(cents));
  const intPart = Math.floor(abs / 100);
  const decPart = String(abs % 100).padStart(2, '0');
  return `${negative ? '-' : ''}${intPart}.${decPart}`;
}

export function addMoney(...values: Array<MoneyString | null | undefined>): MoneyString {
  return fromCents(values.reduce((acc, v) => acc + toCents(v), 0));
}

export function subMoney(a: MoneyString | null | undefined, b: MoneyString | null | undefined): MoneyString {
  return fromCents(toCents(a) - toCents(b));
}

/** 金额格式化为 ¥1,234.50 */
export function formatMoney(value: MoneyString | null | undefined, withSymbol = true): string {
  if (value === null || value === undefined || value === '') return withSymbol ? '¥0.00' : '0.00';
  const negative = String(value).trim().startsWith('-');
  const text = fromCents(Math.abs(toCents(value)));
  const [intPart = '0', decPart = '00'] = text.split('.');
  const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${negative ? '-' : ''}${withSymbol ? '¥' : ''}${grouped}.${decPart}`;
}

/** 校验金额：0.00 ~ 99999999.99，最多两位小数。 */
export function isValidMoney(value: string | null | undefined): boolean {
  if (value === null || value === undefined || value === '') return false;
  if (!/^\d{1,8}(\.\d{1,2})?$/.test(String(value).trim())) return false;
  const cents = toCents(value);
  return cents >= 0 && cents <= 9999999999;
}

/** 输入过滤：只保留数字与最多两位小数 */
export function sanitizeMoneyInput(text: string): string {
  const cleaned = String(text).replace(/[^\d.]/g, '');
  const parts = cleaned.split('.');
  const head = (parts[0] ?? '').slice(0, 8);
  if (parts.length === 1) return head;
  return `${head}.${(parts[1] ?? '').slice(0, 2)}`;
}
