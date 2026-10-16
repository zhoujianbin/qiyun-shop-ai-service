import { maskMobile, maskName } from '@/utils/mask';

export interface MaskedTextProps {
  value?: string | null;
  type?: 'mobile' | 'name';
}

/** 脱敏展示：后端已返回脱敏值时不还原；兜底做展示级脱敏。 */
export function MaskedText({ value, type = 'mobile' }: MaskedTextProps) {
  if (!value) return <span>-</span>;
  return <span>{type === 'mobile' ? maskMobile(value) : maskName(value)}</span>;
}
