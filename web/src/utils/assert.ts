export function assertNever(value: never, message = '未处理的枚举值'): never {
  throw new Error(`${message}: ${String(value)}`);
}

export function invariant(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

export function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}
