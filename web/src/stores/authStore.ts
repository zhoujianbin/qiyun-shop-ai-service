import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { authApi } from '@/api/endpoints/auth';
import { tokenStore } from '@/api/tokenStore';
import { usePermissionStore } from './permissionStore';
import { useChannelScopeStore } from './channelScopeStore';
import type {
  CurrentUser, CustomerLoginRequest, CustomerRegisterRequest, StaffLoginRequest, TokenPair,
} from '@/types/domain';
import type { RoleCode } from '@/types/permissions';

export type AuthStatus = 'idle' | 'loading' | 'authed' | 'expired' | 'error';

interface AuthState {
  user: CurrentUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  expiresAt: number | null;
  status: AuthStatus;
  errorMessage: string | null;
  bootstrapped: boolean;

  setTokens: (pair: TokenPair) => void;
  setUser: (user: CurrentUser) => void;
  loginStaff: (body: StaffLoginRequest) => Promise<CurrentUser>;
  loginCustomer: (body: CustomerLoginRequest) => Promise<CurrentUser>;
  loginAsGuest: () => Promise<CurrentUser>;
  register: (body: CustomerRegisterRequest) => Promise<CurrentUser>;
  bootstrap: () => Promise<void>;
  clearSession: () => void;
  logout: () => Promise<void>;
  hasRole: (role: RoleCode) => boolean;
}

function syncPermissionStore(user: CurrentUser | null): void {
  if (!user) {
    usePermissionStore.getState().reset();
    return;
  }
  usePermissionStore.getState().sync({
    permissions: user.permissions ?? [],
    roles: (user.roles ?? []) as RoleCode[],
    party: user.party,
  });
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      expiresAt: null,
      status: 'idle',
      errorMessage: null,
      bootstrapped: false,

      setTokens: (pair) => {
        tokenStore.set({
          accessToken: pair.access_token,
          refreshToken: pair.refresh_token,
          expiresAt: Date.now() + (pair.expires_in ?? 0) * 1000,
        });
        if (pair.user) {
          set({ user: pair.user });
          syncPermissionStore(pair.user);
        }
      },

      setUser: (user) => {
        set({ user, status: 'authed', errorMessage: null });
        syncPermissionStore(user);
      },

      loginStaff: async (body) => {
        set({ status: 'loading', errorMessage: null });
        const pair = await authApi.staffLogin(body);
        get().setTokens(pair);
        const user = pair.user ?? (await authApi.me());
        get().setUser(user);
        return user;
      },

      loginCustomer: async (body) => {
        set({ status: 'loading', errorMessage: null });
        const pair = await authApi.customerLogin(body);
        get().setTokens(pair);
        const user = pair.user ?? (await authApi.me());
        get().setUser(user);
        return user;
      },

      loginAsGuest: async () => {
        set({ status: 'loading', errorMessage: null });
        const pair = await authApi.guestSession({});
        get().setTokens(pair);
        const user = pair.user ?? (await authApi.me());
        get().setUser(user);
        return user;
      },

      register: async (body) => {
        set({ status: 'loading', errorMessage: null });
        await authApi.register(body);
        return get().loginCustomer({ mobile: body.mobile, password: body.password });
      },

      bootstrap: async () => {
        const { refreshToken, accessToken, expiresAt } = get();
        if (!refreshToken && !accessToken) {
          set({ status: 'idle', bootstrapped: true });
          return;
        }
        tokenStore.set({ accessToken, refreshToken, expiresAt });
        set({ status: 'loading' });
        try {
          const user = await authApi.me();
          get().setUser(user);
          set({ bootstrapped: true });
        } catch {
          // client 已在 401 时尝试单飞刷新；仍失败则视为过期
          tokenStore.clear();
          set({ user: null, accessToken: null, refreshToken: null, expiresAt: null, status: 'expired', bootstrapped: true });
          syncPermissionStore(null);
        }
      },

      clearSession: () => {
        tokenStore.clear();
        usePermissionStore.getState().reset();
        useChannelScopeStore.getState().reset();
        set({ user: null, accessToken: null, refreshToken: null, expiresAt: null, status: 'idle' });
      },

      logout: async () => {
        try {
          await authApi.logout();
        } catch {
          // 登出接口失败不阻塞本地清理
        }
        get().clearSession();
      },

      hasRole: (role) => (get().user?.roles ?? []).includes(role),
    }),
    {
      name: 'qy.auth',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        user: state.user,
        refreshToken: state.refreshToken,
        expiresAt: state.expiresAt,
      }),
      onRehydrateStorage: () => (state) => {
        if (state?.refreshToken || state?.accessToken) {
          tokenStore.set({
            accessToken: state.accessToken,
            refreshToken: state.refreshToken,
            expiresAt: state.expiresAt,
          });
        }
        if (state?.user) syncPermissionStore(state.user);
      },
    },
  ),
);

// token 变化（含 client 单飞刷新）镜像回 store；登出/刷新失败清空会话
tokenStore.onChanged((snapshot) => {
  useAuthStore.setState({
    accessToken: snapshot.accessToken,
    refreshToken: snapshot.refreshToken,
    expiresAt: snapshot.expiresAt,
  });
});
tokenStore.onCleared(() => {
  useAuthStore.getState().clearSession();
});
