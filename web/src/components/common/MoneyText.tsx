import type { CSSProperties } from 'react';
import { formatMoney } from '@/utils/money';
import type { MoneyString } from '@/types/money';

export interface MoneyTextProps {
  value: MoneyString | null | undefined;
  withSymbol?: boolean;
  strong?: boolean;
  danger?: boolean;
  muted?: boolean;
  style?: CSSProperties;
}

/** 金额展示：等宽数字，负数红色并带 - 号；读屏读作“人民币 x 元”。 */
export function MoneyText({ value, withSymbol = true, strong, danger, muted, style }: MoneyTextProps) {
  const negative = typeof value === 'string' && value.trim().startsWith('-');
  const text = formatMoney(value, withSymbol);
  const color = danger || negative ? '#DC2626' : muted ? '#6B7280' : undefined;
  const aria = formatMoney(value, false);
  return (
    <span
      aria-label={`人民币 ${aria} 元`}
      style={{ fontVariantNumeric: 'tabular-nums', fontWeight: strong ? 600 : undefined, color, whiteSpace: 'nowrap', ...style }}
    >
      {text}
    </span>
  );
}
