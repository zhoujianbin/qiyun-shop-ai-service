import { zhCN } from './zh-CN';

export function t(key: string): string {
  return zhCN[key] ?? key;
}

export { zhCN };
