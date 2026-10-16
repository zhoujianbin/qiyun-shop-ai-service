import Tooltip from 'antd/es/tooltip';
import { cloneElement, isValidElement, type ReactElement, type ReactNode } from 'react';
import { usePermissionStore } from '@/stores/permissionStore';
import type { PermissionCode } from '@/types/permissions';

export interface PermissionGateProps {
  permission?: PermissionCode | string;
  anyOf?: Array<PermissionCode | string>;
  mode?: 'hide' | 'disable';
  fallbackReason?: string;
  fallback?: ReactNode;
  children: ReactNode;
}

/**
 * 按钮级权限：hide（默认，不渲染）或 disable（保留入口并说明原因）。
 * 前端权限仅用于体验，写请求后端必须二次校验。
 */
export function PermissionGate({
  permission,
  anyOf,
  mode = 'hide',
  fallbackReason = '无操作权限',
  fallback = null,
  children,
}: PermissionGateProps) {
  const has = usePermissionStore((state) => state.has);
  const allowed = anyOf && anyOf.length > 0 ? anyOf.some((code) => has(code)) : permission ? has(permission) : true;

  if (allowed) return <>{children}</>;
  if (mode === 'hide') return <>{fallback}</>;

  const reason = fallbackReason;
  if (isValidElement(children)) {
    const child = children as ReactElement<{ disabled?: boolean }>;
    return (
      <Tooltip title={reason}>
        <span style={{ display: 'inline-block', cursor: 'not-allowed' }}>
          {cloneElement(child, { disabled: true })}
        </span>
      </Tooltip>
    );
  }
  return (
    <Tooltip title={reason}>
      <span style={{ display: 'inline-block', cursor: 'not-allowed' }}>{children}</span>
    </Tooltip>
  );
}
