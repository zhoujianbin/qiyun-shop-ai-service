import { addMoney, formatMoney, fromCents, isValidMoney, subMoney, toCents } from '@/utils/money';
import type { MoneyString } from '@/types/money';

/** 金额展示与运算的统一入口。 */
export function useMoney() {
  return {
    format: (value: MoneyString | null | undefined, withSymbol = true) => formatMoney(value, withSymbol),
    cents: (value: MoneyString | null | undefined) => toCents(value),
    fromCents,
    add: addMoney,
    sub: subMoney,
    validate: isValidMoney,
  };
}
