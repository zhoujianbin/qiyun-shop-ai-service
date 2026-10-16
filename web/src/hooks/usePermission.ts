import { usePermissionStore } from '@/stores/permissionStore';
import type { PermissionCode } from '@/types/permissions';

/** 判断当前登录主体是否具备某权限码（企业管理员视为全量）。 */
export function usePermission(code: PermissionCode | string): boolean {
  return usePermissionStore((state) => state.has(code));
}

export function useHasAnyPermission(codes: Array<PermissionCode | string>): boolean {
  return usePermissionStore((state) => state.hasAny(codes));
}

export function useHasAllPermissions(codes: Array<PermissionCode | string>): boolean {
  return usePermissionStore((state) => state.hasAll(codes));
}
