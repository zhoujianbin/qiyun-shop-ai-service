import { create } from 'zustand';
import { PERMISSIONS, type PermissionCode } from '@/types/permissions';
import type { RoleCode } from '@/types/permissions';

interface PermissionState {
  permissions: string[];
  roles: RoleCode[];
  party: 'STAFF' | 'CUSTOMER' | 'GUEST' | null;
  sync: (payload: { permissions?: string[]; roles?: RoleCode[]; party?: 'STAFF' | 'CUSTOMER' | 'GUEST' }) => void;
  reset: () => void;
  has: (code: PermissionCode | string) => boolean;
  hasAny: (codes: Array<PermissionCode | string>) => boolean;
  hasAll: (codes: Array<PermissionCode | string>) => boolean;
}

export const usePermissionStore = create<PermissionState>((set, get) => ({
  permissions: [],
  roles: [],
  party: null,
  sync: ({ permissions = [], roles = [], party }) =>
    set({ permissions, roles, party: party ?? get().party }),
  reset: () => set({ permissions: [], roles: [], party: null }),
  has: (code) => {
    const { permissions, roles } = get();
    if (roles.includes('ENTERPRISE_ADMIN')) return true;
    return permissions.includes(code);
  },
  hasAny: (codes) => codes.some((code) => get().has(code)),
  hasAll: (codes) => codes.every((code) => get().has(code)),
}));

export const ALL_PERMISSIONS: readonly PermissionCode[] = PERMISSIONS;
