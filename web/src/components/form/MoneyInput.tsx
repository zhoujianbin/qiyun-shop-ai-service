import Input from 'antd/es/input';
import type { InputProps } from 'antd';
import { sanitizeMoneyInput } from '@/utils/money';

export interface MoneyInputProps extends Omit<InputProps, 'value' | 'onChange' | 'prefix'> {
  value?: string;
  onChange?: (value: string) => void;
  currency?: string;
}

/**
 * 金额输入：受控字符串，最多两位小数、禁止负值与科学计数法。
 * value 始终是 string（后端口径 numeric(14,2)），不做浮点运算。
 */
export function MoneyInput({ value, onChange, currency = '¥', ...rest }: MoneyInputProps) {
  return (
    <Input
      {...rest}
      inputMode="decimal"
      prefix={currency}
      value={value ?? ''}
      onChange={(event) => onChange?.(sanitizeMoneyInput(event.target.value))}
    />
  );
}
