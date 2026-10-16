/**
 * 令牌内存仓：client 与 authStore 的唯一令牌交互点，避免二者互相 import 造成环。
 * access token 只在内存；refresh token 由 authStore 另存 sessionStorage 以便刷新恢复。
 */
export interface TokenSnapshot {
  accessToken: string | null;
  refreshToken: string | null;
  expiresAt: number | null;
}

let snapshot: TokenSnapshot = { accessToken: null, refreshToken: null, expiresAt: null };
let clearedHandler: (() => void) | null = null;
let changedHandler: ((next: TokenSnapshot) => void) | null = null;

export const tokenStore = {
  get(): TokenSnapshot {
    return snapshot;
  },
  getAccess(): string | null {
    return snapshot.accessToken;
  },
  getRefresh(): string | null {
    return snapshot.refreshToken;
  },
  set(next: Partial<TokenSnapshot>): void {
    snapshot = { ...snapshot, ...next };
    changedHandler?.(snapshot);
  },
  clear(): void {
    snapshot = { accessToken: null, refreshToken: null, expiresAt: null };
    changedHandler?.(snapshot);
  },
  onChanged(handler: (next: TokenSnapshot) => void): void {
    changedHandler = handler;
  },
  onCleared(handler: () => void): void {
    clearedHandler = handler;
  },
  notifyCleared(): void {
    snapshot = { accessToken: null, refreshToken: null, expiresAt: null };
    clearedHandler?.();
  },
};
