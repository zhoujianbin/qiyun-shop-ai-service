import { Navigate, Outlet, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { useAuthStore } from '@/stores/authStore';
import { usePermissionStore } from '@/stores/permissionStore';
import { ROUTES } from '@/constants/routes';
import type { PermissionCode } from '@/types/permissions';

export interface RequireAuthProps {
  loginPath?: string;
  /** 直接包裹组件时传入；作为父级路由使用时留空并渲染 <Outlet /> */
  children?: ReactNode;
}

/** 登录守卫：bootstrap 中显示全屏 loading；未登录跳登录并带 redirect。 */
export function RequireAuth({ loginPath = ROUTES.login, children }: RequireAuthProps) {
  const user = useAuthStore((state) => state.user);
  const bootstrapped = useAuthStore((state) => state.bootstrapped);
  const location = useLocation();

  if (!bootstrapped) {
    return (
      <div style={{ padding: 48 }} aria-busy="true">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }
  if (!user) {
    const redirect = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`${loginPath}?redirect=${redirect}`} replace />;
  }
  return children ? <>{children}</> : <Outlet />;
}

export interface RequirePermissionProps {
  permissions?: Array<PermissionCode | string>;
  anyOf?: Array<PermissionCode | string>;
  children: ReactNode;
}

/** 权限守卫：缺任一权限跳 /admin/403（携带所需权限码便于运维定位）。 */
export function RequirePermission({ permissions, anyOf, children }: RequirePermissionProps) {
  const hasAll = usePermissionStore((state) => state.hasAll);
  const hasAny = usePermissionStore((state) => state.hasAny);
  const required = permissions ?? anyOf ?? [];
  const allowed = permissions && permissions.length > 0 ? hasAll(permissions) : hasAny(anyOf ?? []);
  if (!allowed) {
    return <Navigate to={ROUTES.adminForbidden} replace state={{ required }} />;
  }
  return <>{children}</>;
}

/** 游客守卫：已登录时跳转到 redirect 或首页。 */
export function RequireGuest({ redirect = ROUTES.home }: { redirect?: string }) {
  const user = useAuthStore((state) => state.user);
  const bootstrapped = useAuthStore((state) => state.bootstrapped);
  const location = useLocation();
  if (!bootstrapped) {
    return (
      <div style={{ padding: 48 }} aria-busy="true">
        <LoadingSkeleton rows={4} />
      </div>
    );
  }
  if (user) {
    const params = new URLSearchParams(location.search);
    const target = params.get('redirect') ?? redirect;
    return <Navigate to={target} replace />;
  }
  return <Outlet />;
}
