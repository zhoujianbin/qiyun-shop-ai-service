/** 脱敏工具：后端已返回脱敏值时直接展示，前端不做还原。兜底对未脱敏字段做展示级脱敏。 */
export function maskMobile(mobile?: string | null): string {
  if (!mobile) return '-';
  if (mobile.includes('*')) return mobile;
  return mobile.replace(/^(\d{3})\d{4}(\d{4})$/, '$1****$2');
}

export function maskName(name?: string | null): string {
  if (!name) return '-';
  if (name.includes('*')) return name;
  return name.length <= 1 ? name : `${name[0]}*${name.slice(-1)}`;
}
